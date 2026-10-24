"""Build a mod pak that scales the world's difficulty to your story progress.

The game has no runtime level-scaling: enemy stats are static rows in EnemyDB, and the
built-in per-area tier system (EncountVolumeData.EncounterList, gated by ProgressBorder)
tops out at border 88 - which you are already past. So this bakes the numbers instead.

Re-run it after each main chapter; the world danger floor rises by PER_QUEST each time.

What it changes
  * Only enemies an area can actually roll are "regular". Provoke/Challenge opponents
    (NPCBattleData), caits and unreachable rows are left exactly as shipped - see
    enemy_classes().
  * InvadeData: H'aanit's summons of scaled beasts are floor-raised to match.
  * EnemyDB, regular enemies : HP/ATK/MATK/DEF/MDEF/ACC raised UP TO the profile of an
                               enemy at the current world floor. Already-tougher enemies
                               are left alone (floor-raise, never a nerf).
  * EnemyDB, regular enemies : Exp/JobPoint/Money/StealMoney floor-raised the same way,
                               so a buffed enemy pays out like the enemy it now resembles.
  * EnemyDB, normal bosses   : HP x BOSS_HP_MULT. Nothing else, so they hit as designed
                               but last longer.
  * EnemyDB, superbosses     : untouched (BOS_Lst_* Galdera, BOS_Ext_* shrine/rematch
                               bosses, EVE_EXT_* optional beasts).
  * EncountVolumeData        : DangerLevel (the number in the area-name popup) raised to
                               match. Areas already >= HARD_AREA_THRESHOLD go to
                               HARD_AREA_DANGER.

Deliberately NOT changed: DisplayLevel. Despite the name it is read by BattleTameMonsterBP,
FieldCommandMonster, SummonAbilityCommand and InvadeCommand - it affects H'aanit's capture
rates and summon strength, so it is not a cosmetic field.
"""
import paths
import os
import re
import struct
import sys
import statistics

import pak
import uasset
import gvas
import datatable as dt
import pakwrite
import respec_core as rc
import buildlog

# ---------------------------------------------------------------- config
# ---- the world danger floor ----------------------------------------------------------
# Every regular enemy is raised to at least the game's own enemy profile at this danger.
#   floor = max(expected story danger + PROGRESS_MARGIN,  party average level + PARTY_MARGIN)
# "Expected story danger" is the game's own chapter recommendation (TownTable): chapter 1
# 5-12, chapter 2 21-27, chapter 3 32-40, chapter 4 45, interpolated by chapters completed.
# A party playing at the story's pace meets vanilla-plus enemies; a party that out-levels
# the story meets enemies that keep up. Presets in config.py set these.
# "progress" below is chapters completed x PROGRESS_PER_QUEST. Chapters are counted from each
# traveler's MainMissionProgressCnt (1000 per chapter finished; e.g. 2150 = two done and part
# of the third). MainProgressPoint is NOT a chapter count: it weighs chapter 1/2/3/4 as
# 1/4/8/16 points (fitted exactly to 17 real saves), so it undercounts the early game badly.
PROGRESS_PER_QUEST = 8
CHAPTER_WEIGHTS = (1, 4, 8, 16)     # MainProgressPoint per chapter 1..4, for the fallback
# (chapters done, danger): a staircase following the game's chapter recommendations -
# chapter 1s 5-12 (by travelers recruited), chapter 2s 21-27, chapter 3s 32-40, chapter 4s 45,
# the finale ~50. Players can mix chapters freely; this tracks the usual order.
EXPECTED_DANGER = [(0, 5), (7, 12), (8, 21), (15, 27), (16, 32), (23, 40), (24, 45),
                   (31, 45), (32, 50)]
PROGRESS_MARGIN = 2
PARTY_MARGIN = 0          # None = ignore party level
# The original "relentless" curve: 8 + 3 per chapter (ran far ahead of the story on purpose)
LEGACY_FLOOR = False
BASE_DANGER = 8
PER_QUEST = 3
SCALE_WORLD = True        # False = no enemy / boss / area changes at all
# Optional areas whose vanilla danger is already >= HARD_AREA_THRESHOLD can be shown a step
# above the world. Display only, so off by default.
HARD_AREA_DISPLAY = False
# Player stats cap at 999, but the damage cap is lifted - confirmed in-game: H'aanit hit for
# 25,000 WITHOUT the "Surpassing Power" support skill (ability 300), whose vanilla cap is
# 9,999. Only Olberic has that skill, so the global BATTLE_DAMAGE_CAP patch is what allowed
# it. That matters because the tier weapons' WEAPON_ABILITY_UP multipliers apply *after* the
# capped stat: against the old 9,999 wall they were wasted, now they pay off in full. At tier
# 99 that is 999 x 2.56 = 2,557 against a danger-99 enemy's 1,877 DEF - the same 1.36 ratio
# the shipped game balances around. So the ladder holds parity to ~100 rather than stalling
# at the stat-capped 80. This DEPENDS on owning the tier gear; without it, ~82 still applies.
MAX_DANGER = 104
# EnemyLevel feeds BATTLE_DAMAGE_LEVEL_RATIO (0.04/level, capped at 3.1x), so it is a real
# damage lever and not the dead field it looks like - 771 enemies ship at level 1.
# Enemy level feeds BATTLE_DAMAGE_LEVEL_RATIO (4% per level of difference, up to 3.1x).
# Measured in-game at danger 68: with enemies at level 68 vs a ~56 party, a Greater
# Kingfisher's Meteor hit for ~6,800; at vanilla levels, 4,200. Vanilla levels swing the other
# way once the party out-levels everything. So levels track the PARTY's average level (the
# four active members in the save) and the bonus stays roughly neutral both ways.
#   "party" - max(vanilla level, party average)      False - vanilla levels
SET_ENEMY_LEVEL = "party"
HARD_AREA_THRESHOLD = 50  # areas at/above this are "optional / hard"...
HARD_AREA_DANGER = 70     # ...and get this danger level (or floor+margin, whichever is higher)
HARD_AREA_MARGIN = 12
# With HARD_AREA_DISPLAY the hard areas' danger is real, not just shown: their optional
# superbosses (shrine bosses, the beasts in Everhold, the caves and the Hollow Throne) and
# the regular enemies found only there are built for that danger (user 2026-10-24: Everhold
# showed 114 while Managarmr had world-102 HP).
HARD_AREA_SUPERBOSSES = ("BOS_Ext_Job_", "EVE_EXT_")


HARD_AREA_CAP = 108       # user 2026-10-24: hard areas top out at 108 (Galdera: 104)


def hard_danger(floor):
    """The danger of the optional / hard areas: a step above the world, never below it,
    and never past HARD_AREA_CAP."""
    return min(HARD_AREA_CAP, max(HARD_AREA_DANGER, floor + HARD_AREA_MARGIN))


def hard_area_enemies(p, cls):
    """Regular enemies that only appear in hard areas (vanilla danger >= the threshold)."""
    def table(path):
        return uasset.read_datatable(p.read(path + ".uasset"), p.read(path + ".uexp"))
    eg, be, vol = table(ENEMY_GROUPS), table(ENCOUNTERS), table(VOLUME)
    seen = {}
    for v in vol.values():
        for e in g(v, "EncounterList"):
            n, d = g(e, "EncounterName"), g(e, "DangerLevel")
            if n not in be or d <= 0:
                continue
            for x in g(be[n], "Group"):
                for en in (g(eg[g(x, "GroupID")], "EnemyID") if g(x, "GroupID") in eg else ()):
                    if en and en != "None":
                        seen[en] = min(seen.get(en, d), d)
    return {k for k, d in seen.items() if d >= HARD_AREA_THRESHOLD and cls.get(k) == "random"}
BOSS_HP_MULT = 2.0        # user 2026-10-04: 2x (Winnehild's Battle Cry ~24k x6 must not end fights in two turns)
SCALE_REWARDS = True
# Catch-up leveling. CharacterGrowData's TotalExp is one table shared by all eight characters
# and the save stores cumulative EXP, so cheapening low levels must NOT lower the totals of
# levels the main party has reached (they would level instantly). Every level below
# catchup_threshold() (the top active member's level - CATCHUP_MARGIN) costs 1/CATCHUP_FACTOR
# of the EXP; the threshold level and
# above are untouched. No ramp back to vanilla: a ramp charges the saved EXP back on the
# levels just below the threshold (2-3x vanilla each - a traveler 5-10 levels behind levelled
# SLOWER than the party). Instead the whole difference sits in the one step to the threshold,
# and since the threshold follows the party (rebuilt when it levels), a traveler below it
# snaps up to one level under it and keeps pace about CATCHUP_MARGIN + 1 levels behind.
CATCHUP_LEVELING = True
CATCHUP_FACTOR = 5
CATCHUP_MARGIN = 2                # below the highest active party member (catchup_threshold)
GROW = "Octopath_Traveler/Content/Character/Database/CharacterGrowData"

