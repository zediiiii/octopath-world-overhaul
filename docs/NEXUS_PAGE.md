# Nexus Mods page

**Name:** Orsterra Unbound - World Overhaul
**Category:** Overhauls
**Version:** 1.0.0-beta.10
**Short description (350 chars max):** Vanilla chapter 1s, then a world that keeps up: enemies
and bosses scale with your story and party, 560+ new multi-stat items up to level 104, stats past
999, elemental boosts that work on accessories, fast travel to visited places, half the random
encounters, catch-up leveling. Built from your own files; saves never modified.

**Images** (docs/images, 1920x1080): banner.png (main), features.png, curve.png, gear.png,
picker.png.

**Files:** `OrsterraUnbound-<version>.zip` from `python dev/package_release.py` (main file).

**Requirements:** none (Steam version, Windows 10/11; Python not needed - bundled). **Permissions:** MIT (see LICENSE).

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

[size=5][b]560+ new items[/b][/size]
[list]
[*]Six tiers — Tempered, Runeforged, Astral, Sovereign, Eternal and Mythic (levels 60–104) — sold in Grandport as the world reaches them, and as rare drops (every boss drops one).
[*]Every piece boosts several stats, and the description lists every number and how it stacks.
[*]Weapon styles with on-hit effects, Twinfang double strikes, Gambler's crit-or-miss, Headsman's instant kills, dual-element weapons, Hallowed healer staves, a physical War Staff, status-immunity talismans, regen pendants, elemental wards, sigils and hearts.
[*]Big SP and %HP restoratives, and XL Soulstones from world level 70.
[*][b]Loot keeps pace with the world:[/b] enemy drops and steals climb a rung at world danger 35, 50, 65 and 80 — grapes become Grape (M), Vital Draught, Refreshing Jam, then Revitalizing Jam; plums, olives and pomegranates climb the same way; soulstones reach (XL), olives reach (XL), nuts reach (XL) from world 80 (never sold).
[*][b]Treasure chests keep pace too[/b] — every chest: consumables climb the same ladder (jams, Olive of Life (L) and status cures come in bigger stacks), gear becomes the most similar tier piece of the same type, and money pays up to ×6 at world 72.
[*][b]Side stories pay more[/b]: every reward is kept, the money scales, and the free reward slots get world-level counterparts of what the story gives — bigger for later-chapter stories.
[*][b]Fixed-number skills grow[/b]: Alfyn's concoctions, Rest and hired helpers' heals grow with your party's HP, keeping their vanilla feel.
[*][b]Runes for the whole party[/b]: the Runelord's six elemental runes enchant every ally's weapons (Transfer Rune unchanged).
[*]Gear you already own is never changed. New gear sells back for half its price, so you can try it on.
[*][b]Fortune's Purse[/b]: triple JP and battle money (the best JP/money item worn counts; they don't stack).
[*][b]Wayfarer's Laurel[/b]: appears in Grandport once you've finished all 101 side stories — +1,500 to every stat, regeneration, more EXP, JP and money.
[*][b]Unbound Crown[/b]: +3,000 to every stat, dropped by Galdera.
[/list]

[size=5][b]Beyond every cap[/b][/size]
[list]
[*]Stats up to 9,999, HP up to 99,999, damage up to 999,999.
[*][b]Elemental damage boosts on armour and accessories actually work.[/b] The game only counted them on weapons; a 4-byte patch to its battle code makes it count every equipped piece. Boosts of one element add up across your gear and multiply with your skills.
[/list]

[size=5][b]Quality of life[/b][/size]
[list]
[*][b]Side-story walkthroughs in the journal[/b]: every side story's journal entry lists each step with the town and region — who starts it, who to ask around, who to Purchase/Steal an item from or Inquire/Scrutinize for information, every way to finish it, and the reward. Read from the game's own event, NPC and shop data; pairs with fast travel.
[*][b]Side stories you haven't started are marked[/b]: the quest-giver's name gets a leaf ("Ali ⑳") and so does the place on the world map ("Grandport ⑳3" = three begin there). Updated every launch; on automatically once every chapter 3 is done, or switch it with the checkbox in the save picker.
[*]Fast travel to every location you've visited (unvisited places stay locked).
[*]Evasive Maneuvers built in — half the random encounters, one support-skill slot freed.
[*][b]Toggle dash[/b] (optional, toggle_dash = true): press dash once to run, again to walk. A small patch to the game's own controller — no script loader needed.
[*]Catch-up leveling: off in the vanilla opening, then phasing in with the rest of the world, up to 5× cheaper EXP for every level more than 2 below your highest active traveler — benched or lagging travelers shoot up to about 3 levels under your leaders and keep pace from there. Optional catch_up = save tops up their EXP instead, so they truly catch up.
[/list]

