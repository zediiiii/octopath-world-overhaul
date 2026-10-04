# Design and technical notes

## How the mod is delivered

Octopath Traveler (UE 4.18) has no runtime scripting hook for data mods: enemy stats, items
and shops are static DataTables cooked into `Octopath_Traveler-WindowsNoEditor.pak`. A data
mod can only replace those tables, so a world that "levels with you" has to be *rebuilt* from
the save. The launcher does this before every session:

1. read the chosen save (`MainProgressPoint`, the four active party members' levels)
2. read the vanilla tables from the player's own base pak
3. patch them, append the new items, validate, and write `~mods/ZZ_OctopathWorldOverhaul_p.pak`
4. start the game (Steam URL, or the `%command%` Steam passes through Launch Options)

A stamp (save, progress, party level, settings, mod version) skips the build when nothing
changed. A failed build never replaces the installed pak.

Paks mount in filename order and the last one wins; the `ZZ_` prefix makes this pak load
after other mods. Text tables are built on top of whichever mod's version currently wins, so
text mods (Better Descriptions, Side Stories Helper) keep working.

## Editing cooked DataTables without a serializer

- `.uexp` = object properties, `int32 0`, `int32 RowCount`, then rows; a row is an FName and
  tagged properties ending in `None`. Rows have no length prefix, and the only `.uasset`
  field that depends on the `.uexp` size is the export's `SerialSize`. So rows can be
  appended by cloning an existing row's bytes and patching fixed-width fields (FNames are
  8 bytes, ints 4) — no need to serialize TextProperty / ObjectProperty / nested structs.
- **New unique names without touching the name table**: an FName is (index, number), so an
  existing name with an unused number is a new name. All new items are `ITM_078_<n>`, a name
  present in ItemDB, PurchaseItemTable and EnemyDB, so shops and drops can reference them.
- **When a new name is needed** (`datatable.add_names`): append to the name table and shift
  every offset in the package summary plus the export's `SerialOffset`. Name entries carry
  two 16-bit hashes (Strihash_DEPRECATED and StrCrc32); the implementation reproduces all
  2,550 shipped ItemDB hashes.
- Strings are rewritten with a row splice + `SerialSize` fix; arrays of structs are not
  resized (only patched in place).

## The world floor

```
floor = max( story(chapters) + progress_margin ,  party_average_level + party_margin )
```

`story()` is a staircase built from the game's own chapter recommendations (`TownTable`):
chapter 1s 5–12, chapter 2s 21–27, chapter 3s 32–40, chapter 4s 45, finale 50.
`legacy_floor = true` also takes the original `8 + 3 × chapters` (no preset uses it now).

**Stage ramp.** The preset values above are its *full* strength. The game's stage is
`max(story(chapters), party_level − 10)`; at stage ≤ 12 (the chapter 1s) every preset uses
vanilla settings (no floor in the story's areas, vanilla enemy levels, boss HP ×1), blending
linearly to the preset's values by stage 30. `relentless` is `adaptive` from 30 to 40, then
blends to its own values by 50. `party_margin` blends from "off" via −12; enemy levels
rise to `weight × party level` and the steal-threshold shift follows the same weight.
Every **random-encounter** enemy is raised
(never lowered) to the vanilla enemy profile at the floor — the per-level median of the
game's own enemies, made non-decreasing — and its EXP / JP / money with it.

Enemies are classified by how the game reaches them, not by name:
area volume → `BattleEncounterData` → `EnemyGroupData` → `EnemyDB` is a random encounter;
`NPCBattleData` → group is a Provoke / Challenge NPC (left vanilla); `UseCatDamageType` is a
cait (left vanilla — they always take 1 damage); `BossBattle` groups and boss phases that
appear in no group are bosses.

**Bosses** have a *native danger*: story bosses (`BOS_<traveler>_00<chapter>`) use their
chapter's recommendation; others use the danger at which a regular enemy's attack, times the
attack premium story bosses carry (~1.1×), matches theirs. A boss is scaled per stat by
`profile(floor) / profile(native)` when the world has passed its native danger, and its HP
by the preset's extra multiplier.

**Enemy level** feeds `BATTLE_DAMAGE_LEVEL_RATIO` (4% per level of difference). Most rows
ship at level 1, so in vanilla the party out-levels everything; `enemy_level = party` sets
random enemies and bosses to at least the party's average level, keeping the bonus neutral.
Steal odds are keyed to the level difference too, so their thresholds shift with it.

## Gear

Tier numbers come from the same enemy profile: weapon attack so a character with a typical
non-weapon kit reaches vanilla's attack/defense ratio against that tier's enemies; armour
HP so a regular hit is about a fifth of max HP with a full set. Secondary stats on weapons
are capped (enemy evasion and speed never scale). Accessories stay within 2.5 × the tier in
total stat points (HP at 1/10, SP at 1/2).

Item IDs are pinned in `data/item_registry.json` so a rebuild never turns an owned item into
a different one. Every description is regenerated from the row's real data by the validator.

## Verified in-game

- Stat caps (`PLAYER_STATUS_RANGE.Max`, `PLAYER_STATUS_HP_RANGE.Max`) and the damage cap
  (`BATTLE_DAMAGE_CAP`) are data and can be raised.
- Equipment stats: armour and accessory bonuses add up; weapon bonuses don't add across the
  six weapon slots (the best per stat applies), and HP / SP on weapons do nothing.
- Encounter rate: the per-area step counts only matter if `MAX_ENCOUNT_STEP_COUNT` is raised.
- Equipment effects the game honours: fixed HP/SP regen, element / weapon damage boosts,
  resistances, on-hit procs, EXP/JP, encounter rate, status immunity. General battle buffs
  (speed up, BP regen, % HP regen…) on equipment are **ignored**.
- A fifth support skill is impossible: a fifth `EquipSupportSkill` entry is ignored in battle
  and truncated to four on the next save.
- Extended name tables load and work in-game.

## Not yet verified

- Elemental damage boosts on **accessories** (Sigils, Hearts) — shipped data only puts them on
  weapons.
- The exact steal-threshold semantics.

## Validation

`validate.py` runs after every build and blocks the install on any error. Among its checks:
all original item rows byte-identical (nothing a player owns changes), new IDs match the
registry, every description matches its item's data, NPC / cait / unreachable enemies exactly
vanilla, no enemy or boss weakened, superbosses untouched until the world passes them, no
unique vanilla drop replaced, summons only raised, EXP totals unchanged at levels the party
has reached, structure of every table.
