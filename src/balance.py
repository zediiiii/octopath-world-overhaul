"""Work out how far the world can actually be scaled, and what gear each tier should carry.

The hard constraint, confirmed in-game: player stats cap at 999 (HP at 9999). A test blade
with +1234 Phys. Atk showed H'aanit going 663 -> 999, not 1587, while its +77 Critical
applied exactly. So equipment cannot counter-scale past the cap, which puts a ceiling on
how hard the world can get before fights simply stop being winnable.

What is NOT capped, and therefore where high tiers must get their power:
  * HP, up to 9999 (3.4x H'aanit's current 2,919)
  * elemental damage multipliers (FIRE/ICE/THUNDER/WIND/LIGHT/DARK/WEAPON_ABILITY_UP),
    which are percentages applied after the stat
  * the damage cap itself (BATTLE_DAMAGE_CAP, a data value, default 9999)

Reference numbers are measured from the live save rather than assumed: H'aanit at L58 with
her actual kit reads Phys. Atk 663, Phys. Def 520, Max HP 2,919.
"""
import paths
import pak
import uasset
import build_difficulty_mod as B

STAT_CAP = 999
HP_CAP = 9999

# measured in-game, H'aanit L58, equipped (see screenshots in the notes)
REF = dict(level=58, atk=663, dfn=520, hp=2919, acc=477, crit=467, matk=208, mdef=294)
# the enemies she actually fights: the vanilla endgame band (EnemyLevel 45-47)
REF_ENEMY_BAND = (45, 47)

TIERS = [60, 70, 80, 90, 99]


def player_curve(p=None):
    """level -> base parameters, from CharacterGrowData."""
    p = p or pak.Pak(paths.base_pak())
    grow = uasset.read_datatable(
        p.read("Octopath_Traveler/Content/Character/Database/CharacterGrowData.uasset"),
        p.read("Octopath_Traveler/Content/Character/Database/CharacterGrowData.uexp"))
    g = lambda d, pre: next(vv for kk, vv in d.items() if kk.split("_")[0] == pre)
    out = {}
    for k, v in grow.items():
        prm = g(v, "Parameter")
        out[int(k)] = {s: g(prm, s) for s in
                       ["HP", "MP", "ATK", "DEF", "MATK", "MDEF", "ACC", "EVA", "CON", "AGI"]}
    return out


def enemy_curve():
    p = pak.Pak(paths.base_pak())
    rows = uasset.read_datatable(p.read(B.ENEMY + ".uasset"), p.read(B.ENEMY + ".uexp"))
    bosses, _ = B.boss_sets(p)
    curve, levels = B.build_curve(rows, bosses)
    return p, curve, levels


def reference_ratios(curve, levels):
    lo, hi = REF_ENEMY_BAND
    band = [curve[l] for l in levels if lo <= l <= hi]
    e = {k: sum(b[k] for b in band) / len(band) for k in band[0]}
    return e, dict(atk_vs_def=REF["atk"] / e["DEF"],
                   def_vs_atk=REF["dfn"] / e["ATK"],
                   hp_vs_atk=REF["hp"] / e["ATK"])


def sustainable_danger(curve, levels, ratios, slack=1.0):
    """Highest danger at which a stat-capped player still holds `slack` x the vanilla ratio."""
    best = None
    for d in range(40, 140):
        e = B.profile_at(curve, levels, d)
        if STAT_CAP / e["DEF"] >= ratios["atk_vs_def"] * slack:
            best = d
    return best


def tier_plan(curve, levels, ratios):
    """What each tier can actually deliver, given the cap."""
    out = []
    for T in TIERS:
        e = B.profile_at(curve, levels, T)
        # raw stats are only useful up to the cap; everything past it is dead weight
        want_atk = ratios["atk_vs_def"] * e["DEF"]
        capped = min(STAT_CAP, round(want_atk))
        shortfall = max(0.0, want_atk - STAT_CAP) / want_atk
        # the shortfall has to be bought back with an elemental multiplier instead
        elem_pct = int(round(100 * (1 / (1 - shortfall) - 1))) if shortfall else 0
        want_hp = ratios["hp_vs_atk"] * e["ATK"]
        out.append(dict(tier=T, enemy=e, want_atk=round(want_atk), atk_after_cap=capped,
                        shortfall_pct=round(100 * shortfall),
                        elem_needed=min(elem_pct, 200),
                        want_hp=round(want_hp), hp_after_cap=min(HP_CAP, round(want_hp))))
    return out


if __name__ == "__main__":
    p, curve, levels = enemy_curve()
    e_ref, ratios = reference_ratios(curve, levels)
    print("measured reference (H'aanit L58 vs vanilla endgame enemies):")
    print("   player atk %d vs enemy DEF %d  -> ratio %.2f" % (
        REF["atk"], e_ref["DEF"], ratios["atk_vs_def"]))
    print("   player def %d vs enemy ATK %d  -> ratio %.2f" % (
        REF["dfn"], e_ref["ATK"], ratios["def_vs_atk"]))
    print("   player HP  %d vs enemy ATK %d  -> ratio %.2f" % (
        REF["hp"], e_ref["ATK"], ratios["hp_vs_atk"]))
    print()
    for slack, label in [(1.0, "same feel as vanilla"), (0.8, "noticeably harder"),
                         (0.6, "punishing")]:
        d = sustainable_danger(curve, levels, ratios, slack)
        print("   max danger at %-22s (%.0f%% of vanilla power ratio): %s" % (
            label, slack * 100, d))
    print()
    print("tier | enemy DEF | atk wanted | after 999 cap | shortfall | elem%% to cover | "
          "HP wanted | after 9999 cap")
    print("-" * 108)
    for r in tier_plan(curve, levels, ratios):
        print(" %3d | %9d | %10d | %13d | %8d%% | %14d | %9d | %14d" % (
            r["tier"], r["enemy"]["DEF"], r["want_atk"], r["atk_after_cap"],
            r["shortfall_pct"], r["elem_needed"], r["want_hp"], r["hp_after_cap"]))
