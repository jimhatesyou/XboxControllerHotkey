# XboxControllerHotkey V2.0.14

## Features
- Added an option to skip first-run controller setup and launch the app immediately.
- Added a preferred connection method page within the in-app shortcut configuration flow.
- Added a home-screen button to open the Windows-configured Captures folder.

## Improvements
- First-run setup dismissal is remembered, while connection preferences remain accessible later from the popover.
- Captures folder lookup uses the Windows Known Folder API so custom save locations are respected.
- Controller connection and disconnection notifications now remain visible for five seconds.
- The app displays the current controller connection status on launch, whether a controller is connected or not.
- A connection status change immediately replaces any notification already on screen.
