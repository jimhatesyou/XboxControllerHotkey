# XboxControllerHotkey V2.0.4

## UI and branding
- Increased the Powered by JimHub animation display from 48×48 to 56×56.
- Replaced the footer animation asset with the newly supplied GIF, resized to 56×56 while retaining all 80 frames and 50 ms frame timing.
- Moved the home-page close control closer to the top-right corner.
- Applied the bright green `#00D451` directly to the Buy me a coffee hyperlink so the link text is explicitly styled, not dependent on Qt link stylesheet inheritance.

## Connection transport
- No transport-detection algorithm change in this release. The current source intentionally reports `Connection type unavailable` because the existing SDL GUID does not identify the active Windows device instance. A reliable USB/Bluetooth/Xbox Wireless Adapter label requires matching the SDL controller to its exact Windows PnP device path; guessing from model VID/PID previously caused false adapter reports.
