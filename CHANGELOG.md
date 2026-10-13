# Changelog

## 1.0.0-beta.6

- **Side-story walkthroughs in the journal:** every side story's journal entry lists each
  step with town and region: who starts it, who to ask around, who has each item or piece
  of information (and whether to Purchase/Steal or Inquire/Scrutinize), the steps on the way,
  every way to finish it and the reward. Read from the game's event scripts, NPC
  placements, shop and inquire lists. Replaces Side Stories Helper's journal hints (same
  solutions, plus places). `journal_hints` in overhaul.ini; all 101 also in
  docs/SIDE_STORIES.md.
- **Fixed: side stories were counted out of 144 instead of 101.** The game's table has 144
  records, but 32 are blank, 4 are never used and "Kit, the Traveler" is eight records for
  one story. The Wayfarer's Laurel (sold when every side story is done) could never appear,
  and relentless's completion counted side stories as less done than they were.
- **Fixed: 100% completion was out of reach.** Areas are now the world map's 147 real
  locations (was a guessed 190 map pieces, more than exist), and Galdera no longer counts as
  an optional boss (the game ends after that fight, so no save can record it). Every part
  - 32 chapters, 101 side stories, 18 optional bosses, 147 locations - can now reach 100%,
  which takes relentless's world to danger 104.

## 1.0.0-beta.5

- **Fixed: catch-up leveling stalled 5-10 levels below the party.** It made low levels 5x
  cheaper but ramped back to the normal totals just below the party, which charged the saved
  EXP back: those levels cost 2-3x the normal EXP, so a traveler there levelled slower than
  the party. Now every level more than 4 below the party average is 5x cheaper, with no
  payback zone: travelers below that line jump to about 5 levels under the party after their
  next battle and keep pace as the party levels. The party's own levels are unchanged.
- **Catch-up leveling now follows the vanilla start:** off through the chapter 1s (levels
  cost exactly as shipped), phasing in with the rest of the world to full strength (5x) by
  the time the world is fully scaled to your party.

## 1.0.0-beta.4

- **No more PyInstaller exe** (some antivirus tools flagged it as a trojan - a false
  positive caused by the packed-exe format, shared with Python malware). The zip now holds
  the official python.org runtime (`runtime\`, signed by the Python Software Foundation),
  the mod's source as plain files (`app\`) and two double-click scripts: **OrsterraUnbound**
  and **Uninstall-OrsterraUnbound**. Steam's Play button and the desktop shortcut
  run the signed `pythonw.exe` directly.
- **Updating from beta.3 or earlier:** extract over the old folder and double-click OrsterraUnbound
  Orsterra Unbound once; setup comes back to point Steam and the shortcut at the new version.
  Then delete the old `OctopathWorldOverhaul.exe`.
- Uninstall now confirms in a window.

## 1.0.0-beta.3

- **Fixed: Larger Monster Roster's 10-beast limit was reset to 6** by catch-up leveling's
  copy of CharacterGrowData; it is now built on top of whatever copy is installed. The build
  log names other mods that replace the same files.
- Requirements & credits section (README / Nexus page).
- **Toggle dash** option (`toggle_dash`): press dash once to run, again to walk.

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
