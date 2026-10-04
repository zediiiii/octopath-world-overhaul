"""Build the whole package as one pak: scaled world + a new gear ladder + shop + drops.

Everything keys off one number - the world danger floor, derived from your save's story
progress - so re-running this after each chapter re-tunes enemies, rewards, danger numbers,
which gear tiers Grandport stocks, and what drops.

Design notes that the numbers come from (see balance.py):
  * Player stats cap at 999 and HP at 9999. Verified in-game: a +1234 Atk test blade moved
    H'aanit 663 -> 999, while its +77 Critical applied exactly. So gear cannot counter-scale
    forever, and past ~danger 82 nothing keeps up. The floor is capped at MAX_DANGER.
  * Above tier 60 the stat budget is already at the cap, so each higher tier buys its power
    with WEAPON_ABILITY_UP / elemental percentages, which multiply *after* the capped stat,
    plus HP, which has its own much higher ceiling.
  * Gear is all brand-new rows. Nothing you already own changes.
"""
import paths
import os
import random
import struct
import sys

import pak
import uasset
import datatable as dt
import pakwrite
import make_gear
import balance
import buildlog
import build_difficulty_mod as B

OUT_NAME = make_gear.OUT_PREFIX + "OctopathWorldOverhaul_p.pak"
SHOP = "Octopath_Traveler/Content/Shop/Database/ShopList"
PURCHASE = "Octopath_Traveler/Content/Shop/Database/PurchaseItemTable"
GRANDPORT_WEAPONS = "Sea_L_A_SHOP_w"
GRANDPORT_ITEMS = "Sea_L_A_SHOP_i"

import catalogue

TIERS = catalogue.TIERS
TIER_NAME = catalogue.TIER_NAME
# The "Cap Test Charm" (+2000 Atk / Elem. Atk) proved the raised stat cap in-game. It stays
# MINTED because the player owns one (deleting its row could break that save), but is no
# longer sold.
CAP_TEST_ITEM = False          # overhaul.ini [legacy] cap_test_charm
# feature switches (overhaul.ini [features])
NEW_GEAR = True
FAST_TRAVEL = True
CONSUMABLE_UPGRADES = True
CAP_TEST_IN_SHOP = False

# A tier is only sold - or dropped - once the world is within this many danger points of it.
# It was 10, which let tier 60 be bought at danger 50 where it is ~1.5x too strong.
LOOKAHEAD = 5
# From this danger on, random enemies that drop an ordinary consumable drop (and can be
# stolen from for) high-value ones instead - Revitalizing Jam, Olive of Life (L), the
# Invigorating / Vital restores. Alfyn's concoct materials and status cures are left alone.
CONSUMABLE_UPGRADE_FROM = 68
CONSUMABLE_MIN_DROP = 10          # percent
# vanilla rows (by ItemDB key) and our minted ones (by name)
UPGRADE_POOL_LOW = ["Vital Draught", "Invigorating Draught", "ITM_010", "ITM_144"]
UPGRADE_POOL_HIGH = ["ITM_007", "ITM_018", "Vital Cask", "Invigorating Cask", "ITM_017",
                     "ITM_145"]
SHOP_LOOKAHEAD = LOOKAHEAD
DROP_RATE = 1            # percent, for repeatable random encounters
# Bosses are fought once, so a 1% roll would mean effectively never.
BOSS_DROP_RATE = 100

# What the rest of a character's kit already supplies, measured on H'aanit at L58 (status
# screen: Phys. Atk 663, Phys. Def 520, Max HP 2,919). The first version of this formula
# subtracted only the bare level-curve stats (208) and forgot nuts, job bonuses and
# accessories, so Tempered weapons came out at 684 Atk and pushed her to ~999 at danger 50.
#   Phys. Atk shown with her sword (310) equipped  -> 663 - 310 = 353 from everything else
#   armour on her: shield 21 + helm 79 + body 235  -> 520 - 335 = 185 Def from everything else
# Taking the sword (her weakest weapon) as the one shown makes the non-weapon share the
# LARGEST plausible value, so if anything the new gear errs on the weak side.
KIT_ATK = balance.REF["atk"] - 310
KIT_DEF = balance.REF["dfn"] - 335
KIT_HP = balance.REF["hp"]
# The caps are data and now raised (B.PLAYER_STAT_CAP / B.PLAYER_HP_CAP, confirmed in-game),
# so gear can carry the full stat the world asks for instead of a capped stat + multiplier.
GEAR_STAT_ROOM = B.PLAYER_STAT_CAP - KIT_ATK
GEAR_DEF_ROOM = B.PLAYER_STAT_CAP - KIT_DEF
GEAR_HP_ROOM = B.PLAYER_HP_CAP - KIT_HP
# Survival target, measured in-game at danger 68 (enemy Atk ~970): a Greater Kingfisher's
# regular attack hit for ~2,500 and its Meteor for ~4,200 into a defending H'aanit with
# ~3-4k HP - one or two hits to kill. A full tier-T armour set should make a regular hit
# about a fifth of max HP: ~15,000 HP at danger 68, i.e. HP = 15.5 x enemy Atk. (The
# shipped game's 5.5 x was measured with the party out-levelling everything.)
HP_PER_ENEMY_ATK = 15.5


