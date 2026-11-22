# XboxControllerHotkey V2.0.6

## Fixes
- Match the active SDL controller VID/PID to the corresponding Windows gamepad PnP node before resolving USB, Bluetooth, or Xbox Wireless Adapter transport.
- Include Bluetooth LE device ancestry in the transport resolution path.
- Only display a numeric WinRT battery percentage when the raw Windows Gaming Input controller VID/PID matches the active SDL controller. Unmatched reports are ignored; XInput coarse battery status is used as fallback.
- Right-align the connection value consistently with the other detail values.
- Move the home popover close control farther toward the top-right corner.

The XInput hotkey input path and shortcut handling are unchanged.
