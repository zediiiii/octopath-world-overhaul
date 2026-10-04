# Changelog

## Unreleased

- Every preset now plays the chapter 1s as vanilla (no extra enemy or boss HP, vanilla enemy
  levels) and builds up to full strength through the mid game. `relentless` is `adaptive`
  until the chapter 4s, then steps up (story +5, party +4, bosses ×2, superbosses ×4)
  instead of the old 8 + 3 per chapter curve that punished the mid game.
  `vanilla_start = false` restores full strength from the start.
- The save picker shows each save's danger for the configured preset (it used the defaults).

## 1.0.0-beta.1

First public build.

- World scaling keyed to the story's own chapter recommendations and the party's level,
  with `classic` / `adaptive` / `relentless` presets and per-feature switches
  (`overhaul.ini`).
- Bosses scale from their native danger; superbosses only once the world passes them.
- 450-item gear ladder (tiers 60–99), Grandport shop, rare drops, exact descriptions in
  every game language (English text).
- Fast travel to visited locations, built-in Evasive Maneuvers, catch-up leveling, raised
  stat / HP / damage caps, H'aanit summon and Tressa Collect scaling, late-game consumable
  drops.
- Launcher: save picker for shared PCs, Steam Play button / Big Picture hook, desktop
  shortcut, self-validating builds, uninstall.
