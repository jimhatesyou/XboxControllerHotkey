# XboxControllerHotkey V2.0.20

## Main popover redesign
- Standardized the popover at one fixed size across Home, About, controller configuration, shortcut configuration, and FAQs.
- FAQs retain an internal vertical scrollbar; the other views do not scroll.
- Reorganized Battery and Record That shortcut into two equal dark information cards.
- Added three evenly spaced green configuration buttons using the supplied ABXY, Xbox, and capture-settings icons.
- Added a green-outlined Clips Captured control beside About. Clicking it opens the user's configured Windows Gaming Captures folder.

## Clip counter
- Added a persistent lifetime count for clips attributed to Record That triggers sent by XboxControllerHotkey.
- The app watches the configured Captures folder for a newly created video file after a hotkey trigger and counts it after the file size stabilizes.
- Existing clips are not retroactively counted because their origin cannot be reliably identified.

## Live input waveform
- Added a transparent, continuously scrolling Xbox-green waveform driven by controller button, trigger, and thumbstick activity.
- New input activity enters from the right and moves left.
- The zero baseline rests 20 pixels above the popover's bottom edge.
- Added a green translucent shadow beneath the line only, locally varying from 10% opacity at idle to 40% at maximum activity and fading out toward the bottom. No grid or backing panel is drawn.

## About and updates
- When an update is available, the Check for updates button is replaced by Update Now.
- If the user closes the app without updating, the next launch checks GitHub releases again.
- Kept the existing five-second dismissible controller notifications and About-screen footer styling.


## Home screen refinements
- Corrected the three configuration buttons so their icons and two-line labels remain fully visible.
- Tightened the vertical layout and reduced excess spacing while preserving the controller status, clip counter, footer, and activity graph.
- Replaced the capture settings bitmap with a clean white vector icon traced from the supplied reference image.
