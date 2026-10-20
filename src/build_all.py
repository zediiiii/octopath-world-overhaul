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
import collections
import os
import random
import struct
import sys

import pak
import uasset
import datatable as dt
import pakwrite
import rewards
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
TOGGLE_DASH = False        # overhaul.ini [features] toggle_dash
SCALE_SKILLS = True        # overhaul.ini [features] scale_skills (skills.py)
PARTY_RUNES = True         # overhaul.ini [features] party_runes (skills.py)
JOURNAL_HINTS = True       # overhaul.ini [features] journal_hints (side_stories.py)
CAP_TEST_IN_SHOP = False

# The final boss's prize (user 2026-10-04): +3000 to every stat, dropped by Galdera on
# presets that pin him at a fixed danger. Not sold anywhere.
CROWN_NAME = "Unbound Crown"
CROWN_STATS = {k: 3000 for k in ("HP", "MP", "ATK", "DEF", "MATK", "MDEF", "ACC", "EVA",
                                 "CON", "AGI")}
CROWN_DROP_ROW = "BOS_Lst_Upp_101"
# The reward for finishing EVERY side story (user 2026-10-04): sold in Grandport only once
# the save shows all of them complete.
LAUREL_NAME = "Wayfarer's Laurel"
LAUREL_STATS = dict({k: 1500 for k in ("ATK", "DEF", "MATK", "MDEF", "ACC", "EVA", "CON",
                                       "AGI")}, HP=5000, MP=500)
LAUREL_EFFECTS = [("ADD_MP_FIXED_REGENERATION", 25), ("ADD_HP_FIXED_REGENERATION", 1000),
                  ("EXPUP", 200), ("JPUP", 300)]
LAUREL_PRICE = 500000
# Money x3 (and JP x3): JP-up gear raises battle money too (blueprint_patch.py). Always sold.
PURSE_NAME = "Fortune's Purse"
PURSE_STATS = {"CON": 150, "AGI": 150, "MP": 100}
PURSE_EFFECTS = [("JPUP", 300)]
PURSE_PRICE = 150000
# Grandport stocks the newest tiers the world has opened, not every older one
SHOP_TIERS = 2

# Tier equipment sells back for half its price (user 2026-10-04), so a piece bought to
# compare in the Equip menu - the shop's panel can't show every stat - costs half, not 90%.
# The new consumables keep the 1/10 that stops drop upgrades from being a money farm.
GEAR_SELL_RATIO = 0.5
CONSUMABLE_SELL_RATIO = 0.1

# A tier is only sold - or dropped - once the world is within this many danger points of it.
# It was 10, which let tier 60 be bought at danger 50 where it is ~1.5x too strong.
LOOKAHEAD = 5
# Loot keeps pace with the world (rewards.py): consumable drops and steals climb their
# ladders with world danger; treasure chests and side-story rewards follow the same rules.
CONSUMABLE_MIN_DROP = 10          # percent, for drops that have climbed 3+ rungs
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


def party_hp(danger, nums):
    """A party member's max HP at a danger: the kit the gear formula assumes (vanilla endgame,
    KIT_HP) plus three armour pieces of the tier the world has reached, interpolated."""
    pts = [(45, KIT_HP)] + [(T, KIT_HP + 3 * nums[T]["hp_slot"]) for T in TIERS]
    if danger <= pts[0][0]:
        return KIT_HP
    for (d0, h0), (d1, h1) in zip(pts, pts[1:]):
        if danger <= d1:
            return h0 + (h1 - h0) * (danger - d0) / (d1 - d0)
    return pts[-1][1]


def soulstone_xl_damage(danger):
    """XL soulstones: half a regular foe's HP at this danger, never below the minimum."""
    _p, curve, levels = balance.enemy_curve()
    half = B.profile_at(curve, levels, danger)["HP"] / 2
    return int(max(catalogue.SOULSTONE_XL_MIN, round(half, -3)))


def design_catalogue(nums):
    """-> list of dicts describing every item to mint (see catalogue.py)."""
    if not catalogue.NUT_L_GROWTH:
        bp = pak.Pak(paths.base_pak())
        items = uasset.read_datatable(bp.read(make_gear.ITEMS + ".uasset"),
                                      bp.read(make_gear.ITEMS + ".uexp"))
        g = lambda d, pre: next(vv for kk, vv in d.items() if kk.split("_")[0] == pre)
        for _name, key in catalogue.NUT_XL:
            a = g(items[key], "Ailment")[0]
            catalogue.NUT_L_GROWTH[key] = (g(a, "AilmentName"), g(a, "InvocationValue"))
    return catalogue.design(nums)


