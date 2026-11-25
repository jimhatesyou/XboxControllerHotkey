# Changelog

All notable changes to XboxControllerHotkey are documented here.

## [2.0.14] - 2026-11-25

### Improvements
- Controller connection and disconnection notifications now remain visible for five seconds.
- Show the current controller connection status when the application starts, whether a controller is connected or not.
- If the connection status changes while a notification is visible, immediately replace it with the updated status.

## [2.0.13]

### Added
- Added a **Skip and start the app** option to first-run controller setup so users can launch without selecting a preferred connection method or enrolling a controller first.
- Added a preferred connection method page within the in-app shortcut configuration flow.
- Added a **View my clips** button to the home screen to open the Captures folder configured in Windows.

### Improved
- Remember the first-run setup dismissal so users who skip setup are not forced through it again at every launch.
- Kept preferred connection settings accessible from the popover after skipping first-run setup.
- Used the Windows Known Folder API to locate the configured Captures folder, respecting a user-customized save location.

## [2.0.12]

### Initial V2 release
- Rebuilt the original command-line script as a standalone Windows application.
- Added Xbox controller detection, preferred-controller selection, and automatic failover.
- Added configurable controller shortcuts for Xbox Game Bar's Record That feature.
- Added system tray support and optional startup with Windows.
- Added controller connection and battery reporting when available.
- Added automatic update checks and SHA256 verification.
- Added Windows capture-settings access and Xbox Accessories links.
- Added background controller polling and device scanning, scan caching and synchronization, improved Windows device identification, single-instance protection, and portable PyInstaller packaging through GitHub Actions.
