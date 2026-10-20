"""overhaul.ini: difficulty preset, feature switches and individual overrides.

Presets bundle the balance values; anything set under [tuning] overrides the preset, and
[features] turns whole systems on or off. config.apply() pushes the result into the build
modules' settings before a build.
"""
import configparser
import os

import paths

PRESETS = {
    # Vanilla balance, plus the new gear, QoL and caps. The world floor never runs ahead of
    # where the story normally is.
    "classic": dict(progress_margin=0, party_margin=None, legacy_floor=False,
                    boss_hp_mult=1.0, superboss_hp_mult=1.0, enemy_level="vanilla",
                    hard_area_display=False, completion_floor=0.0,
                    final_boss_danger=0, revenant_min_danger=0),
    # Default. A little above vanilla's own curve, and never below the party's level, so a
    # party that out-levels the story meets enemies that keep up.
    "adaptive": dict(progress_margin=2, party_margin=0, legacy_floor=False,
                     boss_hp_mult=1.25, superboss_hp_mult=1.25, enemy_level="party",
                     hard_area_display=False, completion_floor=0.0,
                     final_boss_danger=0, revenant_min_danger=0),
    # Adaptive through the mid game, then a step harder for a strong endgame party: enemies
    # at least party level + 4, bosses x2 HP, superbosses x4. (The original 8 + 3 per
    # chapter curve is still available as legacy_floor = true, but it punished the mid game.)
    "relentless": dict(progress_margin=5, party_margin=4, legacy_floor=False,
                       boss_hp_mult=2.0, superboss_hp_mult=4.0, enemy_level="party",
                       hard_area_display=True, completion_floor=1.0,
                       final_boss_danger=104, revenant_min_danger=94),
}

# The opening of every preset: the chapter 1s play as vanilla (user 2026-10-04: "keep a more
# vanilla curve at the start ... we don't want HP up in early game"). Areas more than 10
# danger behind the story are still raised so old haunts don't become trivial.
VANILLA_START = dict(progress_margin=-10, party_margin=None, legacy_floor=False,
                     boss_hp_mult=1.0, superboss_hp_mult=1.0, enemy_level="vanilla",
                     hard_area_display=False, completion_floor=0.0)
# Stages (see build_difficulty_mod.stage_of): 12 = chapter 1s done, 30 = into the chapter
# 3s, 40-50 = chapter 4s and the finale.
RAMP_START = 12
RAMP_FULL = 30
RELENTLESS_FROM = 40
RELENTLESS_FULL = 50


def ramp(cfg):
    """(stage, settings) anchors for build_difficulty_mod.RAMP, or None for no ramp."""
    if not cfg.get("vanilla_start", True):
        return None
    keys = list(VANILLA_START)

    def norm(d):
        d = {k: d.get(k, 0.0) for k in keys}
        d["enemy_level"] = 1.0 if d["enemy_level"] == "party" else 0.0
        return d
    full = norm(cfg)
    if cfg["preset"] == "relentless":
        mid = norm(PRESETS["adaptive"])
        return [(RAMP_START, norm(VANILLA_START)), (RAMP_FULL, mid),
                (RELENTLESS_FROM, mid), (RELENTLESS_FULL, full)]
    return [(RAMP_START, norm(VANILLA_START)), (RAMP_FULL, full)]


FEATURES = {
    "scale_world": True,          # enemies, bosses, rewards, area danger
    "new_gear": True,             # the tiered gear in Grandport + rare drops
    "fast_travel": True,          # fast travel to every VISITED location
    "fewer_encounters": True,     # Evasive Maneuvers baked in (x2 steps between fights)
    "raise_damage_cap": True,     # 999,999 instead of 9,999
    "raise_stat_caps": True,      # stats 9,999 and HP 99,999 instead of 999 / 9,999
    "catch_up_leveling": True,    # benched travelers level up to 5x cheaper (mid game on)
    "scale_summons": True,        # H'aanit's captured beasts keep pace
    "scale_tressa_collect": True,
    "consumable_upgrades": True,  # consumable drops / steals climb with the world
    "toggle_dash": False,         # dash button toggles running instead of hold-to-run
    "scale_skills": True,         # fixed HP/SP restores of party skills grow with the world
    "party_runes": True,          # the Runelord's elemental runes enchant the whole party
    "journal_hints": True,        # side-story journal entries: step-by-step walkthroughs
}

