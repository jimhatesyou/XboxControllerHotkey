# XboxControllerHotkey V2.0.21

## Automatic updater reliability

- Hardened the Windows self-update handoff after the verified download completes.
- The updater now waits for the running application to exit before replacing the executable.
- Stages the new executable beside the installed copy and verifies the staged file size.
- Attempts an atomic replacement with a backup, then falls back to a backup-and-rename sequence when atomic replacement is unavailable.
- Restores the previous executable if the fallback replacement fails.
- Removes stale `.new` staging files on failure and records detailed updater activity in the temporary update log.
- Retains the previous executable backup until the updated application is confirmed to have started.

## Included from V2.0.20

- Refined home-screen spacing and configuration button sizing.
- Replaced the capture settings icon with a high-resolution white version.
- Hides the controller activity waveform while disconnected and restores it after reconnection.
