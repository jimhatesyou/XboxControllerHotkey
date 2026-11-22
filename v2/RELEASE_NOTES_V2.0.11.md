# XboxControllerHotkey V2.0.11

## Startup crash fix
- Fixed invalid Qt object parenting introduced with background controller scanning.
- The tray application is not a QObject, so it cannot be passed as the parent to QTimer or QThread.
- The monitor timer and controller scan worker are now created without that invalid parent.
- Background scanning and UI-thread separation are retained.

## Validation
- Python syntax compilation passed.
- Windows runtime execution still needs confirmation on a Windows machine.
