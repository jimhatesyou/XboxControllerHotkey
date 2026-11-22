# XboxControllerHotkey V2.0.0 — Portable Edition

The first official V2 release.

## Highlights
- Minimal Windows system-tray interface.
- Controller connection monitoring and connection notifications.
- Controller battery display when available.
- Configurable two-button simultaneous Xbox Game Bar Record That shortcut.
- Controller selection, Xbox Accessories shortcut and Windows capture-settings shortcut.
- Connected/disconnected tray status icon.
- Optional Start with Windows registration.
- Standalone, one-file Windows executable. No installer required.

## Requirements
- Windows 10 or Windows 11, 64-bit.
- Xbox Game Bar installed, enabled and configured for Record That.
- A supported controller and compatible Windows/SDL driver.

## Installation
Download `XboxControllerHotkey.exe` and run it. Keep it in a stable folder if you enable Start with Windows.

## Important
XboxControllerHotkey does not record or store video itself. It triggers Xbox Game Bar's existing Record That feature.

- Added Windows single-instance protection. Re-launching while the app is already running exits quietly instead of creating a duplicate tray process.