# Steal odds come from level-difference thresholds: STEAL_PROBABILITY_LEVEL_OVER (2 / 4 / 11
# levels above the target) -> STEAL_PROBABILITY_OVER (65 / 80 / 100%), and
# STEAL_PROBABILITY_LEVEL_LESS_THAN (-11 / -4 / -1) for being below. In vanilla's endgame the
# party out-levels everything by 11+, so steals land 100%; with enemy levels now tracking the
# party they would fall to the base rate. Shift every threshold down by this many levels so
# an equal-level steal behaves like vanilla's out-levelled one. (Threshold meaning inferred
# from names and values - unverified in-game.)
STEAL_LEVEL_SHIFT = 11

# Player stat caps. Both live in GameParamDefineTable as data (PLAYER_STATUS_RANGE.Max = 999,
# PLAYER_STATUS_HP_RANGE.Max = 9999), not in compiled code. Set to the vanilla values to
# leave them alone.
PLAYER_STAT_CAP = 9999
PLAYER_HP_CAP = 99999

# Tressa's "Collect" talent (money she finds after battle): BattleParamDefineTable
# TRESSA_SPECIAL_PARAM_001..010, vanilla 280..8,560 leaves. Scaled by the same ratio enemy
# money rose by, so her finds keep pace with battle income.
SCALE_TRESSA_COLLECT = True
TRESSA_COLLECT_ROWS = [f"TRESSA_SPECIAL_PARAM_{i:03d}" for i in range(1, 11)]
# H'aanit's summons follow the enemies they came from (see the InvadeData pass)
SCALE_SUMMONS = True
SUMMON_STATS = ["ATK", "MATK", "DEF", "MDEF", "ACC", "CON"]
# Bosses (normal AND super) are scaled by the ratio the world has moved, per stat, so they
# keep the standing they shipped with. Without this a superboss ends up SOFTER than a random
# encounter: median superboss DEF is 553 against a danger-80 regular enemy's 1128.
# At the current floor the ratio is 1.00, so superbosses are untouched until the world
# actually outgrows them.
SCALE_BOSSES = True
SUPERBOSS_EXTRA = 1.0     # additional multiplier on superboss stats, if you want them nastier
SUPERBOSS_HP_MULT = 4.0   # user 2026-10-04: 4x
# Median superboss DEF is 553. Regular enemies pass that between danger 55 and 60, so until
# then superbosses are still the apex and are left exactly as shipped - which also matches
# "I haven't found them yet, leave them alone".
# (superbosses now scale from their own native danger - see boss_natives)
# Raise the global damage cap. It is one value for everyone, but in practice only the player
# gets near it: enemy attack tops out around 1300 at the danger ceiling.
RAISE_DAMAGE_CAP = True
DAMAGE_CAP = 999999
PARAMS = "Octopath_Traveler/Content/GameParam/GameParamDefineTable"
BATTLE_PARAMS = "Octopath_Traveler/Content/GameParam/BattleParamDefineTable"

# "Evasive Maneuvers" (ability 437) has no data-driven effect - it is blueprint logic, so the
# skill itself cannot be switched on permanently. What it does is stretch the steps between
# random encounters, and that IS data. BattleParamDefineTable carries
# EX_EVASION_UP_FIELD_RATIO = 2.0, matching the ADD_EVASION_UP_FIELD ailment, so the skill
# doubles the step count. Baking that into EncountVolumeData gives the same result with no
# skill slot spent - which also frees Olberic's slot, since he is the one carrying it.
# Note: leaving the skill equipped as well stacks with this (2 x 2 = quarter rate).
PERMANENT_EVASIVE_MANEUVERS = True
ENCOUNTER_STEP_MULT = None        # None = read EX_EVASION_UP_FIELD_RATIO from the game data
ENCOUNTER_STEP_FIELDS = ["EncountStepMin", "RandomStepA", "RandomStepB"]
# Doubling the per-area step counts alone does nothing much, because
# GameParamDefineTable.MAX_ENCOUNT_STEP_COUNT caps the counter at 300 - vanilla areas already
# sit at 240 + up to 120 random, so they were being clamped near 300 and the doubled values
# were simply cut back to the same place. This ceiling has to move with them.
ENCOUNT_STEP_CEILING = 1500

# Scaling every existing item is deliberately OFF: it would silently buff the gear already on
# your characters, which is the one thing you asked not to happen. The new gear ladder in
# build_all.py provides the catch-up instead, as brand-new items you choose to acquire.
SCALE_EXISTING_GEAR = False
GEAR_FROM_DANGER = 65
GEAR_CATCHUP = 1.4

ITEMS = "Octopath_Traveler/Content/Item/Database/ItemDB"
# EquipmentRevision is a CharacterParam struct; these names are shared with DopingParam, so
# they are matched in full rather than by prefix (plain "HP" is ambiguous inside ItemDB).
EQUIP_FIELDS = [
    "HP_38_60C1981648472447396094AC51E6861E",
    "MP_39_F930AFBC4A48BE8BF00009B7841D66D5",
    "ATK_40_4AB44CD740D8A6BF06E3A0A6B62FF589",
    "DEF_41_BAE3A0D84D0AD654D3F0D68D467163E3",
    "MATK_42_6CE7342144ABD5515E1DCFB07DB6F9EA",
    "MDEF_43_F437EF5F447142384DD0BA91294B3A3B",
    "ACC_44_C4B000CE4B3238F27EC316896A346DB8",
    "EVA_45_D1A7250742962DB6306A7295D71AADE7",
    "CON_46_9BCE805749432E94492E49B0EE90D7FF",
    "AGI_47_2F9420C345AFAAE3A5D6CC9F78B42D5D",
]

STATS = ["HP", "ATK", "MATK", "DEF", "MDEF", "ACC"]
REWARDS = ["Exp", "JobPoint", "Money", "StealMoney"]
# EXP and JP only follow the PARTY part of the floor halfway. Enemies that keep up with an
# out-levelled party must not also pay at-level EXP, or the party levels every ~6 fights no
# matter how far ahead of the story it is (vanilla slows that to 12-25+ fights once 10-20
# levels ahead) - a runaway the user hit (level 30 in chapter 2). Money pays in full so the
# gear economy holds. 1.0 = old behaviour, 0.0 = growth rewards follow the story only.
GROWTH_REWARDS = ["Exp", "JobPoint"]
REWARD_SHARE = 0.5
STORY_FLOOR = 1           # the floor without the party part, set by world_floor()
SUPERBOSS_PREFIXES = ("BOS_Lst_", "BOS_Ext_", "EVE_EXT_")

ENEMY = "Octopath_Traveler/Content/Character/Database/EnemyDB"
VOLUME = "Octopath_Traveler/Content/Battle/Database/EncountVolumeData"
OUT_NAME = "WorldDifficultyScaling_p.pak"

g = lambda d, pre: next(vv for kk, vv in d.items() if kk.split("_")[0] == pre)


def int_offsets(ua, ue, field, expect=None, exact=False):
    """Byte offsets of every IntProperty named `field`, in file order."""
    names, _ = uasset.names_of(ua)
    if exact:
        cand = [n for n in names if n == field]
    else:
        cand = [n for n in names if n.split("_")[0] == field]
    if len(cand) != 1:
        raise RuntimeError(f"{field}: ambiguous name entries {cand}")
    idx = names.index(cand[0])
    offs = []
    for m in re.finditer(re.escape(struct.pack("<ii", idx, 0)), ue):
        o = m.start()
        t = names[struct.unpack_from("<i", ue, o + 8)[0]]
        size, _i = struct.unpack_from("<ii", ue, o + 16)
        if t == "IntProperty" and size == 4:
            offs.append(o + 25)
    if expect is not None and len(offs) != expect:
        raise RuntimeError(f"{field}: found {len(offs)} offsets, expected {expect}")
    return offs


# the save the launcher's picker chose; None = newest; NEW_GAME = no save yet (chapter 0,
# level 1 - a player starting fresh, or a second player on a shared PC)
SELECTED_SAVE = None
NEW_GAME = "<new game>"


