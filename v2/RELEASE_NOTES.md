## TL;DR — What’s new since v2.0.23

- **Cleaner interface:** Refined home-screen spacing, action-button sizing and alignment, title/version placement, About-page typography, and the About information icon.
- **Better update experience:** Added download progress and a three-second relaunch countdown.
- **More reliable updates:** Improved executable replacement, rollback handling, and updater relaunch detection.
- **Fixed controller battery reporting:** Preserve the last battery reading across background controller scans instead of resetting it to “Battery pending.” Refresh battery status every 60 seconds, with an immediate refresh after connection.
- **Fixed the duplicate-instance popup:** Corrected startup verification for PyInstaller’s bootloader and application child process. The v2.0.32 → v2.0.33 in-app update was confirmed to complete without the extra popup.

This release consolidates the improvements originally shipped across v2.0.24–v2.0.31. Versions v2.0.32 and v2.0.33 were used to validate the updater fix.
