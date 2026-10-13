"""Loot and skill numbers against the world, at several danger levels.

    python dev/loot_balance.py

For each danger: a regular enemy's HP / attack (the profile every enemy is scaled to), a
party member's max HP wearing that danger's gear (the kit the gear formula assumes plus
three armour pieces), and what the scaled rewards and skills come to against those.
"""
import os
import statistics
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
import balance                     # noqa: E402
import build_all                   # noqa: E402
import build_difficulty_mod as B   # noqa: E402
import catalogue                   # noqa: E402
import pak                         # noqa: E402
import paths                       # noqa: E402
import rewards                     # noqa: E402
import skills                      # noqa: E402
import uasset                      # noqa: E402

DANGERS = (35, 50, 60, 70, 81, 90, 104)


def main():
    p, curve, levels = balance.enemy_curve()
    nums = build_all.tier_numbers()
    od = uasset.read_datatable(p.read(rewards.OBJECTS + ".uasset"), p.read(rewards.OBJECTS + ".uexp"))
    sm = uasset.read_datatable(p.read(rewards.MISSIONS + ".uasset"), p.read(rewards.MISSIONS + ".uexp"))
    chest_money = statistics.median(v["HaveItemCnt"] for k, v in od.items()
                                    if k.startswith("TrsrBx") and v["IsMoney"])
    quest_money = statistics.median(B.g(v, "RewardMoney") for v in sm.values()
                                    if B.g(v, "RewardMoney"))
    print("| danger | enemy HP | enemy Atk | party HP | XL stone | Olive XL | Incredible Heal | "
          "Restore Health | chest money | quest money | tier price |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for d in DANGERS:
        e = B.profile_at(curve, levels, d)
        tiers = [t for t in build_all.TIERS if t <= d + build_all.LOOKAHEAD]
        t = tiers[-1] if tiers else None
        hp = build_all.party_hp(d, nums)
        heal = max(1.0, hp / build_all.KIT_HP)
        stone = build_all.soulstone_xl_damage(d)
        olive = 100
        print(f"| {d} | {e['HP']:,} | {e['ATK']:,} | {int(hp):,} | "
              f"{stone:,} = {100 * stone / e['HP']:.0f}% | "
              f"{olive}% = {int(hp * (olive or 0) / 100):,} | "
              f"{int(8000 * heal):,} = {100 * 8000 * heal / hp:.0f}% | "
              f"{int(2000 * heal):,} = {100 * 2000 * heal / hp:.0f}% | "
              f"{int(100 * skills.sp_mult(heal))} | "
              f"{int(chest_money * rewards.money_mult(d)):,} | "
              f"{int(quest_money * rewards.money_mult(d)):,} | "
              f"{nums[t]['price']:,} |" if t else "")


if __name__ == "__main__":
    main()