def expected_danger(chapters):
    """The story's own recommended danger after `chapters` main chapters."""
    pts = EXPECTED_DANGER
    if chapters <= pts[0][0]:
        return pts[0][1]
    for (c0, d0), (c1, d1) in zip(pts, pts[1:]):
        if chapters <= c1:
            return d0 + (d1 - d0) * (chapters - c0) / (c1 - c0)
    return pts[-1][1]


# ---- completion (relentless) --------------------------------------------------------
# Relentless lets the whole game's completion drive the world past the story: danger =
# COMPLETION_TOP x a weighted share of main chapters, side stories, optional bosses fought
# and areas visited (user 2026-10-04: "the highest tier is 104 ... you'll get there by
# completing the main quests + the optional bosses and areas and quests"). The main story
# alone lands near the game's own endgame (~52); everything optional carries it to 104.
COMPLETION_TOP = 104
COMPLETION_WEIGHTS = {"chapters": 0.50, "side_stories": 0.20, "optional_bosses": 0.20,
                      "areas": 0.10}
COMPLETION_FLOOR = 0.0    # 0..1, how much of the completion floor applies (set per stage)
SUB_MISSIONS = "Octopath_Traveler/Content/Mission/Database/Sub_MissionRecord"
# Areas are the world map's 147 locations (WorldMapTable, without the 10 leftover demo rows
# that repeat Cobbleston / Sunshade); one counts as explored when the save's VisitedMap has
# any of its levels (a bit per level ID). All 147 are real places, so 100% is reachable.
WORLD_MAP = "Octopath_Traveler/Content/Level/Database/WorldMapTable"
WORLD_MAP_DEMO_ROWS = 10
# optional bosses, grouped into one fight each: the four shrine gods, the eight revived bosses
# of the Gate of Finis and the side-story beasts (Jotunn, Leviathan ...). A bestiary entry
# counts as fought; EnemyIDs that other rows share are ignored. Galdera is not counted: the
# game ends after that fight, so no save can record it and 100% would be unreachable.
OPTIONAL_BOSS_GROUP = (
    (re.compile(r"BOS_Ext_Job_(\d{3})"), "shrine {}"),
    (re.compile(r"BOS_Ext_Rev_\d(\d{2})"), "rematch {}"),
    (re.compile(r"EVE_EXT_(\d{3})_"), "beast {}"),
)
# The game's hardest fight. Relentless pins it at a fixed danger (FINAL_BOSS_DANGER, from
# config) instead of the world's, so there is always a peak to work toward.
FINAL_BOSS_PREFIX = "BOS_Lst_"
FINAL_BOSS_DANGER = 0     # 0 = scale with the world like the other superbosses
# The eight revived chapter-4 bosses of the Gate of Finis ("Darius?" ...) are fought at
# this danger or the world's, whichever is higher (user 2026-10-04: "at least at 94").
REVENANT_PREFIX = "BOS_Ext_Rev_"
REVENANT_MIN_DANGER = 0
# The Gate of Finis is the last stop: its eight rematches, the Gate itself and At Journey's
# End (which finishes after Galdera) don't count toward completion, so the world reaches its
# peak - and Grandport its newest tier - before you go in.
GATE_LEVELS = {195, 196}
GATE_BOSS_GROUP = "rematch"
_COMPLETION_DATA = {}
LAST_COMPLETION = None    # completion() of the save the last build() was made for


def _completion_data():
    """(({area: [(slot, story)]}, number of side stories), {boss group: [EnemyID]},
    [level IDs of each world-map location]) from the game data, cached. Only the 101 real side stories count (see side_stories.py), and nothing in the Gate of Finis (GATE_LEVELS): counting
    all 144 records made full completion - and the Wayfarer's Laurel - unreachable."""
    if not _COMPLETION_DATA:
        import side_stories
        p = pak.Pak(paths.base_pak())
        per_area = side_stories.slots(countable=True)
        rows = uasset.read_datatable(p.read(ENEMY + ".uasset"), p.read(ENEMY + ".uexp"))
        uses = {}
        for v in rows.values():
            uses[g(v, "EnemyID")] = uses.get(g(v, "EnemyID"), 0) + 1
        groups = {}
        for k, v in rows.items():
            if uses[g(v, "EnemyID")] > 1:
                continue
            for rx, label in OPTIONAL_BOSS_GROUP:
                m = rx.match(k)
                if m and not label.startswith(GATE_BOSS_GROUP):
                    groups.setdefault(label.format(*m.groups()), []).append(g(v, "EnemyID"))
                    break
        wmap = uasset.read_datatable(p.read(WORLD_MAP + ".uasset"), p.read(WORLD_MAP + ".uexp"))
        places = []
        for v in list(wmap.values())[WORLD_MAP_DEMO_ROWS:]:
            ids = {int(x) for x in list(g(v, "RefLevelName")) + [g(v, "MoveLevelName")]
                   if x and x != "None"}
            if ids and not ids & GATE_LEVELS:
                places.append(ids)
        _COMPLETION_DATA.update(per_area=per_area, groups=groups, places=places)
    return _COMPLETION_DATA["per_area"], _COMPLETION_DATA["groups"]


def completion(save_path):
    """-> dict of counts and the weighted completion share (0..1) of a save."""
    if save_path in (None, NEW_GAME):
        return dict(share=0.0, chapters=0, side_stories=0, optional_bosses=0, areas=0)
    s = gvas.SaveFile.load(save_path)
    per_area, groups = _completion_data()
    slots, side_total = per_area
    done = set()
    for a, grp in enumerate(s.get("SubMissionData").value):
        states = {q.name.split("_")[0]: q.value for q in grp}["MissionState"]
        done |= {story for pos, story in slots.get(a, ()) if pos < len(states) and states[pos] == 2}
    side = len(done)
    info = s.get("EnemyInfoData").value
    fought = lambda i: 0 <= i < len(info) and any(q.value for q in info[i])
    bosses = sum(1 for ids in groups.values() if any(fought(i) for i in ids))
    places = _COMPLETION_DATA["places"]
    vm = s.get("VisitedMap").value
    seen = lambda i: i // 32 < len(vm) and (vm[i // 32] >> (i % 32)) & 1
    areas = sum(1 for ids in places if any(seen(i) for i in ids))
    out = dict(chapters=chapters_done(s), side_stories=side, optional_bosses=bosses,
               areas=areas)
    totals = dict(chapters=32, side_stories=side_total,
                  optional_bosses=len(groups), areas=len(places))
    out["share"] = sum(w * min(1.0, out[k] / totals[k]) for k, w in COMPLETION_WEIGHTS.items())
    out["totals"] = totals
    return out


# ---- how hard, by stage of the game ---------------------------------------------------
# The chapter 1s play as vanilla and the preset's full strength builds up through the
# mid game (user 2026-10-04: harder curves were fun late, not early). RAMP is a list of
# (stage, settings) anchors set by config.apply(), interpolated linearly between them. The
# stage is the story's recommended danger, or the party's level less STAGE_PARTY_LEAD when
# that is higher, so a party far ahead of the story moves the game on. None = the module
# settings above apply unchanged.
RAMP = None
STAGE_PARTY_LEAD = 10
# party_margin has no "off" number to interpolate from; this stands in for it
PARTY_MARGIN_OFF = -12
ENEMY_LEVEL_WEIGHT = 1.0  # 0 = vanilla enemy levels, 1 = at least the party's level
STAGE = None              # (stage, settings) of the last world_floor() call, for logs
FLOOR_ACTIVE = True       # False when the stage's floor is below danger 1 (see world_floor)


