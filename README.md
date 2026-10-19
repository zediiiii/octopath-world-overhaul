# Orsterra Unbound
### a world overhaul for Octopath Traveler

![Orsterra Unbound](docs/images/banner.png)

A difficulty, progression and gear overhaul for **Octopath Traveler (Steam, PC)** that keeps
the whole game interesting from the first chapter to the post-game. The world scales to how
far your story is and how strong your party is, bosses keep up when you out-level them, and
a new 450-item gear ladder carries you to level 99 and beyond the old 999 stat cap.

The mod is built **on your PC, from your own game files and your own save**, every time you
launch. No game data is redistributed, and your saves are never modified (unless you turn
on the optional `catch_up = save`, which only raises EXP, after a backup).

---

![What changes](docs/images/features.png)

## Install

1. Download the latest release, right-click the zip and choose **Extract All** (for example
   to `Documents\OrsterraUnbound`). Keep the files together.
2. Double-click **`OrsterraUnbound`** in the extracted folder. On first run a small
   setup window offers to:
   - make **Steam's Play button and Big Picture** run the overhaul first (Steam restarts once)
   - add a **desktop shortcut**
3. Pick the save you are going to play in the list that appears, and the game starts. Load
   **that same save** in the game.

That's it. From then on, launch the game the way you chose in setup; the world is rebuilt
automatically whenever your story, party level or settings change (about 15 seconds),
otherwise the game starts immediately.

**Requirements:** Windows, the Steam version of Octopath Traveler. Works alongside
*Better Descriptions*, *Side Stories Helper* and other text mods (their text is kept).

![The launcher](docs/images/picker.png)

### Uninstall

Double-click **`Uninstall-OrsterraUnbound`** (removes the mod file and the Steam hook), then
delete the folder and the desktop shortcut. Your saves were never touched.

### Updating

Extract the new zip over the old folder. Coming from beta.3 or earlier, double-click
**`OrsterraUnbound`** once: the setup window comes back to point Steam's Play button and
the shortcut at the new version. You can then delete the old `OctopathWorldOverhaul.exe`.

---

## What it changes

### A world that keeps up
- **Enemies scale** to your progress. The baseline is the game's own recommended level for
  the chapters you're on, plus a small margin; if your party is stronger than that, the
  world matches your party instead. Areas you've outgrown are raised so backtracking still
  matters, and **EXP, JP and money scale with them**.
- **Bosses scale from the danger they were designed for.** A chapter 1 boss you tackle late
  in the game is a real fight; fought on time it's only a little tougher than vanilla.
  Superbosses only scale once the world passes them.
- **Never touched:** Provoke / Challenge NPC battles, caits (cait farming still works), and
  anything else that isn't a random encounter or a boss.
- **Area danger numbers** on the map follow the world.
- **H'aanit's captured beasts** get stronger along with the world, and **Tressa's Collect**
  talent finds bigger purses.

### A new gear ladder (from danger 55)
- **450 new items in five tiers** (Tempered, Runeforged, Astral, Sovereign, Eternal) sold in
  **Grandport** as the world reaches each tier, and as rare drops (bosses always drop one).
