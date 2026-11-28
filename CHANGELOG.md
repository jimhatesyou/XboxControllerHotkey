# Changelog

All notable changes to XboxControllerHotkey are documented here.

## [2.0.34] - 2026-11-28

### TL;DR
- Refined home-screen spacing, button sizing/alignment, title/version placement, and About-page typography.
- Updated the About button with the supplied white information icon.
- Enlarged the JimHub footer logo while keeping the “Powered by” label aligned.
- Added updater download progress and a three-second relaunch countdown.
- Improved executable replacement, rollback, and updater relaunch handling.
- Fixed PyInstaller startup verification by correctly validating the application child process, its bootloader parent, executable path, and version.
- Confirmed the v2.0.32 → v2.0.33 in-app update completed without the duplicate-instance popup.

This release consolidates the changes originally shipped in v2.0.24–v2.0.31. Versions v2.0.32 and v2.0.33 were updater-validation releases.

## [2.0.14] - 2026-11-25

### Improvements
- Controller connection and disconnection notifications remain visible for five seconds.
- Show the current controller connection status at startup.
- Replace a visible notification immediately when connection status changes.

## [2.0.13]

### Added
- Added an option to skip first-run controller setup.
- Added preferred connection method settings to the in-app shortcut configuration flow.
- Added a home-screen button to open the Windows-configured Captures folder.

### Improved
- Remember first-run setup dismissal.
- Keep preferred connection settings accessible from the popover.
- Use the Windows Known Folder API to respect custom Captures locations.

## [2.0.12]

### Initial V2 release
- Rebuilt the original command-line script as a standalone Windows application.
- Added Xbox controller detection, preferred-controller selection, and automatic failover.
- Added configurable controller shortcuts for Xbox Game Bar's Record That feature.
- Added system tray support and optional startup with Windows.
- Added controller connection and battery reporting when available.
- Added automatic update checks and SHA256 verification.
- Added Windows capture-settings access and Xbox Accessories links.
- Added background controller polling, device scanning, caching, synchronization, improved Windows device identification, single-instance protection, and portable PyInstaller packaging through GitHub Actions.
