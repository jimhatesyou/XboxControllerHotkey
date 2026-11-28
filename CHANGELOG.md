# Changelog

All notable changes to XboxControllerHotkey are documented here.

## [2.0.32] - Consolidated release notes

This entry consolidates the changes originally published across v2.0.24 through v2.0.31.

### Interface and layout
- Refined home-screen button spacing and sizing.
- Added updater download progress feedback and a three-second relaunch countdown before the application closes to start the replacement.
- Increased the JimHub footer logo to 2.5 times its previous size while keeping the “Powered by” label vertically aligned.
- Corrected the application title/version layout so the version appears beneath the XboxControllerHotkey heading.
- Balanced the green action-button icon and label placement without changing button or popover dimensions.
- Standardized About-page button typography to match the FAQs button.

### Updater reliability
- Added an updater-only retry for the single-instance mutex and retained duplicate-instance protection for normal launches.
- Added an explicit updater-relaunch command-line marker and detect it before Qt initialization.
- Corrected startup verification for PyInstaller one-file builds: the updater verifies the application child process, its parent bootloader process, the installed executable path, and the expected application version rather than incorrectly requiring the parent and child PIDs to match.
- Retained rollback behavior for genuine update-startup verification failures.

### Verification
- Confirmed the v2.0.32 to v2.0.33 in-app update completed, relaunched successfully, and did not display the false duplicate-instance warning.

## [2.0.14] - 2026-11-25

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
