# Nexus Mods page

**Name:** Orsterra Unbound - World Overhaul
**Category:** Overhauls
**Version:** 1.0.0-beta.2
**Short description (350 chars max):** Vanilla chapter 1s, then a world that keeps up: enemies
and bosses scale with your story and party, 450 new multi-stat items to level 99, stats past
999, elemental boosts that work on accessories, fast travel to visited places, half the random
encounters, catch-up leveling. Built from your own files; saves never modified.

**Images** (docs/images, 1920x1080): banner.png (main), features.png, curve.png, gear.png,
picker.png.

**Files:** `OrsterraUnbound-<version>.zip` from `build_release.ps1` (main file).

**Requirements:** none (Steam version, Windows). **Permissions:** MIT (see LICENSE).

---

## Description (BBCode)

```
[center][size=6][b]Orsterra Unbound[/b][/size]
[size=4][i]a world overhaul for Octopath Traveler[/i][/size][/center]

The whole journey stays a real fight — from the first chapter to the last boss beyond the gate. The opening plays exactly like the game you know; from the mid game on, the world keeps up with your story and your party, and a new gear ladder carries you past the old caps.

[size=5][b]A world that keeps up[/b][/size]
[list]
[*][b]The chapter 1s play exactly as vanilla.[/b] The challenge builds up through the chapter 2s and 3s.
[*]Enemies follow your story (the game's own recommended levels) and never fall below your party's level — EXP, JP and money scale with them.
[*]Bosses scale from the level they were built for, so a chapter 1 boss you leave for later is still a fight. Superbosses wait until you outgrow them.
[*]Provoke / Challenge fights and caits are untouched. H'aanit's captured beasts and Tressa's Collect keep pace.
[/list]

[size=5][b]450 new items[/b][/size]
[list]
[*]Five tiers — Tempered, Runeforged, Astral, Sovereign, Eternal (levels 60–99) — sold in Grandport as the world reaches them, and as rare drops (every boss drops one).
[*]Every piece boosts several stats, and the description lists every number and how it stacks.
[*]Weapon styles with on-hit effects, Twinfang double strikes, Gambler's crit-or-miss, Headsman's instant kills, dual-element weapons, Hallowed healer staves, a physical War Staff, status-immunity talismans, regen pendants, elemental wards, sigils and hearts.
[*]Big SP and %HP restoratives; late in the game ordinary drops and steals become Revitalizing Jam and friends.
[*]Gear you already own is never changed. New gear sells back for half its price, so you can try it on.
[/list]

[size=5][b]Beyond every cap[/b][/size]
[list]
[*]Stats up to 9,999, HP up to 99,999, damage up to 999,999.
[*][b]Elemental damage boosts on armour and accessories actually work.[/b] The game only counted them on weapons; a 4-byte patch to its battle code makes it count every equipped piece. Boosts of one element add up across your gear and multiply with your skills.
[/list]

[size=5][b]Quality of life[/b][/size]
[list]
[*]Fast travel to every location you've visited (unvisited places stay locked).
[*]Evasive Maneuvers built in — half the random encounters, one support-skill slot freed.
[*]Catch-up leveling: travelers who fell behind level up to 5× faster.
[/list]

[size=5][b]Presets[/b][/size]
[list]
[*][b]classic[/b] — the story's own curve, plus the gear, caps and quality of life.
[*][b]adaptive[/b] (default) — a little above the story, and never below your party.
[*][b]relentless[/b] — adaptive, then a step harder from the chapter 4s: enemies above your level, bosses ×2 HP, superbosses ×4.
[/list]
Every feature can be switched off in overhaul.ini.

[size=5][b]Install[/b][/size]
[list=1]
[*]Extract the zip anywhere (for example Documents\OrsterraUnbound). Keep the files together.
[*]Run OctopathWorldOverhaul.exe. Setup offers to hook Steam's Play button and Big Picture (Steam restarts once) and to add a desktop shortcut.
[*]Pick the save you're about to play — or New game — and load that same save in the game.
[/list]
From then on, just press Play. The world is rebuilt from your save whenever your story, party or settings change (about 15 seconds). If anything goes wrong, you get a message and the game still starts.

[b]Uninstall:[/b] run OctopathWorldOverhaul.exe --uninstall, then delete the folder.

[size=5][b]Compatibility[/b][/size]
Steam version on Windows (not Game Pass, not Steam Deck/Linux). Works with Better Descriptions, Side Stories Helper and other text mods (their text is kept). Conflicts with mods that replace EnemyDB, ItemDB, ShopList, EncountVolumeData or BattlePlayerBP — this one loads last and wins. New item text is English in every language.

[size=5][b]Good to know[/b][/size]
[list]
[*]No game files are included: the mod is built on your PC from your own installation.
[*]Your saves are only read, never written.
[*]The exe is a packaged Python program (PyInstaller); some antivirus tools flag those by habit.
[*]The fifth support-skill slot isn't possible: the slot count lives in the game's code.
[/list]
```
