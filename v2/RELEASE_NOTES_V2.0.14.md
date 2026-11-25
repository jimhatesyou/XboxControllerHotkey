# XboxControllerHotkey V2.0.14

This release includes the V2.0.12 foundation and the improvements added through V2.0.14.

## Features

- Rebuilt the original command-line script as a standalone Windows application with a graphical interface.
- Detects Xbox controllers, supports preferred-controller selection, and switches to another available controller when needed.
- Lets users configure the controller shortcut for Xbox Game Bar's Record That feature.
- Runs in the system tray and can start with Windows.
- Reports controller connection type and battery information when available.
- Checks for updates and verifies downloaded releases with SHA256 before applying them.
- Includes quick access to Windows capture settings and Xbox Accessories.
- Added an option to skip first-run controller setup and launch the app immediately.
- Added a preferred connection method page within the in-app shortcut configuration flow.
- Added a home-screen button to open the Windows-configured Captures folder.

## Interface & Usability

- Added a dedicated first-run setup flow for choosing a preferred controller connection method.
- Setup can now be skipped; the app starts normally and the connection preference can be configured later from the popover.
- Preferred connection settings are available without leaving the main application.
- The home screen provides direct access to the user's configured Windows Captures folder.

## Technical Improvements

- Uses PySide6 for the application and pygame/SDL2 for game-controller input.
- Moves controller polling and device scans off the UI thread to keep the application responsive.
- Caches scan results, prevents overlapping scans, and uses synchronization around shared controller state.
- Uses Windows device information to improve controller identification and connection-type reporting.
- Uses the Windows Known Folder API to locate the configured Captures folder, including custom save locations.
- Adds single-instance protection and portable PyInstaller packaging.
- Builds the Windows executable and SHA256 checksum through GitHub Actions.

## Controller Notifications

- Displays the current controller connection status when the application launches.
- Shows a notification when a controller connects or disconnects.
- Notifications automatically close after five seconds.
- If the connection status changes while a notification is visible, it is immediately replaced with the latest status.

## Fixes & Reliability

- Improved controller identification and battery matching.
- Corrected connection reporting for adapters and wireless devices.
- Removed blocking device lookups from the refresh path.
- Fixed background scan and Qt timer/thread lifecycle issues.
- Improved update download and replacement safety.

The original V1 command-line source remains in the repository.
