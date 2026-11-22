# XboxControllerHotkey V2.0.12 — Portable Edition

A lightweight Windows system-tray companion that lets you trigger Xbox Game Bar's **Record That** capture using a simultaneous two-button controller shortcut.

**This is not a standalone clipping or recording application.** It sends the configured keyboard shortcut to Windows Xbox Game Bar. Xbox Game Bar capture must already be installed, enabled and configured.

## Download

Download **XboxControllerHotkey.exe** from the [V2.0.12 GitHub Releases page](https://github.com/jimhatesyou/XboxControllerHotkey/releases).

- No installer.
- No Python installation required.
- No administrator privileges required for normal use.
- Run the EXE from a folder where you want to keep it.

## Features

- Runs quietly in the Windows system tray.
- Monitors controller connections and notifies when a supported controller connects or disconnects.
- Displays detected controller name and battery information.
- Battery reporting uses matching controller information where available, with a fallback to XInput battery status.
- Checks GitHub Releases at startup and offers optional portable EXE updates. Downloads are SHA-256 verified before replacing the running executable.
- Configurable two-button simultaneous shortcut for Xbox Game Bar **Record That**.
- Controller selection and supported controller detection.
- Quick access to Xbox Accessories and Windows capture settings.
- Custom tray icon with connected/disconnected status.
- Optional **Start with Windows** setting in the tray's right-click menu.
- Compact controller status popover with About and FAQs.

## Start with Windows

Right-click the system-tray icon and enable **Start with Windows**.

This registers the current EXE under the current Windows user's startup settings. It does not require administrator access.

**Portable-app note:** Keep the EXE in a permanent folder. If you move or delete it after enabling startup, the saved startup path will no longer point to the application. Disable startup before moving the EXE, then enable it again from its new location.

## Xbox Game Bar requirements

XboxControllerHotkey does not record, encode, or store clips itself. It triggers the Windows Xbox Game Bar **Record That** shortcut.

Before using it, make sure:
1. Xbox Game Bar is installed and enabled.
2. Background recording / capture is configured in Windows.
3. The Game Bar Record That keyboard shortcut matches the shortcut sent by this app.

Capture duration, audio, video quality and save location are controlled by Windows.

## Supported controllers

Xbox controllers are the primary target. Other controllers may work when Windows/SDL exposes them as supported game controllers. Detection, button mapping, battery reporting and connection details can vary by controller, driver and connection method.

## Build from source

The release is a standalone, one-file Windows executable built with PyInstaller.

Requirements for building:
- Windows 10 or Windows 11
- 64-bit Python 3.10+
- Internet connection for installing build dependencies

To build locally:
1. Install Python 3.10 or newer.
2. Run `build.bat`.
3. The portable executable will be created at `dist\XboxControllerHotkey.exe`.

The GitHub Actions workflow can also build and publish the portable EXE and its SHA-256 checksum. See `.github/workflows/build-portable-release.yml`. The updater expects those two release assets to be attached to each stable release.

## Project

[GitHub repository](https://github.com/jimhatesyou/XboxControllerHotkey)

[Report a bug or request a feature](https://github.com/jimhatesyou/XboxControllerHotkey/issues)

## License

See [LICENSE](LICENSE).


## Single-instance protection

Only one XboxControllerHotkey process can run per Windows interactive session. If the EXE is launched again while it is already running, the new launch displays a notice and exits, leaving the existing tray instance untouched. Windows automatically releases the named mutex when the process exits or crashes, so no stale lock file needs cleanup.

## Automatic updates

At startup, the app checks the latest stable GitHub release. If no newer version exists, it does not display anything. If an update is available, you can update immediately, be reminded at the next launch, or disable startup checks. Manual checks remain available in About. The portable updater downloads the release EXE and its SHA-256 checksum, verifies the download, then replaces the current EXE after the app exits. Keep the EXE in a user-writable folder for self-updates to work.
