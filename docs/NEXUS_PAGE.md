# Nexus Mods page (draft)

**Name:** World Overhaul — scaling world, 450-item gear ladder, QoL
**Category:** Gameplay / Overhauls
**Short description (350 chars):** The world, bosses and rewards scale with your story and
party, from chapter 1 to post-game. 450 new multi-stat items with on-hit effects, uncapped
stats (9,999 / 99,999 HP), fast travel to visited places, fewer random encounters, catch-up
leveling. Built from your own game files at launch; saves never modified.

---

## Description (BBCode)

```
[size=5][b]Octopath Traveler — World Overhaul[/b][/size]

Keeps every part of the game a real fight, from the first chapter to the post-game, and gives you a gear ladder to climb past the old caps.

[size=4][b]A world that keeps up[/b][/size]
[list]
[*]The chapter 1s play exactly as vanilla; the scaling builds up through the mid game.
[*]Enemies scale with your story (the game's own recommended levels) and never fall below your party's level — EXP, JP and money scale with them.
[*]Bosses scale from the level they were designed for: a chapter 1 boss you leave for later is still a fight.
[*]Superbosses stay as they are until the world outgrows them.
[*]Provoke/Challenge battles and caits are untouched.
[*]H'aanit's captured beasts and Tressa's Collect keep pace.
[/list]

[size=4][b]450 new items[/b][/size]
[list]
[*]Five tiers sold in Grandport as the world reaches them, and as rare drops (bosses always drop one).
[*]Every item boosts several stats; full descriptions with exact numbers.
[*]Weapon styles with on-hit effects (vulnerability, weakness, slow…), Twinfang double strikes, Gambler's crit-or-miss, Headsman's instant kill, dual-element weapons, Hallowed healer weapons, a physical War Staff for Winnehild's Battle Cry.
[*]Status-immunity talismans, regen pendants, elemental wards, EXP/JP tokens.
[*]Big SP and %HP restoratives; late-game drops (and steals) upgrade to Revitalizing Jam and friends.
[/list]

[size=4][b]Quality of life[/b][/size]
[list]
[*]Fast travel to every location you've visited (unvisited stays locked).
[*]Evasive Maneuvers built in — fewer random encounters, one skill slot freed.
[*]Catch-up leveling for travelers who fall behind.
[*]Stats up to 9,999, HP up to 99,999, damage up to 999,999.
[/list]

Three presets (classic / adaptive / relentless) and every feature can be switched off in overhaul.ini.

[size=4][b]Install[/b][/size]
Extract anywhere, run OctopathWorldOverhaul.exe, let it hook Steam's Play button (or make a desktop shortcut), pick your save, play. The world is rebuilt from your save whenever your progress changes (~15 s).

[size=4][b]Compatibility[/b][/size]
Steam version on Windows. Works with Better Descriptions and Side Stories Helper. Conflicts with other mods that replace EnemyDB, ItemDB, ShopList or EncountVolumeData (this one loads last and wins).

[size=4][b]Notes[/b][/size]
[list]
[*]No game files are included: the mod is built on your PC from your own installation.
[*]Your saves are never modified.
[*]The exe is a packaged Python program; full source on GitHub.
[/list]
```

## Files to upload

`OctopathWorldOverhaul-<version>.zip` from `build_release.ps1`:
`OctopathWorldOverhaul.exe`, `data/item_registry.json`, `README.md`, `LICENSE`, `CHANGELOG.md`.

## Suggested screenshots

The save picker; a Grandport shop list; a tooltip of a tier-90 weapon; a boss with scaled
HP; the world map showing raised danger numbers.
