# XboxControllerHotkey V2.0.12

## Features
- Rebuilt the original command-line script as a standalone Windows application.
- Detects Xbox controllers, supports preferred-controller selection, and switches to another available controller when needed.
- Lets users configure the controller shortcut for Xbox Game Bar's Record That feature.
- Runs in the system tray and can start with Windows.
- Reports controller connection and battery information when available.
- Checks for updates and verifies downloaded releases with SHA256 before applying them.
- Includes Windows capture-settings access and links to Xbox Accessories.

## Technical changes
- Uses PySide6 for the application and pygame/SDL2 for game-controller input.
- Moves controller polling and device scans off the UI thread to keep the application responsive.
- Caches scan results, prevents overlapping scans, and uses synchronization around shared controller state.
- Uses Windows device information to improve controller identification and connection-type reporting.
- Adds single-instance protection and portable PyInstaller packaging.
- Builds the Windows executable and checksum through GitHub Actions.

## Fixes
- Improved controller identification and battery matching.
- Corrected connection reporting for adapters and wireless devices.
- Removed blocking device lookups from the refresh path.
- Fixed background scan and Qt timer/thread lifecycle issues.
- Improved update download and replacement safety.

The original V1 command-line source remains in the repository.