def stage_of(progress, party_lv):
    return max(expected_danger(progress // PROGRESS_PER_QUEST), party_lv - STAGE_PARTY_LEAD)


def settings_at(stage, ramp=None):
    """Interpolate the RAMP anchors at `stage` -> settings dict."""
    pts = ramp or RAMP
    if stage <= pts[0][0]:
        return dict(pts[0][1])
    if stage >= pts[-1][0]:
        return dict(pts[-1][1])
    for (s0, a), (s1, b) in zip(pts, pts[1:]):
        if stage <= s1:
            w = (stage - s0) / (s1 - s0)
            break
    out = {}
    for k in b:
        x, y = a[k], b[k]
        if isinstance(x, bool) or isinstance(y, bool):
            out[k] = y if w >= 0.5 else x
        elif k == "party_margin":
            if x is None and y is None:
                out[k] = None
                continue
            x = PARTY_MARGIN_OFF if x is None else x
            y = PARTY_MARGIN_OFF if y is None else y
            v = x + (y - x) * w
            out[k] = None if v <= PARTY_MARGIN_OFF else round(v, 2)
        else:
            out[k] = round(x + (y - x) * w, 3)
    return out


def catchup_divisor():
    """How many times cheaper catch-up makes the low levels: 1 (off) through the vanilla
    opening, rising with the stage ramp to CATCHUP_FACTOR when the world reaches full
    strength - it only matters once the world is scaled to the party. No ramp = full."""
    if not RAMP or not STAGE:
        return float(CATCHUP_FACTOR)
    s0, s1 = RAMP[0][0], RAMP[1][0]
    w = max(0.0, min(1.0, (STAGE[0] - s0) / (s1 - s0)))
    return 1.0 + (CATCHUP_FACTOR - 1) * w


def apply_settings(s):
    global PROGRESS_MARGIN, PARTY_MARGIN, LEGACY_FLOOR, BOSS_HP_MULT, SUPERBOSS_HP_MULT
    global ENEMY_LEVEL_WEIGHT, SET_ENEMY_LEVEL, STEAL_LEVEL_SHIFT, HARD_AREA_DISPLAY
    PROGRESS_MARGIN = s["progress_margin"]
    PARTY_MARGIN = s["party_margin"]
    LEGACY_FLOOR = s["legacy_floor"]
    global COMPLETION_FLOOR
    COMPLETION_FLOOR = s.get("completion_floor", 0.0)
    BOSS_HP_MULT = s["boss_hp_mult"]
    SUPERBOSS_HP_MULT = s["superboss_hp_mult"]
    ENEMY_LEVEL_WEIGHT = s["enemy_level"]
    SET_ENEMY_LEVEL = "party" if ENEMY_LEVEL_WEIGHT > 0 else False
    # steal thresholds shift with how far enemy levels were raised (see STEAL_LEVEL_SHIFT)
    STEAL_LEVEL_SHIFT = round(11 * ENEMY_LEVEL_WEIGHT)
    HARD_AREA_DISPLAY = s["hard_area_display"]


def world_floor(progress, party_lv, completion_share=None):
    """-> (floor, explanation). With a RAMP, first applies this stage's settings.
    completion_share (0..1, see completion()) raises the story side on relentless."""
    global STAGE
    chapters = progress // PROGRESS_PER_QUEST
    why = []
    if RAMP:
        stage = stage_of(progress, party_lv)
        s = settings_at(stage)
        apply_settings(s)
        STAGE = (stage, s)
        why.append(f"stage {stage:.0f}: boss HP x{BOSS_HP_MULT:g}, enemy levels "
                   f"{ENEMY_LEVEL_WEIGHT:.0%} of party")
    story = expected_danger(chapters) + PROGRESS_MARGIN
    why.insert(0, f"story {story:.0f} ({chapters} chapters)")
    if COMPLETION_FLOOR > 0 and completion_share is not None:
        comp = COMPLETION_TOP * completion_share
        if comp > story:
            story += COMPLETION_FLOOR * (comp - story)
            why.append(f"completion {completion_share:.0%} -> {comp:.0f}"
                       + (f" x{COMPLETION_FLOOR:g}" if COMPLETION_FLOOR < 1 else ""))
    if LEGACY_FLOOR:
        legacy = BASE_DANGER + PER_QUEST * chapters
        story = max(story, legacy)
        why.append(f"relentless curve {legacy}")
    party = party_lv + PARTY_MARGIN if PARTY_MARGIN is not None else 0
    if PARTY_MARGIN is not None:
        why.append(f"party {party_lv}{PARTY_MARGIN:+g}")
    raw = max(story, party)
    global STORY_FLOOR
    STORY_FLOOR = max(1, min(MAX_DANGER, story))
    # The opening stage asks for less than danger 1, the lowest there is: no floor at all,
    # rather than raising the weakest starting-area enemies to danger 1's median.
    global FLOOR_ACTIVE
    FLOOR_ACTIVE = raw >= 1
    if not FLOOR_ACTIVE:
        why.append("below danger 1: regular enemies as shipped")
    floor = int(round(min(MAX_DANGER, max(1, raw))))
    return floor, ", ".join(why)


# boss ID prefix -> character id, for BOS_<chr>_00<chapter> / EVE_<chr>_00<chapter>
BOSS_CHARACTER = {"Olb": 1, "Tre": 2, "Cyr": 3, "Pri": 4, "Han": 5, "The": 6, "Oph": 7,
                  "Alf": 8}
TOWNS = "Octopath_Traveler/Content/Level/Database/TownTable"


def chapter_recommendations(p):
    """(character id, chapter) -> recommended level, from the game's TownTable."""
    rows = uasset.read_datatable(p.read(TOWNS + ".uasset"), p.read(TOWNS + ".uexp"))
    out = {}
    for v in rows.values():
        f = {k.split("_")[0]: x for k, x in v.items()}
        for n in ("1", "2"):
            cid, ch = f[f"MainEvent{n}CharacterID"], f[f"MainEvent{n}Capter"]
            rec = f[f"MainEvent{n}Recommendation"]
            if cid and ch:
                # pairs of (travelers recruited, level); chapter 1 has four, the rest one
                levels = [rec[i] for i in range(1, len(rec), 2) if rec[i]]
                out[(cid, ch)] = sum(levels) / len(levels) if levels else 0
    return out


def boss_natives(p, rows, cls, curve, levels):
    """boss row -> the danger it was designed for.

    Story bosses: their chapter's recommended level. Everything else (shrine guardians,
    optional beasts, Galdera, field bosses): the danger whose regular-enemy attack, times the
    attack premium story bosses carry over regular enemies, matches the boss's own attack.
    """
    rec = chapter_recommendations(p)
    out, premiums = {}, []
    for k in rows:
        if cls[k] not in ("boss", "super"):
            continue
        a = k.split("_")
        if a[0] in ("BOS", "EVE") and len(a) > 2 and a[1] in BOSS_CHARACTER and a[2].isdigit():
            n = rec.get((BOSS_CHARACTER[a[1]], int(a[2])))
            if n:
                out[k] = n
                atk = g(g(rows[k], "Param"), "ATK")
                if atk > 0:
                    premiums.append(atk / max(1, profile_at(curve, levels, n)["ATK"]))
    premium = statistics.median(premiums) if premiums else 1.1
    table = [(d, profile_at(curve, levels, d)["ATK"] * premium) for d in range(1, 121)]
    for k in rows:
        if cls[k] in ("boss", "super") and k not in out:
            atk = g(g(rows[k], "Param"), "ATK")
            out[k] = max([d for d, a in table if a <= atk] or [1])
    return out


def quests_done(save_path=None):
    path = save_path or SELECTED_SAVE
    if path is None:
        saves = rc.find_saves()
        path = max(saves, key=os.path.getmtime) if saves else NEW_GAME
    if path == NEW_GAME:
        return NEW_GAME, 0
    s = gvas.SaveFile.load(path)
    return path, chapters_done(s) * PROGRESS_PER_QUEST


def chapters_done(s):
    """Main-story chapters finished across all eight travelers (0-32), from a loaded save."""
    total, found = 0, False
    for m in s.get("PlayerMember").value:
        f = {x.name.split("_")[0]: x.value for x in m}
        if not 1 <= f.get("CharacterID", -1) <= 8 or "MainMissionProgressCnt" not in f:
            continue
        found = True
        total += max(0, min(4, f["MainMissionProgressCnt"] // 1000))
    if found:
        return total
    # no per-traveler counters: estimate from MainProgressPoint, filling chapters in order
    pts, total = s.get("MainProgressPoint").value, 0
    for w in CHAPTER_WEIGHTS:
        n = min(8, pts // w)
        total += n
        pts -= n * w
    return total


def party_level(save_path):
    """Average level of the four active party members in the save."""
    if save_path == NEW_GAME:
        return 1
    s = gvas.SaveFile.load(save_path)
    slot = {x.name.split("_")[0]: x for x in s.get("slotData").value}
    ids = [getattr(x, "value", x) for x in slot["MainMemberCharacterID"].value]
    levels = {}
    for m in s.get("PlayerMember").value:
        f = {x.name.split("_")[0]: x.value for x in m}
        levels[f["CharacterID"]] = f["Level"]
    active = [levels[c] for c in ids if c in levels and levels[c] > 0]
    if not active:
        raise RuntimeError("no active party members found in the save")
    return round(sum(active) / len(active))


def catchup_threshold(save_path):
    """The first level catch-up leaves at its normal cost: the highest active party member's
    level less CATCHUP_MARGIN. A cheaper table only matters for levels a traveler hasn't
    reached, so the leaders - at or above the line - are never moved; everyone below
    climbs to just under it (was: the party average - 4, which left a traveler 5-10 levels
    behind facing one level that charged the whole shortfall)."""
    if save_path == NEW_GAME:
        return 1
    s = gvas.SaveFile.load(save_path)
    slot = {x.name.split("_")[0]: x for x in s.get("slotData").value}
    ids = [getattr(x, "value", x) for x in slot["MainMemberCharacterID"].value]
    top = 1
    for m in s.get("PlayerMember").value:
        f = {x.name.split("_")[0]: x.value for x in m}
        if f["CharacterID"] in ids:
            top = max(top, f["Level"])
    return top - CATCHUP_MARGIN


def build_curve(rows, boss_ids):
    """level -> median stat/reward profile, from enemies the game itself authored."""
    by_lvl = {}
    for k, v in rows.items():
        if k in boss_ids:
            continue
        lv = g(v, "EnemyLevel")
        if lv < 2:                      # level is unset/garbage for most rows
            continue
        by_lvl.setdefault(lv, []).append(v)
    curve = {}
    for lv, vs in by_lvl.items():
        if len(vs) < 2:
            continue
        prm = [g(v, "Param") for v in vs]
        curve[lv] = {s: int(statistics.median(g(p, s) for p in prm)) for s in STATS}
        for r in REWARDS:
            curve[lv][r] = int(statistics.median(g(v, r) for v in vs))
    # make each stat non-decreasing in level so the floor is never a nerf
    levels = sorted(curve)
    for key in STATS + REWARDS:
        run = 0
        for lv in levels:
            run = max(run, curve[lv][key])
            curve[lv][key] = run
    return curve, levels


def profile_at(curve, levels, target):
    """Interpolate (or extrapolate) the authored curve to an arbitrary level."""
    if target <= levels[0]:
        return dict(curve[levels[0]])
    if target >= levels[-1]:
        lo, hi = levels[-2], levels[-1]
        span = hi - lo
        out = {}
        for key in STATS + REWARDS:
            a, b = curve[lo][key], curve[hi][key]
            rate = (b / a) ** (1 / span) if a > 0 and span else 1.0
            out[key] = int(b * (rate ** (target - hi)))
        return out
    lo = max(l for l in levels if l <= target)
    hi = min(l for l in levels if l >= target)
    if lo == hi:
        return dict(curve[lo])
    t = (target - lo) / (hi - lo)
    return {key: int(curve[lo][key] + t * (curve[hi][key] - curve[lo][key]))
            for key in STATS + REWARDS}


def reference_band(curve, levels, lo=45, hi=47):
    """The vanilla endgame enemy profile - what the shipped bosses were balanced against."""
    band = [curve[l] for l in levels if lo <= l <= hi]
    if not band:
        band = [curve[levels[-1]]]
    return {k: sum(b[k] for b in band) / len(band) for k in band[0]}


def boss_sets(p):
    eg = uasset.read_datatable(p.read("Octopath_Traveler/Content/Battle/Database/EnemyGroupData.uasset"),
                               p.read("Octopath_Traveler/Content/Battle/Database/EnemyGroupData.uexp"))
    ids = set()
    for v in eg.values():
        if g(v, "BossBattle"):
            for e in g(v, "EnemyID"):
                if e and e != "None":
                    ids.add(e)
    supers = {k for k in ids if k.startswith(SUPERBOSS_PREFIXES)}
    return ids, supers


NPC_BATTLES = "Octopath_Traveler/Content/Character/Database/NPCBattleData"
ENEMY_GROUPS = "Octopath_Traveler/Content/Battle/Database/EnemyGroupData"
ENCOUNTERS = "Octopath_Traveler/Content/Battle/Database/BattleEncounterData"
INVADE = "Octopath_Traveler/Content/Ability/Database/InvadeData"
BOSS_PREFIXES = ("BOS_", "EVE_")


def enemy_classes(p, rows):
    """Classify every EnemyDB row by how the game actually reaches it.

      random    - in a group that an area's EncounterList can roll (the only rows scaled
                  to the world floor)
      npc       - opponent in a Provoke / Challenge fight (NPCBattleData); kept as shipped
      cat       - cait-type (UseCatDamageType: always takes 1 damage, 4-80 HP); kept as
                  shipped, or they become unkillable
      boss      - in a BossBattle group, OR a BOS_/EVE_ row in no group at all (phases and
                  minions a boss summons mid-fight), scaled with the bosses
      super     - superboss prefixes
      other     - anything else; kept as shipped

    The previous rule was "everything that is not a boss is a regular enemy", which also
    caught the 622 NPC opponents, the caits and 34 boss phases.
    """
    def table(path):
        return uasset.read_datatable(p.read(path + ".uasset"), p.read(path + ".uexp"))
    eg = table(ENEMY_GROUPS)
    be = table(ENCOUNTERS)
    vol = table(VOLUME)
    nb = table(NPC_BATTLES)

    def members(groups):
        return {e for gid in groups if gid in eg for e in g(eg[gid], "EnemyID")
                if e and e != "None"}
    rolls = {g(e, "EncounterName") for v in vol.values() for e in g(v, "EncounterList")}
    random_groups = {g(x, "GroupID") for n in rolls if n in be for x in g(be[n], "Group")}
    random_ids = members(random_groups)
    npc_ids = members({g(v, "EnemyGroupID") for v in nb.values()})
    grouped = members(set(eg))
    bosses, supers = boss_sets(p)
    out = {}
    for k, v in rows.items():
        if k in supers or (k not in grouped and k.startswith(SUPERBOSS_PREFIXES)):
            out[k] = "super"
        elif k in bosses or (k not in grouped and k.startswith(BOSS_PREFIXES)):
            out[k] = "boss"
        elif k in npc_ids:
            out[k] = "npc"                 # NPC use wins over any random-group overlap
        elif g(v, "UseCatDamageType"):
            out[k] = "cat"
        elif k in random_ids:
            out[k] = "random"
        else:
            out[k] = "other"
    return out


def build(out_path=None, save_path=None, verbose=True, pack=True):
    log = buildlog.get()
    global print
    print = lambda *a, **k: log.info(" ".join(str(x) for x in a))
    p = pak.Pak(paths.base_pak())
    save, progress = quests_done(save_path)
    party_lv = party_level(save)
    global LAST_COMPLETION
    done = LAST_COMPLETION = completion(save)
    floor, why = world_floor(progress, party_lv, done["share"])
    if verbose and COMPLETION_FLOOR > 0:
        print("completion: " + ", ".join(f"{k.replace('_', ' ')} {done[k]}/{done['totals'][k]}"
                                         for k in COMPLETION_WEIGHTS) + f" -> {done['share']:.1%}")
    if verbose and SET_ENEMY_LEVEL == "party":
        print(f"party average level {party_lv}: enemy and boss levels raised to at least "
              f"{round(party_lv * ENEMY_LEVEL_WEIGHT)}")
    if verbose:
        print(f"save {os.path.basename(save)}: {progress // PROGRESS_PER_QUEST} chapters done, party level "
              f"{party_lv} -> world danger floor {floor} (max of {why})")

    # ---------------- EnemyDB ----------------
    ua = p.read(ENEMY + ".uasset")
    ue = bytearray(p.read(ENEMY + ".uexp"))
    rows = uasset.read_datatable(ua, bytes(ue))
    keys = list(rows)
    bosses, supers = boss_sets(p)
    curve, levels = build_curve(rows, bosses)
    target = profile_at(curve, levels, floor)
    # what enemies PAY: money at the floor, EXP / JP only part of the way past the story
    reward_floor = floor
    if floor > STORY_FLOOR:
        reward_floor = int(round(STORY_FLOOR + REWARD_SHARE * (floor - STORY_FLOOR)))
    pay = dict(target)
    growth = profile_at(curve, levels, reward_floor)
    for f in GROWTH_REWARDS:
        pay[f] = growth[f]
    if verbose:
        print(f"target profile @ danger {floor}: " +
              ", ".join(f"{k}={target[k]}" for k in STATS))
        print(f"               rewards: " + ", ".join(f"{k}={pay[k]}" for k in REWARDS)
              + (f" (EXP/JP as at danger {reward_floor})" if reward_floor != floor else ""))

    fields = STATS + REWARDS + (["EnemyLevel"] if SET_ENEMY_LEVEL else [])
    offs = {f: int_offsets(ua, bytes(ue), f, expect=len(rows)) for f in fields}
    # verify offsets line up with the parsed table before touching anything
    for f in STATS:
        vals = [struct.unpack_from("<i", ue, o)[0] for o in offs[f]]
        if vals != [g(g(rows[k], "Param"), f) for k in keys]:
            raise RuntimeError(f"{f}: offsets do not match parsed values")
    for f in REWARDS:
        vals = [struct.unpack_from("<i", ue, o)[0] for o in offs[f]]
        if vals != [g(rows[k], f) for k in keys]:
            raise RuntimeError(f"{f}: offsets do not match parsed values")

    # money ratio against the vanilla endgame, for Tressa's Collect talent
    ref = reference_band(curve, levels)
    money_ratio = target["Money"] / ref["Money"] if ref.get("Money") else 1.0
    cls = enemy_classes(p, rows)
    natives = boss_natives(p, rows, cls, curve, levels)
    hard_only, hard_at, hard_pay = set(), None, None
    if HARD_AREA_DISPLAY:
        hard_only = hard_area_enemies(p, cls)
        hard_at = profile_at(curve, levels, hard_danger(floor))
        hard_pay = dict(hard_at)
        grown = profile_at(curve, levels, reward_floor + hard_danger(floor) - floor)
        for f in GROWTH_REWARDS:
            hard_pay[f] = grown[f]

    level_to = round(party_lv * ENEMY_LEVEL_WEIGHT) if SET_ENEMY_LEVEL == "party" else floor

    def set_level(i):
        """Enemy level drives BATTLE_DAMAGE_LEVEL_RATIO (4%/level, capped 3.1x)."""
        if not SET_ENEMY_LEVEL:
            return
        o = offs["EnemyLevel"][i]
        old = struct.unpack_from("<i", ue, o)[0]
        if 0 < old < level_to:           # leave the -100/0 sentinel rows alone
            struct.pack_into("<i", ue, o, level_to)
            expected.add(o)

    def scale_boss(i, extra_hp=1.0, extra_all=1.0, to=None):
        """Scale a boss by how far the world has moved past the danger it was built for,
        per stat; extra_hp always applies (the preset's boss HP bonus). to = a profile to
        scale to instead of the world's (fixed-danger final boss)."""
        native = profile_at(curve, levels, natives[keys[i]])
        for f in STATS + (REWARDS if SCALE_REWARDS else []):
            o = offs[f][i]
            old = struct.unpack_from("<i", ue, o)[0]
            if old <= 0:
                continue
            want = to[f] if to else (pay[f] if f in REWARDS else target[f])
            world = max(1.0, want / native[f]) if native.get(f) else 1.0
            mult = world * extra_all * (extra_hp if f == "HP" else 1.0)
            new = max(old, int(old * mult))
            if new != old:
                struct.pack_into("<i", ue, o, new)
                expected.add(o)
        set_level(i)

    touched = {"regular": 0, "boss": 0, "superboss": 0, "superboss_untouched": 0,
               "npc": 0, "cat": 0, "other": 0}
    expected = set()
    scaled_regular = set()
    for i, k in enumerate(keys):
        c = cls[k]
        if c in ("npc", "cat", "other") or not SCALE_WORLD:
            touched[c if c in touched else "other"] += 1     # exactly as shipped
            continue
        if c == "super":
            # superbosses scale only once the world passes the danger they were built for
            pin = None
            if FINAL_BOSS_DANGER and k.startswith(FINAL_BOSS_PREFIX):
                pin = FINAL_BOSS_DANGER
            elif REVENANT_MIN_DANGER > floor and k.startswith(REVENANT_PREFIX):
                pin = REVENANT_MIN_DANGER
            elif HARD_AREA_DISPLAY and k.startswith(HARD_AREA_SUPERBOSSES):
                pin = hard_danger(floor)
            scale_boss(i, extra_hp=SUPERBOSS_HP_MULT, extra_all=SUPERBOSS_EXTRA,
                       to=profile_at(curve, levels, pin) if pin else None)
            touched["superboss"] += 1
            continue
        if c == "boss":
            if SCALE_BOSSES:
                scale_boss(i, extra_hp=BOSS_HP_MULT)
            else:
                o = offs["HP"][i]
                old = struct.unpack_from("<i", ue, o)[0]
                struct.pack_into("<i", ue, o, int(old * BOSS_HP_MULT))
                expected.add(o)
            touched["boss"] += 1
            continue
        set_level(i)
        changed = False
        for f in (STATS if FLOOR_ACTIVE else []):
            o = offs[f][i]
            old = struct.unpack_from("<i", ue, o)[0]
            if old <= 0:                      # 0 means "not used" for some rows; leave it
                continue
            new = max(old, (hard_at if k in hard_only else target)[f])
            if new != old:
                struct.pack_into("<i", ue, o, new)
                expected.add(o)
                changed = True
        if changed:
            scaled_regular.add(k)
        if SCALE_REWARDS and changed:
            for f in REWARDS:
                o = offs[f][i]
                old = struct.unpack_from("<i", ue, o)[0]
                if old <= 0:
                    continue
                new = max(old, (hard_pay if k in hard_only else pay)[f])
                if new != old:
                    struct.pack_into("<i", ue, o, new)
                    expected.add(o)
        touched["regular"] += 1
    if verbose:
        behind = sum(1 for k in keys if cls[k] in ("boss", "super") and natives[k] < floor)
        print(f"enemies: {touched['regular']} regular raised to danger {floor}; "
              f"{touched['boss']} bosses and {touched['superboss']} superbosses scaled from "
              f"their native danger ({behind} built for less than {floor}), extra HP "
              f"x{BOSS_HP_MULT} / x{SUPERBOSS_HP_MULT}")
        if HARD_AREA_DISPLAY:
            print(f"hard areas fought at danger {hard_danger(floor)}: "
                  f"{len(hard_only)} regular enemies found only there and the optional "
                  f"superbosses ({', '.join(HARD_AREA_SUPERBOSSES)})")
        print(f"         left as shipped: {touched['npc']} Provoke/Challenge opponents, "
              f"{touched['cat']} caits, {touched['other']} unreachable rows")

    orig = p.read(ENEMY + ".uexp")
    assert len(ue) == len(orig), "EnemyDB size changed"
    diff = {i for i in range(len(orig)) if orig[i] != ue[i]}
    stray = diff - {o + d for o in expected for d in range(4)}
    assert not stray, f"unexpected bytes changed in EnemyDB: {sorted(stray)[:8]}"
    after = uasset.read_datatable(ua, bytes(ue))      # must still parse
    assert list(after) == keys, "EnemyDB row set changed"

    # ---------------- InvadeData (H'aanit's summons) ----------------
    # A captured beast is saved as just an enemy ID; when summoned, its stats come from
    # InvadeData as PERCENTAGES OF H'AANIT'S OWN STATS (vanilla: 133% for a level-1 beast up
    # to 657% at 58+). The enemy scaling above never reaches them, so a beast caught in a
    # now-dangerous area would summon at its vanilla strength. Floor-raise the summon of
    # every scaled, capturable enemy to what a vanilla beast of the world level gets - the
    # same rule the enemies follow - so harder enemies stay harder hitters when summoned.
    files_invade = {}
    summons_raised = 0
    if SCALE_SUMMONS and SCALE_WORLD:
        iua = p.read(INVADE + ".uasset")
        iue = bytearray(p.read(INVADE + ".uexp"))
        inv = uasset.read_datatable(iua, bytes(iue))
        ikeys = list(inv)
        ioffs = {f: int_offsets(iua, bytes(iue), f, expect=len(inv)) for f in SUMMON_STATS}
        for f in SUMMON_STATS:
            vals = [struct.unpack_from("<i", iue, o)[0] for o in ioffs[f]]
            if vals != [g(g(inv[k], "Parameter"), f) for k in ikeys]:
                raise RuntimeError(f"InvadeData {f}: offsets do not match parsed values")
        # vanilla curve: source enemy level -> median summon %, made non-decreasing
        by_lvl = {}
        for k, v in rows.items():
            iid = g(v, "InvadeMonsterID")
            if g(v, "TameEnable") and iid in inv and g(v, "EnemyLevel") >= 1:
                by_lvl.setdefault(g(v, "EnemyLevel"), []).append(g(inv[iid], "Parameter"))
        scurve = {}
        run = {f: 0 for f in SUMMON_STATS}
        for lv in sorted(by_lvl):
            for f in SUMMON_STATS:
                run[f] = max(run[f], int(statistics.median(g(x, f) for x in by_lvl[lv])))
            scurve[lv] = dict(run)
        top = max(scurve)
        if floor <= top:
            want = scurve[max(l for l in scurve if l <= floor)]
        else:
            # past the authored range, grow with enemy attack like everything else
            grow = target["ATK"] / max(1, profile_at(curve, levels, top)["ATK"])
            want = {f: int(scurve[top][f] * grow) for f in SUMMON_STATS}
        idx = {k: i for i, k in enumerate(ikeys)}
        iexp = set()
        for k in sorted(scaled_regular):
            v = rows[k]
            iid = g(v, "InvadeMonsterID")
            if not g(v, "TameEnable") or iid not in idx:
                continue
            raised = False
            for f in SUMMON_STATS:
                o = ioffs[f][idx[iid]]
                old = struct.unpack_from("<i", iue, o)[0]
                if old <= 0:
                    continue
                new = max(old, want[f])
                if new != old:
                    struct.pack_into("<i", iue, o, new)
                    iexp.add(o)
                    raised = True
            summons_raised += raised
        origi = p.read(INVADE + ".uexp")
        diffi = {i for i in range(len(origi)) if origi[i] != iue[i]}
        assert not diffi - {o + d for o in iexp for d in range(4)}, "stray InvadeData bytes"
        assert list(uasset.read_datatable(iua, bytes(iue))) == ikeys
        files_invade = {INVADE + ".uasset": iua, INVADE + ".uexp": bytes(iue)}
        if verbose:
            print(f"summons: {summons_raised} captured-beast summons raised to at least "
                  f"{want['ATK']}% of H'aanit's Atk (vanilla range 133-657%)")

    # ---------------- EncountVolumeData ----------------
    ua2 = p.read(VOLUME + ".uasset")
    ue2 = bytearray(p.read(VOLUME + ".uexp"))
    vols = uasset.read_datatable(ua2, bytes(ue2))
    flat = [(k, e) for k, v in vols.items() for e in g(v, "EncounterList")]
    doffs = int_offsets(ua2, bytes(ue2), "DangerLevel", expect=len(flat))
    vals = [struct.unpack_from("<i", ue2, o)[0] for o in doffs]
    if vals != [g(e, "DangerLevel") for _k, e in flat]:
        raise RuntimeError("DangerLevel offsets do not match parsed values")

    exp2 = set()
    bumped = hard = 0

    # bake Evasive Maneuvers in permanently by stretching the step counts
    if PERMANENT_EVASIVE_MANEUVERS:
        mult = ENCOUNTER_STEP_MULT
        if mult is None:
            bp = uasset.read_datatable(p.read(BATTLE_PARAMS + ".uasset"),
                                       p.read(BATTLE_PARAMS + ".uexp"))
            row = bp.get("EX_EVASION_UP_FIELD_RATIO")
            mult = float(next(vv for kk, vv in row.items()
                              if kk.split("_")[0] == "Param")) if row else 2.0
            if mult <= 1.0:
                mult = 2.0
        steps_changed = 0
        for field in ENCOUNTER_STEP_FIELDS:
            soffs = int_offsets(ua2, bytes(ue2), field, expect=len(vols))
            for o in soffs:
                old = struct.unpack_from("<i", ue2, o)[0]
                if old <= 0:
                    continue
                new = int(round(old * mult))
                if new != old:
                    struct.pack_into("<i", ue2, o, new)
                    exp2.add(o)
                    steps_changed += 1
        if verbose:
            print(f"evasive maneuvers: encounter steps x{mult:g} baked in "
                  f"({steps_changed} values across {len(vols)} areas) - no skill slot needed")

    # hard/optional areas stay a step above the rest of the world, never below it
    hard_target = hard_danger(floor)
    hard_display = HARD_AREA_DISPLAY
    for (k, e), o in zip(flat, doffs):
        old = struct.unpack_from("<i", ue2, o)[0]
        if old <= 0:                      # unused tier slot
            continue
        if not SCALE_WORLD:
            continue
        new = (hard_target if hard_display and old >= HARD_AREA_THRESHOLD
               else max(old, floor))
        if new != old:
            struct.pack_into("<i", ue2, o, new)
            exp2.add(o)
            hard += hard_display and old >= HARD_AREA_THRESHOLD
            bumped += 1
    if verbose:
        print(f"areas: {bumped} danger values raised ({hard} hard/optional tiers -> {hard_target})")

    orig2 = p.read(VOLUME + ".uexp")
    assert len(ue2) == len(orig2), "EncountVolumeData size changed"
    diff2 = {i for i in range(len(orig2)) if orig2[i] != ue2[i]}
    stray2 = diff2 - {o + d for o in exp2 for d in range(4)}
    assert not stray2, "unexpected bytes changed in EncountVolumeData"
    after2 = uasset.read_datatable(ua2, bytes(ue2))
    assert list(after2) == list(vols), "volume row set changed"
    for (k, v) in after2.items():          # DisplayLevel must be untouched
        for a, b in zip(g(v, "EncounterList"), g(vols[k], "EncounterList")):
            assert g(a, "DisplayLevel") == g(b, "DisplayLevel"), f"{k}: DisplayLevel moved"

    # ---------------- gear (ItemDB) ----------------
    gear_mult = 1.0
    if SCALE_EXISTING_GEAR and floor > GEAR_FROM_DANGER:
        ratio = profile_at(curve, levels, floor)["ATK"] / profile_at(curve, levels, GEAR_FROM_DANGER)["ATK"]
        gear_mult = 1 + (ratio - 1) * GEAR_CATCHUP
    ua3 = p.read(ITEMS + ".uasset")
    ue3 = bytearray(p.read(ITEMS + ".uexp"))
    items = uasset.read_datatable(ua3, bytes(ue3))
    ikeys = list(items)
    exp3 = set()
    gear_touched = 0
    if gear_mult > 1.0:
        goffs = {f: int_offsets(ua3, bytes(ue3), f, expect=len(items), exact=True)
                 for f in EQUIP_FIELDS}
        for f in EQUIP_FIELDS:
            vals = [struct.unpack_from("<i", ue3, o)[0] for o in goffs[f]]
            parsed = [g(items[k], "EquipmentRevision")[f] for k in ikeys]
            if vals != parsed:
                raise RuntimeError(f"ItemDB {f}: offsets do not match parsed values")
        for i, _k in enumerate(ikeys):
            bumped_any = False
            for f in EQUIP_FIELDS:
                o = goffs[f][i]
                old = struct.unpack_from("<i", ue3, o)[0]
                if old <= 0:          # leave drawbacks (negative stats) alone
                    continue
                new = int(round(old * gear_mult))
                if new != old:
                    struct.pack_into("<i", ue3, o, new)
                    exp3.add(o)
                    bumped_any = True
            gear_touched += bumped_any
        orig3 = p.read(ITEMS + ".uexp")
        assert len(ue3) == len(orig3), "ItemDB size changed"
        diff3 = {i for i in range(len(orig3)) if orig3[i] != ue3[i]}
        stray3 = diff3 - {o + d for o in exp3 for d in range(4)}
        assert not stray3, "unexpected bytes changed in ItemDB"
        after3 = uasset.read_datatable(ua3, bytes(ue3))
        assert list(after3) == ikeys, "ItemDB row set changed"
    if verbose and SCALE_EXISTING_GEAR:
        print(f"gear: x{gear_mult:.2f} on {gear_touched} pieces of equipment")

    # ---------------- global tunables ----------------
    # Which column the engine reads is ambiguous in this debug-style table, so set both
    # Init and Param on every row we touch.
    # row -> {column: value}. The *_RANGE rows keep their limit in the Max column.
    wanted = {}
    if RAISE_DAMAGE_CAP:
        wanted["BATTLE_DAMAGE_CAP"] = {"Init": DAMAGE_CAP, "Param": DAMAGE_CAP}
    if PERMANENT_EVASIVE_MANEUVERS:
        wanted["MAX_ENCOUNT_STEP_COUNT"] = {"Init": ENCOUNT_STEP_CEILING,
                                           "Param": ENCOUNT_STEP_CEILING}
    if PLAYER_STAT_CAP != 999:
        wanted["PLAYER_STATUS_RANGE"] = {"Max": PLAYER_STAT_CAP}
    if PLAYER_HP_CAP != 9999:
        wanted["PLAYER_STATUS_HP_RANGE"] = {"Max": PLAYER_HP_CAP}
    if STEAL_LEVEL_SHIFT and SET_ENEMY_LEVEL:
        gpd = uasset.read_datatable(p.read(PARAMS + ".uasset"), p.read(PARAMS + ".uexp"))
        for row in ("STEAL_PROBABILITY_LEVEL_OVER", "STEAL_PROBABILITY_LEVEL_LESS_THAN"):
            wanted[row] = {col: int(g(gpd[row], col)) - STEAL_LEVEL_SHIFT
                           for col in ("Min", "Max", "Init")}
    files_params = {}
    if wanted:
        pua2 = p.read(PARAMS + ".uasset")
        pue2 = p.read(PARAMS + ".uexp")
        pnames, _ = uasset.names_of(pua2)
        for row_name, cols in wanted.items():
            spans = {s[0]: s for s in dt.row_spans(pua2, pue2)}
            if row_name not in spans:
                raise RuntimeError(f"{row_name} not found in {PARAMS}")
            _nm, _i, _n, s0, e0 = spans[row_name]
            row = pue2[s0:e0]
            for col, value in cols.items():
                row = dt.set_str_field(row, pnames, col, str(value))
            pua2, pue2 = dt.replace_row(pua2, pue2, row_name, row)
            dt.verify(pua2, pue2)
        back = uasset.read_datatable(pua2, pue2)
        for row_name, cols in wanted.items():
            got = {kk.split("_")[0]: vv for kk, vv in back[row_name].items()}
            assert all(got[c] == str(v) for c, v in cols.items()), (row_name, got)
            if verbose:
                print(f"tunable {row_name} -> " +
                      ", ".join(f"{c}={v:,}" for c, v in cols.items()))
        files_params = {PARAMS + ".uasset": pua2, PARAMS + ".uexp": pue2}

    # ---------------- catch-up leveling (CharacterGrowData) ----------------
    files_grow = {}
    cheapen = catchup_divisor()
    if CATCHUP_LEVELING and cheapen <= 1.0 and verbose:
        print("catch-up leveling: off during the vanilla opening (levels cost as shipped)")
    if CATCHUP_LEVELING and cheapen > 1.0:
        # Built on the copy the game would otherwise load: Larger Monster Roster, for one,
        # raises H'aanit's capture limit (FCParameter.TameCount) in this same table.
        gua, gue_in, grow_src = paths.installed_asset(GROW, p)
        gue = bytearray(gue_in)
        if verbose and grow_src != "base game":
            print(f"catch-up leveling: built on {grow_src}'s CharacterGrowData (its changes kept)")
        grow = uasset.read_datatable(gua, bytes(gue))
        gkeys = list(grow)
        tot_offs = int_offsets(gua, bytes(gue), "TotalExp", expect=len(grow))
        nxt_offs = int_offsets(gua, bytes(gue), "NextExp", expect=len(grow))
        tot = [g(grow[k], "TotalExp") for k in gkeys]
        if [struct.unpack_from("<i", gue, o)[0] for o in tot_offs] != tot:
            raise RuntimeError("TotalExp offsets do not match parsed values")
        lv = [int(k) for k in gkeys]
        threshold = catchup_threshold(save)

        def factor(level):
            return 1.0 if level >= threshold else 1.0 / cheapen
        new_tot = [int(round(t * factor(L))) for t, L in zip(tot, lv)]
        assert all(b > a for a, b in zip(new_tot, new_tot[1:])), "EXP table not increasing"
        gexp = set()
        for i in range(len(gkeys)):
            if new_tot[i] != tot[i]:
                struct.pack_into("<i", gue, tot_offs[i], new_tot[i])
                gexp.add(tot_offs[i])
            if i + 1 < len(gkeys):
                nx = new_tot[i + 1] - new_tot[i]
                if nx != struct.unpack_from("<i", gue, nxt_offs[i])[0]:
                    struct.pack_into("<i", gue, nxt_offs[i], nx)
                    gexp.add(nxt_offs[i])
        origg = gue_in
        diffg = {i for i in range(len(origg)) if origg[i] != gue[i]}
        assert not diffg - {o + d for o in gexp for d in range(4)}, "stray CharacterGrowData bytes"
        assert list(uasset.read_datatable(gua, bytes(gue))) == gkeys
        files_grow = {GROW + ".uasset": gua, GROW + ".uexp": bytes(gue)}
        if verbose:
            cheap = [L for L, a, b in zip(lv, tot, new_tot) if b < a]
            print(f"catch-up leveling: levels {min(cheap) if cheap else '-'}-"
                  f"{max(cheap) if cheap else '-'} cost {cheapen:.2g}x less EXP; "
                  f"level {threshold}+ unchanged (top active party level {threshold + CATCHUP_MARGIN})")

    # ---------------- Tressa's Collect talent ----------------
    files_bparams = {}
    if SCALE_TRESSA_COLLECT:
        ratio = max(1.0, money_ratio)
        bua = p.read(BATTLE_PARAMS + ".uasset")
        bue = p.read(BATTLE_PARAMS + ".uexp")
        bnames, _ = uasset.names_of(bua)
        before = uasset.read_datatable(bua, bue)
        newvals = {}
        for row_name in TRESSA_COLLECT_ROWS:
            if row_name not in before:
                raise RuntimeError(f"{row_name} not found in {BATTLE_PARAMS}")
            old = float(g(before[row_name], "Param"))
            newvals[row_name] = str(int(round(old * ratio)))
            # Max is exactly Param / 20 in every shipped row; which column the game reads
            # isn't visible in data, so keep both in step
            new_max = str(int(round(float(g(before[row_name], "Max")) * ratio)))
            spans = {sp[0]: sp for sp in dt.row_spans(bua, bue)}
            _nm, _i, _n, s0, e0 = spans[row_name]
            row = dt.set_str_field(bue[s0:e0], bnames, "Param", newvals[row_name])
            row = dt.set_str_field(row, bnames, "Max", new_max)
            bua, bue = dt.replace_row(bua, bue, row_name, row)
            dt.verify(bua, bue)
        back = uasset.read_datatable(bua, bue)
        for k in before:
            if k in newvals:
                assert g(back[k], "Param") == newvals[k], (k, back[k])
            else:
                assert str(back[k]) == str(before[k]), f"{k} changed unexpectedly"
        files_bparams = {BATTLE_PARAMS + ".uasset": bua, BATTLE_PARAMS + ".uexp": bue}
        if verbose:
            lo, hi = TRESSA_COLLECT_ROWS[0], TRESSA_COLLECT_ROWS[-1]
            print(f"tressa collect: x{ratio:.2f} -> {newvals[lo]}..{newvals[hi]} leaves "
                  f"(vanilla {float(g(before[lo], 'Param')):g}..{float(g(before[hi], 'Param')):g})")

    # ---------------- pack ----------------
    out_path = out_path or os.path.join(paths.mods_dir(), OUT_NAME)
    files = {ENEMY + ".uasset": ua, ENEMY + ".uexp": bytes(ue),
             VOLUME + ".uasset": ua2, VOLUME + ".uexp": bytes(ue2)}
    files.update(files_params)
    files.update(files_invade)
    files.update(files_bparams)
    files.update(files_grow)
    if gear_mult > 1.0:
        files[ITEMS + ".uasset"] = ua3
        files[ITEMS + ".uexp"] = bytes(ue3)
    if not pack:
        return files, floor, target, gear_mult
    size = pakwrite.write_pak(out_path, files)
    q = pak.Pak(out_path)
    for n, data in files.items():
        assert q.read(n) == data, f"pak round-trip failed for {n}"
    if verbose:
        print(f"wrote {out_path} ({size:,} bytes), {len(q.entries)} files, re-read OK")
    return out_path, floor, target, gear_mult


def preview(target, floor):
    print(f"\n--- what a random encounter looks like at danger {floor} ---")
    print(f"  weakest enemies become: {target['HP']:,} HP, {target['ATK']} Atk, "
          f"{target['DEF']} Def")
    print(f"  a 3-enemy pack is ~{target['HP'] * 3:,} HP")
    print(f"  payout per enemy: {target['Exp']} EXP, {target['JobPoint']} JP, "
          f"{target['Money']} leaves")


if __name__ == "__main__":
    buildlog.setup("difficulty")
    out = sys.argv[1] if len(sys.argv) > 1 else None
    _path, floor, target, gear = build(out)
    preview(target, floor)
    if gear > 1:
        print(f"  gear multiplier in effect: x{gear:.2f} "
              f"(e.g. a 400 Atk weapon becomes {int(400 * gear)})")
