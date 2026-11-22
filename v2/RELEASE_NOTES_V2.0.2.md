# XboxControllerHotkey 2.0.2

## Connection display correction
- The home screen now displays the active controller's reported connection type rather than the setup preference.
- Removed the unreliable registry-wide VID/PID lookup that could match a separate Xbox Wireless Adapter and mislabel a USB-connected controller.
- When Windows/SDL cannot associate transport information with the exact active controller instance, the app displays `Connection type unavailable` instead of guessing.
- Controller selection, preferred-device priority, and automatic failover behavior are otherwise unchanged.
