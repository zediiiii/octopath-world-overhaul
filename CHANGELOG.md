# Changelog

## 1.0.0-beta.2 — Orsterra Unbound

- New name: **Orsterra Unbound**.
- Launcher: **New game** in the save picker (and automatically when there are no saves),
  so a fresh start gets a fresh world. If anything goes wrong before the game starts, you
  get a message saying why and the game still starts. `overhaul.ini` saved by Notepad with a
  byte-order mark is read correctly; mistyped values name the setting. A failed install
  leaves no stray files.
- Every preset now plays the chapter 1s as vanilla (no extra enemy or boss HP, vanilla enemy
  levels) and builds up to full strength through the mid game. `relentless` is `adaptive`
  until the chapter 4s, then steps up (story +5, party +4, bosses ×2, superbosses ×4)
  instead of the old 8 + 3 per chapter curve that punished the mid game.
  `vanilla_start = false` restores full strength from the start.
- Elemental damage boosts on armour and accessories (Sigils, Hearts) now work: the game
  only counted weapons; a 4-byte blueprint patch counts every equipped piece. Descriptions
  say how each boost stacks.
- New equipment sells back for 50% of its price (was 10%); the new consumables stay at 10%.
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
