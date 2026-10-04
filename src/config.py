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
                    hard_area_display=False),
    # Default. A little above vanilla's own curve, and never below the party's level, so a
    # party that out-levels the story meets enemies that keep up.
    "adaptive": dict(progress_margin=2, party_margin=0, legacy_floor=False,
                     boss_hp_mult=1.25, superboss_hp_mult=1.25, enemy_level="party",
                     hard_area_display=False),
    # The original overhaul: +3 danger per chapter from 8, at least party level + 4, bosses
    # x2 HP and superbosses x4. Built for a strong, over-levelled endgame party.
    "relentless": dict(progress_margin=2, party_margin=4, legacy_floor=True,
                       boss_hp_mult=2.0, superboss_hp_mult=4.0, enemy_level="party",
                       hard_area_display=True),
}

FEATURES = {
    "scale_world": True,          # enemies, bosses, rewards, area danger
    "new_gear": True,             # the tiered gear in Grandport + rare drops
    "fast_travel": True,          # fast travel to every VISITED location
    "fewer_encounters": True,     # Evasive Maneuvers baked in (x2 steps between fights)
    "raise_damage_cap": True,     # 999,999 instead of 9,999
    "raise_stat_caps": True,      # stats 9,999 and HP 99,999 instead of 999 / 9,999
    "catch_up_leveling": True,    # under-levelled travelers level ~5x faster
    "scale_summons": True,        # H'aanit's captured beasts keep pace
    "scale_tressa_collect": True,
    "consumable_upgrades": True,  # high-value consumable drops / steals late game
}

DEFAULT_INI = """\
; Octopath Traveler - World Overhaul settings.
; Changes take effect the next time you launch through OctopathWorldOverhaul.exe.

[general]
; classic    - vanilla difficulty curve, plus the new gear, caps and quality of life
; adaptive   - a little harder than vanilla, and enemies never fall below your party level
; relentless - the original overhaul: steep scaling, bosses x2 HP, superbosses x4
preset = adaptive
; Which save the world is built for. "ask" shows a picker at launch (pick the save you
; will load!); "newest" always uses the most recently saved slot.
save_choice = ask
; seconds before the picker continues with the highlighted save
ask_timeout = 20
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

[tuning]
; Leave empty to use the preset's value.
progress_margin =
party_margin =
boss_hp_mult =
superboss_hp_mult =
; party or vanilla
enemy_level =
max_danger =

[legacy]
; Only for saves made with early test builds that bought the "Cap Test Charm".
cap_test_charm = false
"""


def ini_path():
    return os.path.join(paths.app_dir(), "overhaul.ini")


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
        cp.read(p, encoding="utf-8")
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
        if k == "enemy_level":
            if v not in ("party", "vanilla"):
                raise ValueError("overhaul.ini: enemy_level must be party or vanilla")
            cfg[k] = v
        elif k == "party_margin" and v.lower() in ("off", "none"):
            cfg[k] = None
        else:
            cfg[k] = float(v)
    cfg["features"] = {k: cp.getboolean("features", k, fallback=d)
                       for k, d in FEATURES.items()}
    cfg["save_choice"] = cp.get("general", "save_choice", fallback="ask").strip().lower()
    cfg["ask_timeout"] = cp.getint("general", "ask_timeout", fallback=20)
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
    if "max_danger" in cfg:
        B.MAX_DANGER = int(cfg["max_danger"])
    B.SCALE_WORLD = f["scale_world"]
    B.PERMANENT_EVASIVE_MANEUVERS = f["fewer_encounters"]
    B.RAISE_DAMAGE_CAP = f["raise_damage_cap"]
    B.PLAYER_STAT_CAP = 9999 if f["raise_stat_caps"] else 999
    B.PLAYER_HP_CAP = 99999 if f["raise_stat_caps"] else 9999
    B.CATCHUP_LEVELING = f["catch_up_leveling"]
    B.SCALE_SUMMONS = f["scale_summons"] and f["scale_world"]
    B.SCALE_TRESSA_COLLECT = f["scale_tressa_collect"]
    build_all.NEW_GEAR = f["new_gear"]
    build_all.FAST_TRAVEL = f["fast_travel"]
    build_all.CONSUMABLE_UPGRADES = f["consumable_upgrades"]
    build_all.CAP_TEST_ITEM = cfg["cap_test_charm"]
    return cfg


def fingerprint(cfg):
    """Stable string of everything that changes the build (for the launcher's stamp)."""
    import json
    return json.dumps({k: v for k, v in cfg.items() if k not in ("save_choice", "ask_timeout")},
                      sort_keys=True)