def main(out_path=None, install=False):
    log = buildlog.get()
    global print
    print = lambda *a, **k: log.info(" ".join(str(x) for x in a))
    files, floor, target, _gm = B.build(out_path=None, verbose=True, pack=False)
    nums = tier_numbers()
    catalogue.SOULSTONE_XL_DAMAGE = soulstone_xl_damage(floor)
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
                           immune=spec.get("immune", ()),
                           sell_ratio=(CONSUMABLE_SELL_RATIO if spec["kind"] == "consumable"
                                       else GEAR_SELL_RATIO))
        info.update(tier=spec["tier"], kind=spec["kind"], gated=spec.get("gated", False),
                    unsold=spec.get("unsold", False))
        minted.append(info)
    if NEW_GEAR:
        info = forge.forge(catalogue.ACCESSORY_TEMPLATE, LAUREL_NAME,
                           catalogue.describe(LAUREL_STATS, LAUREL_EFFECTS), LAUREL_STATS,
                           ailment=LAUREL_EFFECTS, price=LAUREL_PRICE,
                           sell_ratio=GEAR_SELL_RATIO)
        info.update(tier=0, kind="reward")
        minted.append(info)
        info = forge.forge(catalogue.ACCESSORY_TEMPLATE, PURSE_NAME,
                           catalogue.describe(PURSE_STATS, PURSE_EFFECTS), PURSE_STATS,
                           ailment=PURSE_EFFECTS, price=PURSE_PRICE,
                           sell_ratio=GEAR_SELL_RATIO)
        info.update(tier=0, kind="special")
        minted.append(info)
    if NEW_GEAR and B.FINAL_BOSS_DANGER:
        info = forge.forge(catalogue.ACCESSORY_TEMPLATE, CROWN_NAME,
                           catalogue.describe(CROWN_STATS, []), CROWN_STATS, ailment=None,
                           price=2, sell_ratio=0.5)
        info.update(tier=0, kind="unique")
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
    if PARTY_RUNES:
        import skills
        bp0 = pak.Pak(paths.base_pak())
        abil = uasset.read_datatable(bp0.read(skills.ABILITIES + ".uasset"),
                                     bp0.read(skills.ABILITIES + ".uexp"))
        text0 = uasset.read_datatable(bp0.read(make_gear.TEXT + ".uasset"),
                                      bp0.read(make_gear.TEXT + ".uexp"))
        labels = {skills._g(abil[k], "Detail") for k in skills.rune_rows(abil, text0)}
        forge.text_ua, forge.text_ue = skills.rune_text(forge.text_ua, forge.text_ue, labels,
                                                        log=print)
    if JOURNAL_HINTS:
        import side_stories
        forge.text_ua, forge.text_ue = side_stories.add_walkthroughs(forge.text_ua, forge.text_ue,
                                                             log=print)
    markers = None
    import quest_markers
    if quest_markers.wanted(B.SELECTED_SAVE):
        try:
            markers = quest_markers.Markers(forge, B.SELECTED_SAVE)
        except Exception as exc:                         # noqa: BLE001 (an odd save: no markers)
            print(f"side-story markers skipped: {exc}")
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

    if NEW_GEAR:
        # Sigils / Hearts / armour boosts: make the game count elemental damage boosts on
        # every equipped piece, not only weapons (see blueprint_patch.py)
        import blueprint_patch
        files.update(blueprint_patch.patched_files(pak.Pak(paths.base_pak())))
        print("elemental damage boosts count on armour and accessories too")
    if TOGGLE_DASH:
        import blueprint_patch
        files.update(blueprint_patch.dash_toggle_files(pak.Pak(paths.base_pak())))
        print("dash button toggles running (press once to run, again to walk)")

    if FAST_TRAVEL:
        import build_fasttravel_mod
        ft = build_fasttravel_mod.patched_files(pak.Pak(paths.base_pak()))
        files.update(ft)
        print("fast travel enabled for every visited location")
    if markers:
        markers.apply(files, pak.Pak(paths.base_pak()))

    # ---- other installed mods replacing the same files ----
    # Text tables and CharacterGrowData are built ON TOP of other mods' copies; for anything
    # else this pak (loading last) wins, so name the overlap in the log.
    merged = {make_gear.TEXT, B.GROW}
    for path, (mod, _q) in sorted(paths.other_mod_files().items()):
        stem = path.rsplit(".", 1)[0]
        if stem in merged or "/GameText/" in path or not path.endswith(".uexp"):
            continue
        if path in files:
            print(f"note: {mod} also replaces {stem.rsplit('/', 1)[-1]}; "
                  f"this overhaul's version is the one the game uses")

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
    crown = next((m for m in minted if m["name"] == CROWN_NAME), None)
    if crown:
        i = ekeys.index(CROWN_DROP_ROW)
        dt.set_fname(eue, have_offs[i], anchor_e, crown["row_num"])
        struct.pack_into("<i", eue, prob_offs[i], 100)
        print(f"{CROWN_NAME} (+3000 to every stat): dropped by Galdera ({CROWN_DROP_ROW}), "
              f"fixed at danger {B.FINAL_BOSS_DANGER}")
    print(f"drop tiers open at danger {floor}: {open_tiers or 'none yet (vanilla drops kept)'}")
    print(f"drops: {kept_unique} enemies keep a unique vanilla drop (not sold anywhere)")
    # ---- consumable drops climb their ladders as the world grows (rewards.py) ----
    base_items = uasset.read_datatable(bp.read(make_gear.ITEMS + ".uasset"),
                                       bp.read(make_gear.ITEMS + ".uexp"))
    up = rewards.Upgrader(floor, minted, base_items, open_tiers, LOOKAHEAD)
    upgraded = 0
    if CONSUMABLE_UPGRADES and up.climb:
        names = rewards._Names(eua)
        cur = uasset.read_datatable(eua, bytes(eue))
        for i, k in enumerate(ekeys):
            have = g(base_rows[k], "HaveItemID")
            if cls[k] != "random" or have not in up.rung or g(cur[k], "HaveItemID") != have:
                continue                    # bosses, NPCs, rows given tier gear, other items
            new, _cnt = up.consumable(have, 1)
            if new == have:
                continue
            dt.set_fname(eue, have_offs[i], *names.ref(new, up.by_name))
            o = prob_offs[i]
            if up.climb >= 3 and struct.unpack_from("<i", eue, o)[0] < CONSUMABLE_MIN_DROP:
                struct.pack_into("<i", eue, o, CONSUMABLE_MIN_DROP)
            upgraded += 1
        eua = names.ua
        files[B.ENEMY + ".uasset"] = eua
        print(f"consumable drops climb {up.climb} rung(s) at danger {floor}: "
              f"{upgraded} enemies now drop / can be robbed of better items")
    if CONSUMABLE_UPGRADES:
        # treasure chests and side-story rewards, for the whole world (not just what's left)
        oua, oue = rewards.chests(bp.read(rewards.OBJECTS + ".uasset"),
                                  bp.read(rewards.OBJECTS + ".uexp"), up, log=print)
        files[rewards.OBJECTS + ".uasset"], files[rewards.OBJECTS + ".uexp"] = oua, oue
        mua, mue = rewards.side_stories(bp.read(rewards.MISSIONS + ".uasset"),
                                        bp.read(rewards.MISSIONS + ".uexp"), up, log=print)
        files[rewards.MISSIONS + ".uasset"], files[rewards.MISSIONS + ".uexp"] = mua, mue
    if SCALE_SKILLS or PARTY_RUNES:
        import skills
        text = uasset.read_datatable(bp.read(make_gear.TEXT + ".uasset"),
                                     bp.read(make_gear.TEXT + ".uexp"))
        item_names = {(text.get(g(v, "ItemNameID")) or {}).get("Text")
                      for v in base_items.values()}
        aua = files.get(skills.ABILITIES + ".uasset") or bp.read(skills.ABILITIES + ".uasset")
        aue = files.get(skills.ABILITIES + ".uexp") or bp.read(skills.ABILITIES + ".uexp")
        if SCALE_SKILLS:
            aua, aue = skills.scale(aua, aue, party_hp(floor, nums) / KIT_HP, item_names,
                                    text, floor, log=print)
        if PARTY_RUNES:
            aua, aue, rune_details = skills.runes_for_all(aua, aue, text, log=print)
        if aue != bp.read(skills.ABILITIES + ".uexp"):
            files[skills.ABILITIES + ".uasset"], files[skills.ABILITIES + ".uexp"] = aua, aue
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
    shop_open = sorted(T for T in TIERS if T <= floor + SHOP_LOOKAHEAD)[-SHOP_TIERS:]
    stocked = lambda m: m["tier"] in shop_open
    done = B.LAST_COMPLETION or {}
    side_all = bool(done.get("totals")) and done["side_stories"] >= done["totals"]["side_stories"]
    if NEW_GEAR:
        print(f"{LAUREL_NAME}: " + ("sold in Grandport - every side story is done" if side_all
              else f"sold once every side story is done ({done.get('side_stories', 0)}/"
                   f"{(done.get('totals') or {}).get('side_stories', '?')})"))
    plan = [(GRANDPORT_WEAPONS, "Sea_L_A_SHOP_w_01",
             [m for m in minted if m["kind"] in ("weapon", "armour") and stocked(m)]),
            (GRANDPORT_ITEMS, "Sea_L_A_SHOP_i_01",
             [m for m in minted if (m["kind"] == "consumable" and not m.get("unsold")
                                    and (not m.get("gated") or m["tier"] <= floor + SHOP_LOOKAHEAD))
              or (m["kind"] == "test" and CAP_TEST_IN_SHOP)
              or (m["kind"] == "reward" and side_all)
              or m["kind"] == "special"]
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
        try:
            shutil.copyfile(path, final + ".new")
            os.replace(final + ".new", final)    # fails while the game holds the pak open
        finally:
            for leftover in (final + ".new", path):
                try:
                    os.remove(leftover)
                except OSError:
                    pass
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