[size=5][b]Presets[/b][/size]
[list]
[*][b]classic[/b] — the story's own curve, plus the gear, caps and quality of life.
[*][b]adaptive[/b] (default) — a little above the story, and never below your party.
[*][b]relentless[/b] — adaptive, then a step harder from the chapter 4s: enemies above your level, bosses ×2 HP, superbosses ×4. The world keeps growing with everything you complete — main story, side stories, optional bosses and exploration — up to danger 104. The Gate of Finis bosses fight at 94 or more, and Galdera waits at 104.
[/list]
Every feature can be switched off in overhaul.ini.

[size=5][b]Install[/b][/size]
[list=1]
[*]Right-click the zip, choose Extract All (for example to Documents\OrsterraUnbound). Keep the files together.
[*]Double-click [b]OrsterraUnbound[/b]. Setup offers to hook Steam's Play button and Big Picture (Steam restarts once) and to add a desktop shortcut.
[*]Pick the save you're about to play — or New game — and load that same save in the game.
[/list]
From then on, just press Play. The world is rebuilt from your save whenever your story, party or settings change (about 15 seconds). If anything goes wrong, you get a message and the game still starts.

[b]Updating from beta.3 or earlier:[/b] extract over the old folder and double-click OrsterraUnbound once, so setup points Steam's Play button at the new version; then delete the old OctopathWorldOverhaul.exe.
[b]Uninstall:[/b] double-click Uninstall-OrsterraUnbound, then delete the folder.

[size=5][b]Requirements & credits[/b][/size]
[b]Requirements: none.[/b] Everything is built from your own game install; no other mod is needed, and Python does not need to be installed (the download carries its own copy of the official python.org runtime). Windows 10 or 11, Steam version.

Thanks to these mods — Orsterra Unbound is built to work alongside them:
[list]
[*][url=https://www.nexusmods.com/octopathtraveler/mods/16]Better Descriptions[/url] — the new items' descriptions follow its wording conventions, and its text is kept: new item text is added on top of it.
[*][url=https://www.nexusmods.com/octopathtraveler/mods/21]Side Stories Helper[/url] — its text is kept the same way; its side-story journal hints are replaced by the full walkthroughs, which cover the same solutions plus where everyone is.
[*][url=https://www.nexusmods.com/octopathtraveler/mods/22]Larger Monster Roster[/url] — H'aanit's larger capture roster is kept: catch-up leveling is built on top of its table.
[*][url=https://www.nexusmods.com/octopathtraveler/mods/41]Long Distance Banter[/url] and [url=https://www.nexusmods.com/octopathtraveler/mods/58]Our Purple Chests[/url] — tested together, no overlap.
[/list]

[size=5][b]Compatibility[/b][/size]
Steam version on Windows (not Game Pass, not Steam Deck/Linux). Other text mods keep their text too. Conflicts with mods that replace EnemyDB, ItemDB, ShopList, EncountVolumeData, BattlePlayerBP, BattleManagerBP or (with toggle dash) ActionController_Impl — this one loads last and wins. New item text is English in every language.

[size=5][b]Good to know[/b][/size]
[list]
[*][b]Play in borderless fullscreen.[/b] The launcher shows a banner while you play when your progress would grow the world; in exclusive fullscreen nothing can appear over the game, so you'd only see it after Alt-Tab. Borderless also avoids a display crash on some streaming / virtual-display setups.
[*][b]Source code:[/b] [url=https://github.com/zediiiii/octopath-world-overhaul]github.com/zediiiii/octopath-world-overhaul[/url] (MIT licence).
[*]No game files are included: the mod is built on your PC from your own installation.
[*]Your saves are only read, never written — unless you turn on the optional catch_up = save, which raises lagging travelers' EXP (backed up first; nothing else changes).
[*]No exe of its own: the only programs in the zip are the official python.org runtime, digitally signed by the Python Software Foundation. The mod is plain-text Python source in the app folder (read every line), and OrsterraUnbound is a two-line script. Windows may ask "Do you want to run this file?" the first time: click Run.
[*]The fifth support-skill slot isn't possible: the slot count lives in the game's code.
[/list]
```
