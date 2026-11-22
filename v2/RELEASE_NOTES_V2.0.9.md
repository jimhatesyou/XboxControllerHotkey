# XboxControllerHotkey V2.0.9

## Responsiveness fix
- Removed the Windows Plug and Play / PowerShell transport lookup from the recurring controller-refresh path.
- The home screen no longer displays connection type, so this lookup was unnecessary work.
- Prevents a synchronous PowerShell process (with a timeout of up to six seconds) from blocking the Qt UI during periodic controller scans.
- Controller hotkey polling, connection monitoring, notifications, and battery refresh cadence are otherwise unchanged.

## Follow-up
- If connection-type detection is reintroduced, it must run asynchronously outside the UI thread and publish cached results back to the interface.
