# Changelog

## 1.0.0-beta.10

- **Wayfarer's Laurel pays x10 JP and money** (was x3, the same as Fortune's Purse). Only the
  best JP / money item counts (Laurels don't stack with each other or the Purse).
- **Hard areas top out at danger 108** (world + 12, at most 108; Galdera stays at 104).
- **Hard areas are as tough as they say (relentless):** the danger shown for optional
  areas (world + 12) was only a label - their bosses were built for the world's danger.
  Now the shrine bosses, the beasts (Everhold's Managarmr, the caves, the Hollow Throne's
  Throne Guardian) and the 10 regular enemies found only in those areas are built for it.
- **EXP gear says it stacks** (read from the battle code: every EXP piece the party wears
  adds up, plus the best EXP support skill); JP / money still take the best item.
- **Side stories you haven't started are marked in the game:** the person who starts one is
  named with the leaf ("Ali ⑳"), only on the placement that starts it, and the world map
  adds the leaf to the place's name ("Grandport ⑳3": three begin there). Rebuilt from the
  save at each launch, so a marker goes once its story begins. Automatic once 24 chapters
  (every chapter 3) are done, so the opening isn't covered in leaves; the save picker has a
  checkbox to turn it on or off (`side_story_markers = auto | on | off`,
  `side_story_markers_from`). Givers who only appear after a later chapter count too.
- **The world peaks before the Gate of Finis.** Nothing inside it counts toward completion
  any more: not its eight rematches, not the Gate itself, and not At Journey's End (which
  only finishes after Galdera). Everything else - 32 chapters, 100 side stories, 10
  optional bosses, 146 places - takes relentless to danger 104, so Grandport sells the
  Mythic tier and Wayfarer's Laurel appears before you go in.
- **A save point in the Gate of Finis** (the game has none in there): in the first hall,
  beside the party monument. `gate_save_point`.

## 1.0.0-beta.9

- **Catch-up reaches your leaders:** the catch-up line is now your highest active
  traveler's level - 2 (was the party average - 4). A cheaper table only affects levels a
  traveler hasn't reached, so the leaders are never moved; everyone below climbs to about 3
  levels under them. Before, a traveler 5-10 levels behind hit one level that charged the
  whole EXP shortfall (e.g. 230,000+ EXP for a single level).
- **Optional real catch-up (`catch_up = save`):** before the game starts, anyone more than 5
  levels behind your highest active traveler gets their EXP raised to that level's normal
  total, and the game hands out the levels after their next battle - no shortfall left.
  Writes the save (backed up first, only EXP changes). Off by default (`catch_up = table`).

## 1.0.0-beta.8

- **Runes for the whole party:** the Runelord's six elemental runes (all four levels) now
  enchant every ally's weapons; Transfer Rune unchanged. `party_runes`.
  Their descriptions say so and state the damage: the equipped weapon's Elem. Atk. x 8.
- **XL Soulstones** deal 12,000 or half a regular foe's HP at the world's danger, whichever is
  more (12,000 at 70-81, 14,000 at 90, 18,000 at 104) - the vanilla (L) stone's 40-70%.
- **Olive of Life (XL):** revives with full HP; from world 75, top of the revive ladder.
- **Fixed-number heals follow party HP** instead of world / 35, keeping their vanilla
  feel (Restore Health ~69% of a bar at every level; Incredible Heal a full heal); SP
  restores grow 40% as fast.
- **Money follows gear prices from world 60** (a chest ~30-44% of a tier piece; was 20% at
  104). Balance numbers: `python dev/loot_balance.py`.

## 1.0.0-beta.7

- **Treasure chests keep pace with the world** (all 734, for any save): consumables climb the
  loot ladder; top items (jams, Olive of Life (L), status cures) come in bigger stacks (x2
  from world 50, x3 from 80); gear becomes the most similar open-tier piece of the same type
  (stats and status immunities matched; money when nothing matches); money and sell-only
  treasures pay x(world / 12).
- **Side stories pay more:** existing rewards kept, money scaled the same way, and the free
  reward slots get world-level counterparts of the story's rewards (tier gear, better nuts,
  laddered stacks), scaled by the story's original chapter.
- **XL nuts** (5x the (L) nut) from world 80 - chests, side stories and drops only.
- **Fixed-number skills grow:** party skills that restore a fixed HP / SP amount (Alfyn's
  concoctions, Rest, hired helpers) restore x(world / 35) from world 35. `scale_skills`.
- New module rewards.py (drops, chests, side stories share one set of rules).

## 1.0.0-beta.6

- **Loot keeps pace with the world:** consumable drops and steals climb a ladder one rung at
  world danger 35, 50, 65 and 80 (grapes -> Grape (M) -> Vital Draught -> Refreshing Jam ->
  Revitalizing Jam; plums, olives, pomegranates likewise), replacing the single jump at 68.
- **XL Soulstones** (six elements, 9,000 damage to all foes), sold and dropped from world
  level 70.
- Python is bundled - stated as a non-requirement.
- **No archive inside the download:** the bundled Python standard library ships as plain
  files (runtime\Lib) instead of a zip within the zip, which Nexus treats as a nested
  archive and quarantines.
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
