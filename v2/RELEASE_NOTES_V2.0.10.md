# V2.0.10 — UI responsiveness and background controller scans

- Moved routine SDL/Pygame controller enumeration off the Qt UI thread into a dedicated worker.
- Prevented overlapping scans; the monitor skips a timer tick while a previous scan is still running.
- Added a shared controller-state lock so fallback SDL input reads do not race device-list updates.
- The controller-selection page now renders cached scan results instead of performing its own synchronous device enumeration.
- Controller scanning runs every 2.5 seconds in the background; the tray UI remains responsive while scans complete.
- XInput hotkey polling remains on its dedicated high-priority worker and is not changed.
