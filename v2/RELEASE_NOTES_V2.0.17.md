# XboxControllerHotkey V2.0.17

## Update Prompt

- Startup update checks run quietly while the application remains in the system tray.
- When an update is available, the prompt appears only after the user opens the main popover view.
- The prompt offers two actions: **Update Now** and **Remind me later**.
- **Do not ask me again** is presented as a footer preference beneath the two actions.
- Choosing **Remind me later** defers the prompt until the next time the popover is opened.
- Choosing **Do not ask me again** suppresses future automatic update prompts. Manual update checks and the About-page update action remain available.

## Update Installation

- Downloads the standalone Windows executable directly from the latest stable GitHub release.
- Verifies the downloaded executable against its published SHA256 checksum before installation.
- Closes the running application, replaces the existing executable, and relaunches the updated version.
