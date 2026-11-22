# XboxControllerHotkey V2.0.1

## Controller selection and connection reporting

- The saved controller preference is now a priority, not a hard lock.
- If the preferred controller is unavailable, the app automatically selects the most recently detected supported controller.
- When the preferred controller reconnects, it regains priority.
- The active connection label is now derived from Windows Plug and Play device enumeration rather than the saved setup preference.
- If Windows does not expose enough information to identify the transport, the app reports that the connection type is unavailable instead of guessing.

## Notes

- Controller model GUIDs are used for preference matching. SDL/Pygame does not expose a universally reliable unique hardware serial for every controller, so two identical controllers may be indistinguishable to this preference mechanism.
- Connection transport reporting is best-effort and depends on the controller/driver's Windows PnP identifiers.