def tier_numbers():
    p, curve, levels = balance.enemy_curve()
    _e, ratios = balance.reference_ratios(curve, levels)
    out = {}
    for T in TIERS:
        e = B.profile_at(curve, levels, T)
        # aim: a character wearing this tier at danger T feels like vanilla endgame
        want_atk = ratios["atk_vs_def"] * e["DEF"]
        gear_atk = min(GEAR_STAT_ROOM, max(1, round(want_atk - KIT_ATK)))
        # whatever the 999 cap stops the stat from delivering, the multiplier delivers
        reach = KIT_ATK + gear_atk
        weapon_mult = max(100, int(round(100 * want_atk / reach)))
        want_def = ratios["def_vs_atk"] * e["ATK"]
        gear_def = min(GEAR_DEF_ROOM, max(3, round(want_def - KIT_DEF)))
        want_hp = HP_PER_ENEMY_ATK * e["ATK"]
        gear_hp = min(GEAR_HP_ROOM, max(3, round(want_hp - KIT_HP)))
        out[T] = dict(enemy=e, weapon_atk=gear_atk, weapon_mult=min(weapon_mult, 260),
                      def_slot=max(1, gear_def // 3), hp_slot=max(1, gear_hp // 3),
                      budget=round(2.5 * T),
                      price=round(50000 * (T / 60.0) ** 3))
    return out


def design_catalogue(nums):
    """-> list of dicts describing every item to mint (see catalogue.py)."""
    return catalogue.design(nums)


def main(out_path=None, install=False):
    log = buildlog.get()
    global print
    print = lambda *a, **k: log.info(" ".join(str(x) for x in a))
    files, floor, target, _gm = B.build(out_path=None, verbose=True, pack=False)
    nums = tier_numbers()
    cat = design_catalogue(nums)
    if not NEW_GEAR:
        # keep the new consumables (SP / % HP restores); drop the equipment ladder
        cat = [c for c in cat if c["kind"] == "consumable"]
    print(f"\ndesigned {len(cat)} new items across tiers {TIERS}")
    for T in TIERS:
        n = nums[T]
        print(f"  tier {T:>2} ({TIER_NAME[T]:<10}): weapon {n['weapon_atk']} Atk "
              f"x{n['weapon_mult']}%, armour {n['def_slot']} Def / {n['hp_slot']} HP per slot, "
              f"accessory budget {n['budget']}, price {n['price']:,}")

    registry = make_gear.IdRegistry()
    forge = make_gear.GearForge(registry)
    print(f"text rows appended onto: {forge.text_source}")
    # the world-scaling pass already rewrote EnemyDB/ItemDB; keep those edits
    forge.item_ua = files[make_gear.ITEMS + ".uasset"] if make_gear.ITEMS + ".uasset" in files else forge.item_ua
    if make_gear.ITEMS + ".uexp" in files:
        forge.item_ue = files[make_gear.ITEMS + ".uexp"]
        forge.item_spans = {s[0]: s for s in dt.row_spans(forge.item_ua, forge.item_ue)}
        forge.rows = uasset.read_datatable(forge.item_ua, forge.item_ue)

    minted = []
    for spec in cat:
        info = forge.forge(spec["template"], spec["name"], spec["desc"], spec["stats"],
                           ailment=spec["ailment"], price=spec["price"],
                           immune=spec.get("immune", ()))
        info.update(tier=spec["tier"], kind=spec["kind"])
        minted.append(info)
    if CAP_TEST_ITEM:
        # TEMPORARY: proves whether the raised stat cap holds in-game. +2000 to both attack
        # stats on an accessory (accessories stack), sold for 1 leaf in the item shop.
        stats = {"ATK": 2000, "MATK": 2000}
        info = forge.forge(catalogue.ACCESSORY_TEMPLATE, "Cap Test Charm",
                           catalogue.describe(stats, []), stats, ailment=None, price=1)
        info.update(tier=0, kind="test")
        minted.append(info)
        print("TEST ITEM: Cap Test Charm kept in ItemDB" + (" and sold" if CAP_TEST_IN_SHOP else
                                                             " (not sold)"))

    registry.save()
    print(f"item IDs {min(m['id'] for m in minted)}-{max(m['id'] for m in minted)} "
          f"(stable across rebuilds, see {os.path.basename(make_gear.REGISTRY)})")
    iua, iue = dt.append_rows(forge.item_ua, forge.item_ue, forge.new_items)
    tua, tue = dt.append_rows(forge.text_ua, forge.text_ue, forge.new_texts)
    dt.verify(iua, iue)
    dt.verify(tua, tue)
    files[make_gear.ITEMS + ".uasset"] = iua
    files[make_gear.ITEMS + ".uexp"] = iue
    files[make_gear.TEXT + ".uasset"] = tua
    files[make_gear.TEXT + ".uexp"] = tue
    # the same rows (English text) in every other language, so names are never blank
    for base, (lua, lue, _src) in forge.other_languages().items():
        try:
            rows = forge.text_rows_for(lua)
        except RuntimeError as exc:
            print(f"  {base.rsplit('/', 1)[-1]}: skipped ({exc})")
            continue
        lua2, lue2 = dt.append_rows(lua, lue, rows)
        dt.verify(lua2, lue2)
        files[base + ".uasset"], files[base + ".uexp"] = lua2, lue2
    print(f"item names added to {1 + len(forge.other_languages())} language tables")

    if FAST_TRAVEL:
        import build_fasttravel_mod
        ft = build_fasttravel_mod.patched_files(pak.Pak(paths.base_pak()))
        files.update(ft)
        print("fast travel enabled for every visited location")

    # ---- rare drops: tougher monsters carry better tiers ----
    eua = files[B.ENEMY + ".uasset"]
    eue = bytearray(files[B.ENEMY + ".uexp"])
    enames, _ = uasset.names_of(eua)
    base_rows = uasset.read_datatable(pak.Pak(paths.base_pak()).read(B.ENEMY + ".uasset"),
                                      pak.Pak(paths.base_pak()).read(B.ENEMY + ".uexp"))
    ekeys = list(base_rows)
    bosses, supers = B.boss_sets(pak.Pak(paths.base_pak()))
    have_offs = dt.field_offsets_in(bytes(eue), enames, 0, len(eue),
                                    "HaveItemID", "NameProperty")
    prob_offs = B.int_offsets(eua, bytes(eue), "DropProbability", expect=len(ekeys))
    if len(have_offs) != len(ekeys):
        raise RuntimeError(f"HaveItemID offsets {len(have_offs)} != rows {len(ekeys)}")

    g = lambda d, pre: next(vv for kk, vv in d.items() if kk.split("_")[0] == pre)
    # Only replace a vanilla drop the player can still get elsewhere (sold in some shop) or
    # an empty one - never unique equipment, nuts, or other one-source loot. And only on
    # enemies an area can actually roll: never Provoke/Challenge opponents or caits.
    cls = B.enemy_classes(pak.Pak(paths.base_pak()), base_rows)
    bp = pak.Pak(paths.base_pak())
    sold = {g(v, "ItemLabel") for v in uasset.read_datatable(
        bp.read(PURCHASE + ".uasset"), bp.read(PURCHASE + ".uexp")).values()}

    def replaceable(k):
        have = g(base_rows[k], "HaveItemID")
        return have in ("None", "") or have in sold
    kept_unique = sum(1 for k in ekeys if cls[k] in ("random", "boss") and not replaceable(k))
    regular = [(g(g(base_rows[k], "Param"), "HP"), i, k)
               for i, k in enumerate(ekeys) if cls[k] == "random" and replaceable(k)]
    regular.sort()
    # equipment only - the SP consumables carry tier 60 for pricing and must not become drops
    by_tier = {T: [m for m in minted if m["tier"] == T and m["kind"] != "consumable"]
               for T in TIERS}
    for T, lst in by_tier.items():
        if NEW_GEAR and not lst:
            raise RuntimeError(f"no equipment minted for tier {T}; cannot assign drops")
    # Tougher monsters carry better tiers, but never a tier the world hasn't nearly reached:
    # an enemy with no eligible tier keeps its vanilla drop untouched.
    open_tiers = [T for T in TIERS if T <= floor + LOOKAHEAD] if NEW_GEAR else []
    bands = [(0.50, 0.70, 60), (0.70, 0.85, 70), (0.85, 0.95, 80), (0.95, 1.01, 90)]
    rng = random.Random(1729)
    drops = 0
    boss_drops = 0
    anchor_e = enames.index(make_gear.ROW_ANCHOR)
    for lo, hi, T in bands:
        allowed = [t for t in open_tiers if t <= T]
        if not allowed:
            continue
        T = max(allowed)
        chunk = regular[int(len(regular) * lo):int(len(regular) * hi)]
        for _hp, i, _k in chunk:
            pick = rng.choice(by_tier[T])
            dt.set_fname(eue, have_offs[i], anchor_e, pick["row_num"])
            struct.pack_into("<i", eue, prob_offs[i], DROP_RATE)
            drops += 1
    # normal bosses carry the best open tier; their vanilla drops are common consumables
    if open_tiers:
        for i, k in enumerate(ekeys):
            if cls[k] == "boss" and replaceable(k):
                pick = rng.choice(by_tier[max(open_tiers)])
                dt.set_fname(eue, have_offs[i], anchor_e, pick["row_num"])
                struct.pack_into("<i", eue, prob_offs[i], BOSS_DROP_RATE)
                drops += 1
                boss_drops += 1
    print(f"drop tiers open at danger {floor}: {open_tiers or 'none yet (vanilla drops kept)'}")
    print(f"drops: {kept_unique} enemies keep a unique vanilla drop (not sold anywhere)")
    # ---- high-value consumables at danger CONSUMABLE_UPGRADE_FROM+ ----
    upgraded = 0
    if CONSUMABLE_UPGRADES and floor >= CONSUMABLE_UPGRADE_FROM:
        base_items = uasset.read_datatable(bp.read(make_gear.ITEMS + ".uasset"),
                                           bp.read(make_gear.ITEMS + ".uexp"))
        minted_by_name = {m["name"]: m for m in minted}

        def ref(key):
            """-> (EnemyDB name index, FName number) for a pool entry."""
            nonlocal eua, enames
            if key in minted_by_name:
                return enames.index(make_gear.ROW_ANCHOR), minted_by_name[key]["row_num"]
            if key not in base_items:
                raise RuntimeError(f"upgrade pool item {key} not in ItemDB")
            if key not in enames:
                eua = dt.add_names(eua, [key])
                enames, _ = uasset.names_of(eua)
            return enames.index(key), 0

        def ordinary(item):
            if item in ("None", "") or item not in sold or item.startswith("ITM_MB_"):
                return False
            ails = [g(a, "AilmentName") for a in g(base_items[item], "Ailment")]
            return not any(a.startswith("REMOVE_") for a in ails)
        cur = uasset.read_datatable(eua, bytes(eue))
        cands = sorted((g(g(base_rows[k], "Param"), "HP"), i, k) for i, k in enumerate(ekeys)
                       if cls[k] == "random"
                       and g(cur[k], "HaveItemID") == g(base_rows[k], "HaveItemID")
                       and ordinary(g(base_rows[k], "HaveItemID")))
        low = [ref(x) for x in UPGRADE_POOL_LOW]
        high = [ref(x) for x in UPGRADE_POOL_HIGH]
        for rank, (_hp, i, _k) in enumerate(cands):
            idx, num = rng.choice(high if rank >= len(cands) // 2 else low)
            dt.set_fname(eue, have_offs[i], idx, num)
            o = prob_offs[i]
            if struct.unpack_from("<i", eue, o)[0] < CONSUMABLE_MIN_DROP:
                struct.pack_into("<i", eue, o, CONSUMABLE_MIN_DROP)
            upgraded += 1
        files[B.ENEMY + ".uasset"] = eua
        print(f"danger {floor} >= {CONSUMABLE_UPGRADE_FROM}: {upgraded} enemies now drop / "
              f"can be robbed of high-value consumables (min {CONSUMABLE_MIN_DROP}% drop)")
    files[B.ENEMY + ".uexp"] = bytes(eue)
    uasset.read_datatable(eua, bytes(eue))      # must still parse
    print(f"rare drops: {drops - boss_drops} enemies at {DROP_RATE}%, "
          f"{boss_drops} bosses at {BOSS_DROP_RATE}%")

    # ---- shop: stock the tiers appropriate to current progress ----
    p = pak.Pak(paths.base_pak())
    pua, pue = p.read(PURCHASE + ".uasset"), p.read(PURCHASE + ".uexp")
    pnames, _ = uasset.names_of(pua)
    pspans = {s[0]: s for s in dt.row_spans(pua, pue)}
    if make_gear.ROW_ANCHOR not in pnames:
        raise RuntimeError(f"{make_gear.ROW_ANCHOR} missing from PurchaseItemTable names")
    # equipment goes to the weapon shop, consumables to the item shop
    # weapons and armour go to the weapon shop; accessories and consumables to the item
    # shop, which keeps each list a manageable length
    stocked = lambda m: m["tier"] <= floor + SHOP_LOOKAHEAD
    plan = [(GRANDPORT_WEAPONS, "Sea_L_A_SHOP_w_01",
             [m for m in minted if m["kind"] in ("weapon", "armour") and stocked(m)]),
            (GRANDPORT_ITEMS, "Sea_L_A_SHOP_i_01",
             [m for m in minted if m["kind"] == "consumable"
              or (m["kind"] == "test" and CAP_TEST_IN_SHOP)]
             + [m for m in minted if m["kind"] == "accessory" and stocked(m)])]

    new_purchase = []
    shop_additions = {}
    num_seq = make_gear.FNUM_BASE + 700
    for shop_row, tmpl_key, group in plan:
        if tmpl_key not in pspans:
            raise RuntimeError(f"shop template row {tmpl_key} not found")
        _nm, _idx, _num, s, e = pspans[tmpl_key]
        anchor_i = pnames.index(tmpl_key)
        refs = []
        for m in group:
            buf = bytearray(pue[s:e])
            num = num_seq
            num_seq += 1
            dt.set_fname(buf, 0, anchor_i, num)                 # new purchase row name
            offs = dt.field_offsets_in(buf, pnames, 0, len(buf), "ItemLabel", "NameProperty")
            if len(offs) != 1:
                raise RuntimeError("ItemLabel offset not unique")
            dt.set_fname(buf, offs[0], pnames.index(make_gear.ROW_ANCHOR), m["row_num"])
            new_purchase.append(bytes(buf))
            refs.append((tmpl_key, num))
        shop_additions[shop_row] = refs

    pua2, pue2 = dt.append_rows(pua, pue, new_purchase)
    dt.verify(pua2, pue2)
    sua2, sue2 = p.read(SHOP + ".uasset"), p.read(SHOP + ".uexp")
    for shop_row, refs in shop_additions.items():
        if not refs:
            continue
        snames, _ = uasset.names_of(sua2)
        sua2, sue2 = dt.extend_shop_row(
            sua2, sue2, shop_row, [(snames.index(t), n) for t, n in refs])
        dt.verify(sua2, sue2)
    files[PURCHASE + ".uasset"] = pua2
    files[PURCHASE + ".uexp"] = pue2
    files[SHOP + ".uasset"] = sua2
    files[SHOP + ".uexp"] = sue2
    for shop_row, refs in shop_additions.items():
        print(f"Grandport {shop_row}: +{len(refs)} entries")

    out_path = out_path or os.path.join(paths.mods_dir() if install else ".", OUT_NAME)
    size = pakwrite.write_pak(out_path, files)
    q = pak.Pak(out_path)
    for n, d in files.items():
        assert q.read(n) == d, f"pak round-trip failed: {n}"
    print(f"wrote {out_path} ({size:,} bytes), {len(q.entries)} files, re-read OK")
    return out_path, minted, floor


def build_and_check(out_path=None, install=False):
    """Build, then validate; only a pak that passes is ever put in the mods folder.

    Builds into a staging file next to this script, validates THAT, and only then swaps it
    over the installed pak - so a failed build leaves the previous, known-good pak in place.
    """
    final = out_path or (os.path.join(paths.mods_dir(), OUT_NAME) if install else None)
    staging = os.path.join(paths.user_dir(), "staging_" + OUT_NAME)
    path, minted, floor = main(staging, install=False)
    import validate
    errors = validate.main(path)
    if errors:
        raise RuntimeError(f"{errors} validation error(s) in {path} - installed pak NOT "
                           f"replaced; see the log above")
    if final:
        import shutil
        shutil.copyfile(path, final + ".new")
        os.replace(final + ".new", final)
        os.remove(path)
        path = final
        print(f"installed {final}")
    return path, minted, floor


if __name__ == "__main__":
    import config
    config.apply(config.load())
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    do_install = "--install" in sys.argv
    target = args[0] if args else (
        os.path.join(paths.mods_dir(), OUT_NAME) if do_install else None)
    buildlog.run(build_and_check, target, name="build_all")
