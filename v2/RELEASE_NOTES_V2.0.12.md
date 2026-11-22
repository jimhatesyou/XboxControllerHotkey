# XboxControllerHotkey V2.0.12 — Complete V1.25-to-V2 Release Notes

V2 is a substantial rewrite of XboxControllerHotkey. It replaces the original V1.25 console-oriented utility with a native Windows desktop companion that lives in the system tray, adds a complete graphical interface and setup experience, and expands controller detection, configuration, status reporting, and update management.

This release preserves the original purpose and default shortcut: hold **Back / View + Start / Menu** together to trigger Windows Xbox Game Bar's **Record That** command.

## The V2 rewrite

- Rebuilt the application around **Python + PySide6**, replacing the original console-first V1 experience with a Windows GUI and system-tray application.
- Added a custom dark-themed interface with a compact controller status popover, dedicated About and FAQ pages, custom artwork, rounded surfaces, and branded UI elements.
- Added first-launch information explaining what the app does, what Xbox Game Bar must provide, and how to configure Windows capture settings.
- Added first-run controller setup, including connection preference selection and automatic detection when the user is unsure.
- Added a tray-resident workflow so the utility can run quietly while a game remains in the foreground.

## Controller detection and status

- Added supported game-controller detection using SDL/Pygame's GameController layer, filtering out unrelated generic joystick/HID devices.
- Preserved a preferred controller selection while allowing automatic failover to another recently detected supported controller; the preferred controller regains priority when it reconnects.
- Added a controller selection screen and quick access to Xbox Accessories.
- Added controller connection and disconnection monitoring with notifications.
- Added a custom tray icon that shows a green connected state and a red disconnected/no-supported-controller state.
- Added controller identity and battery information to the status UI.
- Added battery reporting that uses a matching Windows Gaming Input battery report for a percentage when reliably associated with the active controller, with XInput battery status as a fallback.
- Added Windows Plug and Play device ancestry matching to distinguish USB, Bluetooth, and Xbox Wireless Adapter connections where the active device can be identified. The app avoids guessing when Windows does not provide reliable matching information.

## Record That shortcut configuration

- Preserved the V1.25 **Back / View + Start / Menu** shortcut as the default.
- Added a graphical shortcut editor that lets users assign controller controls individually.
- Added live shortcut preview, duplicate-control validation, save behavior, and a **Revert to default** option.
- Added warnings that custom combinations can conflict with gameplay or trigger unintentionally.
- Kept the Record That action as a keyboard shortcut sent to Windows Xbox Game Bar; the app does not record, encode, or store clips itself.

## Windows integration and convenience

- Added quick links to Windows Xbox Game Bar capture settings and Xbox Accessories.
- Added an optional **Start with Windows** setting through the tray menu.
- Added single-instance protection so launching the EXE a second time does not create another tray process.
- Added a standalone, one-file portable Windows executable; no installer, Python installation, or administrator privileges are required for normal use.

## Automatic updates

- Added a silent startup check for the latest stable GitHub Release, with an optional update prompt when a newer version is available.
- Added choices to update immediately, be reminded at the next launch, or disable automatic startup update prompts.
- Retained a manual **Check for updates** action in About.
- Added background downloading of the portable EXE and its SHA-256 checksum, checksum verification before installation, and a helper process to replace the running executable safely after the app exits.

## Responsiveness and reliability improvements

- Added a dedicated XInput polling worker for responsive controller shortcut detection while games retain foreground focus.
- Moved routine SDL/Pygame controller enumeration to a background worker, with overlap prevention and shared-state locking so scans do not block the Qt interface or race fallback input reads.
- Changed the controller-selection page to use cached scan results rather than starting its own synchronous enumeration.
- Removed a blocking PowerShell transport lookup from the recurring UI refresh path after connection type was removed from the home status panel.
- Added bounded background update checks and background update downloads so network activity does not freeze the interface.
- Corrected Qt timer and worker ownership after introducing background controller scanning.
- Added a named Windows mutex for single-instance behavior; Windows releases it automatically when the process exits or crashes.
- Refined controller matching and battery association to avoid reporting data from a different connected device.

## UI, branding, and usability refinements

- Added About details, creator credit, update status, manual update controls, FAQs, GitHub project/release links, and the first-launch notice.
- Added custom controller artwork, tray status overlays, setup backgrounds, and the JimHub branding animation.
- Refined the home status panel to focus on the active controller, battery, and Record That shortcut.
- Added dark-theme scrollbar styling, consistent alignment, rounded visual elements, and the green accent color used by the interface.
- Refined notification timing and presentation, and corrected navigation, button, and About-page details.
- Updated the About-page creator link to James Cavanaugh's Linktree and removed the visible @handle from the creator credit.

## Build, distribution, and source

- Added a repeatable Windows build using PyInstaller to produce the portable XboxControllerHotkey.exe.
- Added a GitHub Actions workflow to build the executable, generate a SHA-256 checksum, and publish both as GitHub Release assets.
- Added the V2 source, assets, requirements, build scripts, and versioned release notes under the v2/ directory.
- Preserved the original V1 source files and repository history rather than overwriting the V1.25 implementation.

## V2.0.12 finalization

- Set the About-page creator credit to a clickable James Cavanaugh link and removed the visible @jimhatesyou handle.
- Reviewed the V2.0.11 baseline for responsiveness, threading, update safety, and avoidable work; retained the known-good runtime behavior rather than making a broad unneeded refactor.
- Synchronized the release workflow's tag default and release-notes path with V2.0.12.

## Requirements and important behavior

- Windows 10 or Windows 11, 64-bit.
- A supported controller and compatible Windows/SDL driver.
- Xbox Game Bar must be installed, enabled, and configured for **Record That**.
- XboxControllerHotkey sends the configured keyboard shortcut to Game Bar. Capture duration, audio, video quality, and save location remain controlled by Windows.

## Known limitations

- Controller detection, button mapping, connection details, and battery reporting vary by controller, driver, and connection method.
- Numeric battery percentage is shown only when Windows provides a battery report that can be reliably matched to the active controller; otherwise the app falls back to XInput's coarse battery state or reports battery information as unavailable.
- Connection type is best-effort and is not guessed when the active Windows device cannot be reliably identified.
- Keep the portable EXE in a permanent, user-writable folder. If you enable startup launch or self-updates, moving the EXE can break the saved startup path or prevent the updater from replacing it.

**V1.25 to V2.0.12:** the original controller-to-Record-That shortcut remains, but the surrounding application has been rebuilt into a configurable, tray-based Windows utility with a graphical setup flow, controller status UI, notifications, update management, and a repeatable portable release pipeline.
