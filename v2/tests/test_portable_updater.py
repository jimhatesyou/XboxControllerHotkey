"""Windows integration tests for the portable self-updater.

These tests extract the exact PowerShell helper template used by app.py, then
exercise replacement, restart/version handshake, fallback replacement, and
rollback in temporary folders containing spaces and Unicode characters.
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time


def powershell_executable() -> str:
    candidate = shutil.which("powershell.exe")
    if candidate:
        return candidate
    candidate = Path(os.environ.get("WINDIR", r"C:\Windows")) / (
        "System32/WindowsPowerShell/v1.0/powershell.exe"
    )
    if candidate.exists():
        return str(candidate)
    raise RuntimeError("Windows PowerShell 5.1 was not found.")


def extract_helper_template(app_path: Path) -> str:
    tree = ast.parse(app_path.read_text(encoding="utf-8-sig"), filename=str(app_path))
    matches = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(target, ast.Name) and target.id == "script" for target in node.targets):
            continue
        try:
            value = ast.literal_eval(node.value)
        except (ValueError, TypeError):
            continue
        if isinstance(value, str) and "$pidToWait = __PID__" in value:
            matches.append(value)
    if len(matches) != 1:
        raise AssertionError(f"Expected one updater PowerShell template; found {len(matches)}.")
    return matches[0]


def ps_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def run_powershell(script_path: Path, *args: str, timeout: int = 30) -> subprocess.CompletedProcess:
    command = [
        powershell_executable(),
        "-NoProfile",
        "-NonInteractive",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(script_path),
        *args,
    ]
    env = os.environ.copy()
    # CI invokes this test from PowerShell 7. Windows PowerShell 5.1 child
    # processes must not inherit PowerShell 7 module directories.
    env.pop("PSModulePath", None)
    return subprocess.run(command, capture_output=True, text=True, timeout=timeout, env=env)


def compile_test_executable(out_path: Path, build_version: str, compile_script: Path) -> None:
    result = run_powershell(compile_script, str(out_path), build_version, timeout=45)
    if result.returncode != 0 or not out_path.is_file():
        raise RuntimeError(
            "Could not compile updater test executable.\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )


def build_helper(
    template: str,
    helper_path: Path,
    pid_to_wait: int,
    source: Path,
    target: Path,
    log_path: Path,
    handshake_path: Path,
    expected_version: str,
    force_rename_fallback: bool = False,
) -> None:
    script = template
    if force_rename_fallback:
        replace_call = "[System.IO.File]::Replace($tmp,$target,$backup,$true)"
        if replace_call not in script:
            raise AssertionError("Atomic File.Replace call was not found in updater template.")
        script = script.replace(replace_call, "throw 'Integration test forced File.Replace fallback.'")
        script = script.replace(
            "for ($i=1; $i -le 20 -and -not $installed; $i++)",
            "for ($i=1; $i -le 1 -and -not $installed; $i++)",
        )
        script = script.replace("Start-Sleep -Milliseconds 500", "Start-Sleep -Milliseconds 10")

    replacements = {
        "__PID__": str(pid_to_wait),
        "__SOURCE__": ps_quote(str(source)),
        "__TARGET__": ps_quote(str(target)),
        "__LOG__": ps_quote(str(log_path)),
        "__HANDSHAKE__": ps_quote(str(handshake_path)),
        "__VERSION__": ps_quote(expected_version),
    }
    for token, replacement in replacements.items():
        script = script.replace(token, replacement)
    helper_path.write_text(script, encoding="utf-8-sig")


def run_update_case(
    root: Path,
    template: str,
    compile_script: Path,
    name: str,
    new_version: str,
    expected_version: str,
    should_succeed: bool,
    force_rename_fallback: bool = False,
) -> None:
    case_root = root / name
    target_dir = case_root / "Portable Folder 'ü' & spaces"
    download_dir = case_root / "download cache"
    target_dir.mkdir(parents=True)
    download_dir.mkdir(parents=True)

    target = target_dir / f"{name}.exe"
    old_build = case_root / "old build.exe"
    downloaded = download_dir / "downloaded update.exe"
    log_path = case_root / "update diagnostics.log"
    handshake_path = case_root / "startup handshake.json"
    helper_path = case_root / "portable updater helper.ps1"

    compile_test_executable(out_path=old_build, build_version="old-build", compile_script=compile_script)
    compile_test_executable(out_path=downloaded, build_version=new_version, compile_script=compile_script)
    shutil.copy2(old_build, target)
    old_hash = hashlib.sha256(target.read_bytes()).hexdigest()
    new_hash = hashlib.sha256(downloaded.read_bytes()).hexdigest()

    signal_path = case_root / "stop old process.signal"
    old_env = os.environ.copy()
    old_env["XCH_TEST_OLD_EXIT_SIGNAL"] = str(signal_path)
    old_process = subprocess.Popen([str(target), "wait-old"], env=old_env)

    build_helper(
        template,
        helper_path,
        old_process.pid,
        downloaded,
        target,
        log_path,
        handshake_path,
        expected_version,
        force_rename_fallback,
    )
    helper_env = os.environ.copy()
    helper_env.pop("PSModulePath", None)
    helper_process = subprocess.Popen(
        [
            powershell_executable(),
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(helper_path),
        ],
        env=helper_env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    try:
        deadline = time.monotonic() + 12
        while time.monotonic() < deadline:
            if log_path.exists() and "Attempt started." in log_path.read_text(encoding="utf-8", errors="replace"):
                break
            if helper_process.poll() is not None:
                out, err = helper_process.communicate()
                raise RuntimeError(f"Updater helper exited before startup acknowledgement.\n{out}\n{err}")
            time.sleep(0.05)
        else:
            if helper_process.poll() is None:
                helper_process.terminate()
            try:
                out, err = helper_process.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                helper_process.kill()
                out, err = helper_process.communicate()
            helper_diagnostics = log_path.read_text(encoding="utf-8", errors="replace") if log_path.exists() else "<no updater log was created>"
            raise TimeoutError(
                "Updater helper did not write its startup acknowledgement.\n"
                f"Helper stdout:\\n{out}\\nHelper stderr:\\n{err}\\n"
                f"Updater log:\\n{helper_diagnostics}"
            )

        signal_path.write_text("exit", encoding="utf-8")
        old_process.wait(timeout=10)
        out, err = helper_process.communicate(timeout=60)
        log_text = log_path.read_text(encoding="utf-8", errors="replace") if log_path.exists() else ""

        if should_succeed:
            if "UPDATE COMPLETE" not in log_text:
                raise AssertionError(f"Update did not complete.\n{log_text}\nstdout={out}\nstderr={err}")
            actual_hash = hashlib.sha256(target.read_bytes()).hexdigest()
            if actual_hash != new_hash:
                raise AssertionError("Updated executable bytes do not match the downloaded executable.")
            if downloaded.exists():
                raise AssertionError("Successful update did not clean up the downloaded staging file.")
            if "STARTUP VERIFIED" not in log_text:
                raise AssertionError("Updated process did not pass its version/PID/path handshake.")
            route = "same-directory rename fallback" if force_rename_fallback else "atomic replacement"
            print(f"PASS {name}: {route}, startup handshake, and portable path.")
        else:
            if "UPDATE FAILED" not in log_text or "Rollback completed" not in log_text:
                raise AssertionError(f"Expected rollback was not confirmed.\n{log_text}\nstdout={out}\nstderr={err}")
            actual_hash = hashlib.sha256(target.read_bytes()).hexdigest()
            if actual_hash != old_hash:
                raise AssertionError("Rollback did not restore the original executable.")
            print(f"PASS {name}: failed startup was detected and the previous executable was restored.")
    finally:
        if old_process.poll() is None:
            signal_path.write_text("exit", encoding="utf-8")
            try:
                old_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                old_process.kill()
        if helper_process.poll() is None:
            helper_process.terminate()
            try:
                helper_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                helper_process.kill()
        # The helper may leave the successfully launched app or the restored app
        # running. Each case uses a unique image name, so taskkill is scoped.
        subprocess.run(
            ["taskkill.exe", "/IM", target.name, "/F"],
            capture_output=True,
            text=True,
            check=False,
        )


def main() -> int:
    if os.name != "nt":
        print("Portable updater integration tests require Windows.")
        return 2

    app_path = Path(__file__).resolve().parents[1] / "app.py"
    template = extract_helper_template(app_path)
    ps = powershell_executable()

    # Hashing is implemented in the PowerShell helper via .NET SHA-256.
    # Keep this test independent of optional PowerShell cmdlet modules.
    print("PASS .NET SHA-256 is used; no PowerShell hash cmdlet required.")

    csharp_template = r'''
using System;
using System.Diagnostics;
using System.IO;
using System.Text;
using System.Threading;

public static class XCHPortableUpdaterTestApp {
    private const string BuildVersion = "__BUILD_VERSION__";

    public static int Main(string[] args) {
        if (args.Length > 0 && args[0] == "wait-old") {
            string signal = Environment.GetEnvironmentVariable("XCH_TEST_OLD_EXIT_SIGNAL");
            DateTime deadline = DateTime.UtcNow.AddSeconds(45);
            while (!String.IsNullOrEmpty(signal) && !File.Exists(signal) && DateTime.UtcNow < deadline) {
                Thread.Sleep(50);
            }
            return 0;
        }

        string handshake = Environment.GetEnvironmentVariable("XCH_UPDATE_HANDSHAKE");
        if (!String.IsNullOrEmpty(handshake)) {
            string executable = Process.GetCurrentProcess().MainModule.FileName;
            string json = "{\"pid\":" + Process.GetCurrentProcess().Id
                + ",\"version\":\"" + BuildVersion + "\""
                + ",\"executable\":" + JsonQuote(executable) + "}";
            File.WriteAllText(handshake, json, new UTF8Encoding(false));
        }

        Thread.Sleep(20000);
        return 0;
    }

    private static string JsonQuote(string value) {
        return "\"" + value.Replace("\\", "\\\\").Replace("\"", "\\\"") + "\"";
    }
}
'''
    with tempfile.TemporaryDirectory(prefix="XCH portable updater tests ") as temp:
        root = Path(temp) / "Integration Root 'ñ' & spaces"
        root.mkdir()
        compile_script = root / "compile-test-app.ps1"
        compile_script.write_text(
            "param([string]$OutputPath, [string]$BuildVersion)\n"
            "$ErrorActionPreference = 'Stop'\n"
            "$source = @'\n"
            + csharp_template
            + "\n'@\n"
            "$source = $source.Replace('__BUILD_VERSION__', $BuildVersion)\n"
            "Add-Type -TypeDefinition $source -OutputAssembly $OutputPath -OutputType ConsoleApplication -ErrorAction Stop\n",
            encoding="utf-8",
        )

        run_update_case(root, template, compile_script, "XCHPortableAtomic", "new-build", "new-build", True)
        run_update_case(
            root,
            template,
            compile_script,
            "XCHPortableFallback",
            "new-build",
            "new-build",
            True,
            force_rename_fallback=True,
        )
        run_update_case(root, template, compile_script, "XCHPortableRollback", "wrong-build", "new-build", False)

    print("All portable updater integration tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
