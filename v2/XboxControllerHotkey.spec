# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

datas, binaries, hiddenimports = collect_all("pygame")
try:
    win_datas, win_binaries, win_hidden = collect_all("winsdk")
    datas += win_datas
    binaries += win_binaries
    hiddenimports += win_hidden
except Exception:
    pass

asset_names = [
    "controller-icon.png", "tray-background.png", "setup-background.png",
    "powered-by-logo.gif", "powered-by-logo.png", "bluetooth-icon.png",
    "xbox-icon.png", "usb-icon.png", "arrow-back-white.png",
    "arrow-forward-white.png", "app-icon.ico"
]
datas += [(f"assets/{name}", "assets") for name in asset_names]

a = Analysis(
    ["app.py"], pathex=[], binaries=binaries, datas=datas,
    hiddenimports=hiddenimports, hookspath=[], hooksconfig={},
    runtime_hooks=[], excludes=[], noarchive=False
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, a.binaries, a.datas, [],
    name="XboxControllerHotkey", debug=False,
    bootloader_ignore_signals=False, strip=False, upx=True,
    console=False, disable_windowed_traceback=False,
    argv_emulation=False, target_arch=None,
    codesign_identity=None, entitlements_file=None,
    icon="assets/app-icon.ico"
)