DEFAULT_INI = """\
; Octopath Traveler - World Overhaul settings.
; Changes take effect the next time you launch the game (Steam Play button or the desktop shortcut).

[general]
; Every preset plays the chapter 1s as vanilla and builds up through the mid game.
; classic    - vanilla difficulty curve, plus the new gear, caps and quality of life
; adaptive   - a little harder than vanilla, and enemies never fall below your party level
; relentless - adaptive, then a step harder from the chapter 4s: enemies above your
;              party's level, bosses x2 HP, superbosses x4
preset = adaptive
; Which save the world is built for. "ask" shows a picker at launch (pick the save you
; will load!); "newest" always uses the most recently saved slot.
save_choice = ask
; seconds before the picker continues with the highlighted save
ask_timeout = 20
; How travelers far below your party catch up (needs catch_up_leveling = true):
;   table - levels below your leaders cost up to 5x less EXP; your save is never touched,
;           but a traveler who levelled cheaply owes the difference at the first normal
;           level, so they settle ~3 levels behind your leaders
;   save  - before the game starts, anyone more than 5 levels behind your highest active
;           traveler gets their EXP raised to that level's normal total; the game hands out
;           the levels after their next battle. Writes the save (backed up first; only the
;           EXP numbers change).
catch_up = table
; While you play, show a banner when your progress would make the world grow (it changes
; at the next launch). Set the game to borderless fullscreen to see it over the game:
; nothing can draw over exclusive fullscreen.
world_notice = true
; Mark side stories you haven't started: their giver is named "<name>" plus the leaf, and
; the world map shows the leaf (or leaf 3 for three) after the place's name. Updated at
; each launch. auto = once you've finished side_story_markers_from chapters (24 = every
; chapter 3); on / off = always / never. The save picker's checkbox sets on / off.
side_story_markers = auto
side_story_markers_from = 24
; Leave empty to auto-detect.
game_dir =
save_dir =

[features]
scale_world = true
new_gear = true
fast_travel = true
fewer_encounters = true
raise_damage_cap = true
raise_stat_caps = true
catch_up_leveling = true
scale_summons = true
scale_tressa_collect = true
consumable_upgrades = true
; press dash once to run, again to walk (instead of holding the button)
toggle_dash = false
; party skills that restore a fixed amount (concoctions, Rest, helpers) grow with the world
scale_skills = true
; the Runelord's six elemental runes enchant the whole party (Transfer Rune unchanged)
party_runes = true
; side-story journal entries become step-by-step walkthroughs (who, where, region)
journal_hints = true

[tuning]
; true = the chapter 1s play as vanilla and the preset's values below build up through
; the mid game; false = full strength from the start.
vanilla_start = true
; Leave empty to use the preset's value (its full, late-game strength).
progress_margin =
party_margin =
boss_hp_mult =
superboss_hp_mult =
; How much of the party-driven part of the world EXP and JP follow (0..1, default 0.5).
; Enemies always keep up with your party; at 1.0 they also pay full at-level EXP, so an
; out-levelled party never slows down. Money always pays in full.
reward_share =
; party or vanilla
enemy_level =
max_danger =

[legacy]
; Only for saves made with early test builds that bought the "Cap Test Charm".
cap_test_charm = false
"""


def ini_path():
    return os.path.join(paths.app_dir(), "overhaul.ini")


def set_general(key, value):
    """Write one [general] setting into overhaul.ini, keeping every other line (and its
    comments) as it is; adds the line if it's missing."""
    import re
    p = ini_path()
    if not os.path.exists(p):
        load()
    with open(p, encoding="utf-8-sig") as f:
        text = f.read()
    line = f"{key} = {value}"
    pat = re.compile(rf"^{re.escape(key)}\s*=.*$", re.M)
    if pat.search(text):
        text = pat.sub(line, text, count=1)
    elif re.search(r"^\[general\][^\n]*\n", text, re.M):
        text = re.sub(r"^\[general\][^\n]*\n", lambda m: m.group(0) + line + "\n", text,
                      count=1, flags=re.M)
    else:
        text = f"[general]\n{line}\n\n" + text
    with open(p, "w", encoding="utf-8") as f:
        f.write(text)