- Every piece boosts **several stats**, with accuracy on every weapon and SP on armour.
- **Weapon styles with on-hit effects**: Keen, Swift, Arcane, Brutal, Sage, Quicksilver,
  Battle, Ruinous — target takes +50% damage, deals −33% damage, loses speed, and more, at
  chances up to 50%. Plus **Twinfang** (every attack hits twice), **Gambler's** (crit or
  miss), **Headsman's** (instant kill), **Sundering**, **Hexing** status weapons, single and
  dual **elemental** weapons, **Hallowed** healer weapons (Elemental Defense = healing power)
  and the **War Staff** (a physical staff for Winnehild's Battle Cry).
- **Armour** in Heavy / Warded / Nimble variants, **Clearmind** and **Purity** immunity
  pieces, **Berserker Mail**.
- **Accessories**: stat charms, SP / HP regeneration pendants, EXP / JP tokens, status
  **talismans** (up to full immunity), elemental **wards**, **sigils** and **hearts**,
  Hunter's Lure.
- **Full descriptions** — every stat and effect is listed with its exact number, and how it
  stacks.
- **Elemental damage boosts work on armour and accessories.** The game only counted them on
  weapons; a 4-byte patch to its battle blueprint makes it count every equipped piece.
  Boosts of one element add up across all your gear (+30% staff + 20% sigil = +50%), and
  the total multiplies with support skills and buffs. Physical damage boosts add up across
  equipped weapons; elemental resistances add up across all gear, down to full immunity
  (as in vanilla).
- New consumables: **Invigorating Draught / Cask** (500 / 300 SP), **Vital Draught /
  Cask** (50% / 35% max HP), **XL Soulstones** (elemental damage to all foes: 12,000, or
  half a regular foe's HP once that is more - 14,000 at 90, 18,000 at 104; from world 70)
  and **Olive of Life (XL)** (revives with full HP; from world 75).
- **Loot keeps pace with the world:** enemy drops and Therion's steals climb their ladder one
  rung at world danger 35, 50, 65 and 80 - grapes -> Grape (M) -> Vital Draught ->
  Refreshing Jam -> Revitalizing Jam, plums the same way, olives to Olive of Life (L),
  pomegranates to the jam, soulstones (M) -> (L) -> (XL), nuts up to **(XL)** (5x the (L)
  nut, from world 80, never sold).
- **Treasure chests keep pace too** - all of them, in a new game as in an old one: their
  consumables climb the same ladder (items already at the top - jams, Olive of Life (L),
  status cures - come in bigger stacks: x2 from world 50, x3 from 80), gear becomes the
  most similar tier piece of the same type (a staff stays a staff, a poison talisman finds
  the poison-proof one; money if nothing matches), and money and sell-only treasures pay
  x(world / 12) - x6 at world 72 - and from world 60 follow tier-gear prices, so a chest
  stays worth about a third of a gear piece.
- **Side stories pay more:** every reward is kept; the money scales the same way, and the
  free reward slots get world-level counterparts of what the story already gives (tier gear
  for gear, better nuts, laddered stacks), bigger for the game's later-chapter stories.
- **Fixed-number skills grow:** Alfyn's concoctions, Rest and hired helpers' heals grow with
  your party's HP, so they keep their vanilla feel (Restore Health ~70% of a bar, Incredible
  Heal a full heal); their SP restores grow 40% as fast. Skills that scale with stats already
  grow with the new gear.
- **Runes for the whole party:** the Runelord's six elemental runes enchant every ally's
  weapons (Transfer Rune unchanged). Rune damage is the equipped weapon's elemental attack
  x 8, so pair them with elemental-attack weapons.

![The gear ladder](docs/images/gear.png)

### Quality of life

- **Toggle dash** (optional, `toggle_dash = true` in `overhaul.ini`): press the dash button
  once to run and again to walk, instead of holding it. A small patch to the game's own
  controller; no script loader needed.
- **Side-story walkthroughs in the journal**: each side story's journal entry lists every
  step with the town *and region*: who starts it, who to ask around, where to get each item
  or piece of information (who to Purchase/Steal or Inquire/Scrutinize), the steps on the
  way, every way to finish it and the reward. Read from the game's own event, NPC and shop
  data - pair it with fast travel. Also as one document: [docs/SIDE_STORIES.md](docs/SIDE_STORIES.md).
- **Fast travel to every location you have visited** (dungeons, caves, shrines — not just
  towns). Places you've never been stay locked.
- **Fewer random encounters**: Evasive Maneuvers is built in, so you get the support-skill
  slot back.
- **Catch-up leveling**: off in the vanilla opening; from the chapter 2s it phases in with
  the rest of the world, up to 5× cheaper EXP for every level more than 2 below your highest
  active traveler. A benched or lagging traveler shoots up to about 3 levels under your
  leaders and keeps pace with them, without grinding. Or set `catch_up = save`: before the
  game starts, anyone more than 3 levels behind gets their EXP raised to that level's normal
  total (the save is backed up first and only EXP changes), so they truly catch up after
  their next battle.
- **Higher caps**: stats 9,999 (from 999), HP 99,999 (from 9,999), damage 999,999.

All of these can be switched off individually.

---

## Settings — `overhaul.ini`

Created next to the exe on first run. Every preset plays the **chapter 1s exactly as
vanilla** and builds up to its full strength through the chapter 2s and 3s; `relentless`
adds its extra step through the chapter 4s and the finale. Three presets (full strength):

| Preset | For | World | Boss / superboss HP |
|---|---|---|---|
| `classic` | vanilla feel | the story's own curve | ×1 / ×1, vanilla enemy levels |
| `adaptive` *(default)* | most players | a little above the story, never below your party | ×1.25 / ×1.25 |
| `relentless` | strong, over-levelled endgame parties | story +5, at least party level +4 | ×2 / ×4 |

`vanilla_start = false` under `[tuning]` applies the full strength from the start.

Every value can be overridden under `[tuning]`, and every system turned off under
`[features]`. See [docs/BALANCE.md](docs/BALANCE.md) for what each preset does at every
stage of the game.

---

![The difficulty curve](docs/images/curve.png)

## Requirements & credits

**Requirements: none** — everything is built from your own game install, and you don't
need Python: the download carries its own copy of the official python.org runtime.
Windows 10 or 11 and the Steam version of the game.

Built to work alongside, with thanks:
- [Better Descriptions](https://www.nexusmods.com/octopathtraveler/mods/16) — the new items'
  descriptions follow its wording conventions, and its text is kept (new text is added on
  top of it).
- [Side Stories Helper](https://www.nexusmods.com/octopathtraveler/mods/21) — its other text
  is kept; its side-story journal hints are replaced by the full walkthroughs (which cover
  the same solutions, plus where everyone is).
- [Larger Monster Roster](https://www.nexusmods.com/octopathtraveler/mods/22) — H'aanit's
  larger roster is kept: catch-up leveling is built on top of its `CharacterGrowData`.
- [Long Distance Banter](https://www.nexusmods.com/octopathtraveler/mods/41) and
  [Our Purple Chests](https://www.nexusmods.com/octopathtraveler/mods/58) — no overlap.

The build log names any other installed mod that replaces a file this overhaul also
replaces (this one loads last and wins, except for the text tables and
`CharacterGrowData`, which it builds on top of).

## FAQ

**We share a PC / Steam account — does it work for two players?** Yes. The launcher asks
which save you're about to play and builds the world for that save. Load the same save in
the game (Continue loads whichever save is newest, so choose it from Load Game if needed).
Starting a brand-new game? Pick **New game** at the bottom of the list. Set
`save_choice = newest` in `overhaul.ini` to skip the question.

**Something went wrong — will the game still start?** Yes. If the overhaul can't be
rebuilt (game folder not found, a typo in `overhaul.ini`, the game still running...), you get
a message saying why and the game starts with the previous build. Details are in the `logs`
folder next to the exe. A rebuild takes about 15 seconds; if you click Play and nothing
seems to happen, give it a moment — the progress window may be on another monitor.

**Play in borderless fullscreen** (the game's display settings). While you play, the
launcher shows a "The World Stirs" banner when your progress would grow the world. In
exclusive fullscreen the game takes over the screen and no other window can appear on top,
so the banner only shows when you Alt-Tab. Borderless looks the same, switches faster, and
also avoids a display-mode crash some streaming or virtual-display setups hit in exclusive
fullscreen.

**Steam Deck / Linux / Game Pass?** Windows and the Steam version only. (The Game Pass
version stores its files differently.)

**Will I out-level everything?** Enemies keep up with your party, but the EXP and JP they
pay only follow half of your lead over the story, so leveling far ahead slows down like it
does in vanilla. `reward_share` in `overhaul.ini` changes that (1.0 = full EXP).

**Does the world change while I play?** The numbers are fixed for a session; the next
launch recalculates them from your save. Restart the game after a big story jump if you
want the world to catch up straight away.

**Other languages?** New item names and descriptions are in English in every language.

**Antivirus warning?** Since beta.4 the mod ships no exe of its own. The only programs in the
zip are the official python.org runtime (`runtime\`, digitally signed by the Python Software
Foundation); the mod itself is plain-text Python source in `app\` - you can read every line -
and `OrsterraUnbound.cmd` is a two-line script that starts it. (Earlier versions were
a PyInstaller exe, a format some scanners flag by habit.) Windows may ask "Do you want to run
this file?" the first time: click **Run**.

**Can I get a fifth support-skill slot?** No — the slot count lives in the game's code, not
its data. (Tested: the game ignores a fifth skill and removes it on save.) The built-in
Evasive Maneuvers and the uncapped damage free up two slots instead.

---

## Running from source

```bash
python src/launch_octopath.py           # same as the exe
python src/build_all.py                 # build a pak to the current folder, validate it
python dev/balance_report.py            # balance tables for every preset
```

Build the release (launcher + trimmed python.org runtime + source) with
`python dev/package_release.py` - it uses the Python on PATH as the runtime.

How it works, and why: [docs/DESIGN.md](docs/DESIGN.md).

---

*Not affiliated with Square Enix. Octopath Traveler is © Square Enix. This mod contains no
game files.* MIT licensed.
