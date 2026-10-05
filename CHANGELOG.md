# Changelog

## 1.0.0-beta.2 — Orsterra Unbound

- New name: **Orsterra Unbound**.
- **Relentless grows with completion**: danger = 104 x a weighted share of main chapters
  (50%), side stories (20%), optional bosses fought (20%) and areas explored (10%); the main
  story alone ends near the game's own 50. Danger earned this way pays full EXP.
- **Galdera** is pinned at danger 104 on relentless and drops the **Unbound Crown** (+3000
  to every stat). The eight revived bosses of the Gate of Finis fight at danger 94 or the
  world's, whichever is higher.
- **Mythic tier** (danger 104) joins the ladder; Grandport stocks the two newest open tiers.
- **Wayfarer's Laurel**, sold once every side story is done; **Fortune's Purse** (x3 JP and
  money). Battle money now follows the equipment JP bonus (1-byte patch), and that bonus
  takes the best item worn instead of adding up (4-byte patch).
- **"The World Stirs"**: while you play, a banner says when your progress would grow the
  world at the next launch (`world_notice`).
- **Fixed: the launcher could vanish mid-build** after you picked a save (a Python/Tk
  crash when the save picker's leftovers were cleaned up from the build thread). Hard
  crashes now also leave a trace in logs/launcher.log.
- **Chapters are counted correctly.** The save's MainProgressPoint weighs chapters 1/2/3/4
  as 1/4/8/16 points; it was read as 8 per chapter, so the story looked far less advanced
  than it was in the early and mid game (all chapter 2s done read as 5 chapters, not 16).
  Chapters now come from each traveler's own mission counter.
- **Leveling no longer runs away.** Enemies keep up with an out-levelled party, but their
  EXP and JP now follow only half of that lead (money still pays in full). Before, a party
  gained a level every ~6 fights however far ahead of the story it was; now being 20
  levels ahead takes about twice as long, as in vanilla. `reward_share` in overhaul.ini.
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