def load():
    p = ini_path()
    if not os.path.exists(p):
        try:
            with open(p, "w", encoding="utf-8") as f:
                f.write(DEFAULT_INI)
        except OSError:
            pass
    cp = configparser.ConfigParser()
    cp.read_string(DEFAULT_INI)
    if os.path.exists(p):
        # utf-8-sig: Notepad (older Windows) saves a byte-order mark the parser rejects
        cp.read(p, encoding="utf-8-sig")
    preset = cp.get("general", "preset", fallback="adaptive").strip().lower()
    if preset not in PRESETS:
        raise ValueError(f"overhaul.ini: unknown preset '{preset}' "
                         f"(use one of {', '.join(PRESETS)})")
    cfg = dict(PRESETS[preset])
    cfg["preset"] = preset
    for k, v in cp.items("tuning"):
        v = v.strip()
        if not v:
            continue
        if k == "vanilla_start":
            cfg[k] = v.lower() in ("1", "true", "yes", "on")
        elif k == "enemy_level":
            if v not in ("party", "vanilla"):
                raise ValueError("overhaul.ini: enemy_level must be party or vanilla")
            cfg[k] = v
        elif k == "party_margin" and v.lower() in ("off", "none"):
            cfg[k] = None
        else:
            try:
                cfg[k] = float(v)
            except ValueError:
                raise ValueError(f"overhaul.ini [tuning] {k} = {v}: expected a number "
                                 f"(or leave it empty)") from None
    cfg["features"] = {k: cp.getboolean("features", k, fallback=d)
                       for k, d in FEATURES.items()}
    cfg["save_choice"] = cp.get("general", "save_choice", fallback="ask").strip().lower()
    cfg["ask_timeout"] = cp.getint("general", "ask_timeout", fallback=20)
    cfg["catch_up"] = cp.get("general", "catch_up", fallback="table").strip().lower()
    if cfg["catch_up"] not in ("table", "save"):
        raise ValueError(f"overhaul.ini catch_up = {cfg['catch_up']}: expected table or save")
    cfg["world_notice"] = cp.getboolean("general", "world_notice", fallback=True)
    cfg["markers"] = cp.get("general", "side_story_markers", fallback="auto").strip().lower()
    if cfg["markers"] not in ("auto", "on", "off"):
        raise ValueError(f"overhaul.ini side_story_markers = {cfg['markers']}: "
                         f"expected auto, on or off")
    cfg["markers_from"] = cp.getint("general", "side_story_markers_from", fallback=24)
    cfg["game_dir"] = cp.get("general", "game_dir", fallback="").strip()
    cfg["save_dir"] = cp.get("general", "save_dir", fallback="").strip()
    cfg["cap_test_charm"] = cp.getboolean("legacy", "cap_test_charm", fallback=False)
    return cfg


def apply(cfg):
    """Push settings into the build modules."""
    import build_difficulty_mod as B
    import build_all
    paths.OVERRIDES.update(game_dir=cfg["game_dir"], save_dir=cfg["save_dir"])
    f = cfg["features"]
    B.PROGRESS_MARGIN = cfg["progress_margin"]
    B.PARTY_MARGIN = cfg["party_margin"]
    B.LEGACY_FLOOR = cfg["legacy_floor"]
    B.BOSS_HP_MULT = cfg["boss_hp_mult"]
    B.SUPERBOSS_HP_MULT = cfg["superboss_hp_mult"]
    B.SET_ENEMY_LEVEL = "party" if cfg["enemy_level"] == "party" else False
    B.STEAL_LEVEL_SHIFT = 11 if B.SET_ENEMY_LEVEL else 0
    B.HARD_AREA_DISPLAY = cfg["hard_area_display"]
    B.FINAL_BOSS_DANGER = int(cfg.get("final_boss_danger", 0) or 0)
    B.REVENANT_MIN_DANGER = int(cfg.get("revenant_min_danger", 0) or 0)
    B.REWARD_SHARE = min(1.0, max(0.0, cfg.get("reward_share", 0.5)))
    # the per-stage values above are overwritten at build time from these anchors
    B.RAMP = ramp(cfg)
    if "max_danger" in cfg:
        B.MAX_DANGER = int(cfg["max_danger"])
    B.SCALE_WORLD = f["scale_world"]
    B.PERMANENT_EVASIVE_MANEUVERS = f["fewer_encounters"]
    B.RAISE_DAMAGE_CAP = f["raise_damage_cap"]
    B.PLAYER_STAT_CAP = 9999 if f["raise_stat_caps"] else 999
    B.PLAYER_HP_CAP = 99999 if f["raise_stat_caps"] else 9999
    # catch_up = save tops up the save's EXP instead (topup.py); the table stays as shipped
    B.CATCHUP_LEVELING = f["catch_up_leveling"] and cfg.get("catch_up", "table") == "table"
    B.SCALE_SUMMONS = f["scale_summons"] and f["scale_world"]
    B.SCALE_TRESSA_COLLECT = f["scale_tressa_collect"]
    build_all.NEW_GEAR = f["new_gear"]
    build_all.FAST_TRAVEL = f["fast_travel"]
    build_all.CONSUMABLE_UPGRADES = f["consumable_upgrades"]
    build_all.TOGGLE_DASH = f["toggle_dash"]
    build_all.JOURNAL_HINTS = f["journal_hints"]
    import quest_markers
    quest_markers.MODE, quest_markers.FROM = cfg["markers"], cfg["markers_from"]
    build_all.SCALE_SKILLS = f["scale_skills"]
    build_all.PARTY_RUNES = f["party_runes"]
    build_all.CAP_TEST_ITEM = cfg["cap_test_charm"]
    return cfg


def fingerprint(cfg):
    """Stable string of everything that changes the build (for the launcher's stamp)."""
    import json
    skip = ("save_choice", "ask_timeout", "world_notice")
    return json.dumps({k: v for k, v in cfg.items() if k not in skip},
                      sort_keys=True)
