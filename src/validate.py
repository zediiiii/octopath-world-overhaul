"""Check a built pak against the base game and report anything suspicious.

Run after building:  python validate.py <pak>
Exits non-zero if any ERROR-level problem is found, so it can gate an install.

The most important check is the first one: that no item you already own has changed.
"""
import paths
import collections
import os
import sys

import pak
import uasset
import datatable as dt
import buildlog
import build_difficulty_mod as B
import make_gear

ITEMS = make_gear.ITEMS
TEXT = make_gear.TEXT
PURCHASE = "Octopath_Traveler/Content/Shop/Database/PurchaseItemTable"
SHOP = "Octopath_Traveler/Content/Shop/Database/ShopList"
PARAMS = B.PARAMS

g = lambda d, pre: next(vv for kk, vv in d.items() if kk.split("_")[0] == pre)


class Report:
    def __init__(self, log):
        self.log = log
        self.errors = 0
        self.warnings = 0

    def ok(self, msg):
        self.log.info("  PASS  %s", msg)

    def warn(self, msg):
        self.warnings += 1
        self.log.warning("  WARN  %s", msg)

    def fail(self, msg):
        self.errors += 1
        self.log.error("  FAIL  %s", msg)

    def check(self, cond, good, bad):
        self.ok(good) if cond else self.fail(bad)


def table(p, path):
    return uasset.read_datatable(p.read(path + ".uasset"), p.read(path + ".uexp"))


def read_text_row(ua, ue, row_name):
    """Look up one GameTextEN row without walking the whole table.

    GameTextEN comes from another mod and our reader cannot walk every row of it, so rows
    are located by their FName bytes (name index + number) and parsed individually.
    """
    import struct
    names, _ = uasset.names_of(ua)
    base, _, suffix = row_name.rpartition("_")
    if suffix.isdigit() and base in names:
        idx, num = names.index(base), int(suffix) + 1
    elif row_name in names:
        idx, num = names.index(row_name), 0
    else:
        return None
    pos = ue.find(struct.pack("<ii", idx, num))
    if pos < 0:
        return None
    try:
        r = uasset.DTReader(ue, names)
        r.p = pos
        r.fname()
        return r.props()
    except Exception:                              # noqa: BLE001
        return None


def text_of(row):
    if not row:
        return None
    for k, v in row.items():
        if k.split("_")[0] == "Text":
            return v
    return None


def main(pak_path):
    log = buildlog.get()
    log.info("validating %s", pak_path)
    base = pak.Pak(paths.base_pak())
    mod = pak.Pak(pak_path)
    r = Report(log)

    present = set(mod.entries)
    log.info("files in pak: %d", len(present))

    # ---- 1. nothing the player already owns may change -------------------
    log.info("[1] existing content untouched")
    b_items = table(base, ITEMS)
    m_items = table(mod, ITEMS) if ITEMS + ".uexp" in present else b_items
    changed = [k for k in b_items if k in m_items and str(b_items[k]) != str(m_items[k])]
    r.check(not changed,
            f"all {len(b_items)} original item rows are byte-identical (no owned gear changed)",
            f"{len(changed)} original item rows were modified: {changed[:5]}")
    missing = [k for k in b_items if k not in m_items]
    r.check(not missing, "no original item row was dropped",
            f"{len(missing)} original item rows are missing: {missing[:5]}")

    # ---- 2. new items are coherent ---------------------------------------
    log.info("[2] new items")
    new_keys = [k for k in m_items if k not in b_items]
    log.info("  %d new item rows", len(new_keys))
    ids = collections.Counter(g(v, "ItemID") for v in m_items.values())
    dupes = [i for i, c in ids.items() if c > 1 and i > 0]
    r.check(not dupes, "no duplicate ItemIDs", f"duplicate ItemIDs: {dupes[:10]}")

    name_of = {}
    desc_of = {}
    if TEXT + ".uexp" in present:
        tua, tue = mod.read(TEXT + ".uasset"), mod.read(TEXT + ".uexp")
        unresolved, blank, nodesc, sample = [], [], [], []
        for k in new_keys:
            nm = text_of(read_text_row(tua, tue, g(m_items[k], "ItemNameID")))
            name_of[k] = nm
            ds = text_of(read_text_row(tua, tue, g(m_items[k], "DetailTextID")))
            if nm is None:
                unresolved.append(k)
            elif not nm.strip():
                blank.append(k)
            elif len(sample) < 6:
                sample.append(nm)
            if ds is None:
                nodesc.append(k)
            else:
                desc_of[k] = ds
        r.check(not unresolved, f"all {len(new_keys)} new items resolve a name string",
                f"{len(unresolved)} new items have no name row: {unresolved[:5]}")
        r.check(not blank, "no new item has a blank name",
                f"{len(blank)} new items have blank names: {blank[:5]}")
        r.check(not nodesc, "all new items resolve a description",
                f"{len(nodesc)} new items have no description row")
        log.info("  sample names: %s", ", ".join(sample))
    else:
        r.warn("GameTextEN not in pak - new items would have blank names")

    # stat sanity: anything above the usable cap is wasted
    over = []
    for k in new_keys:
        rev = g(m_items[k], "EquipmentRevision")
        for s, f in make_gear.STAT_FIELD.items():
            v = rev[f]
            if s == "HP" and v > B.PLAYER_HP_CAP:
                over.append((k, s, v))
            elif s != "HP" and v > B.PLAYER_STAT_CAP:
                over.append((k, s, v))
    if over:
        r.warn(f"{len(over)} new stat values exceed the usable cap (wasted): {over[:5]}")
    else:
        r.ok(f"no new gear stat exceeds the {B.PLAYER_STAT_CAP} / {B.PLAYER_HP_CAP} caps")

    # effect slots: only intended effects. Passive effects must carry the timing shipped
    # gear uses (cloned templates used to leak procs and regen onto new gear); on-hit procs
    # are deliberate and must have a real chance (1-100%) and, for debuffs, a duration.
    import catalogue
    proc_names = set(catalogue.DEBUFF_TEXT) | {"INSTANT_DEATH"}
    junk = []
    for k in new_keys:
        for a in g(m_items[k], "Ailment"):
            an = g(a, "AilmentName")
            if an in ("None", "0"):
                continue
            got = (g(a, "InvocationTurn"), g(a, "DiseaseRate"))
            if an in proc_names:
                bad = not (1 <= got[1] <= 100) or (an != "INSTANT_DEATH" and got[0] <= 0)
            else:
                bad = got != make_gear.AILMENT_TIMING.get(an, (0, 0))
            if bad:
                junk.append((name_of.get(k, k), an, got))
    r.check(not junk, "every new effect slot is intentional, with valid timing",
            f"{len(junk)} stray/mistimed effects on new gear: {junk[:5]}")
    procs = sum(1 for k in new_keys for a in g(m_items[k], "Ailment")
                if g(a, "AilmentName") in proc_names)
    log.info("  %d on-hit effects across new weapons", procs)

    # design rules: a major + minor stat everywhere, SP standard from tier 70, SP regen
    # common from tier 80
    tier_of = {}
    for k, nm in name_of.items():
        for T, pre in catalogue.TIER_NAME.items():
            if nm and nm.startswith(pre + " "):
                tier_of[k] = T
    equip = [k for k in new_keys if g(m_items[k], "ItemID") and k in tier_of
             and g(g(m_items[k], "EquipmentRevision"), "ATK") is not None
             and any(g(g(m_items[k], "EquipmentRevision"), s) for s in make_gear.STAT_FIELD)]
    single = [name_of[k] for k in equip
              if sum(1 for f in make_gear.STAT_FIELD.values()
                     if g(m_items[k], "EquipmentRevision")[f] > 0) < 2]
    r.check(not single, f"all {len(equip)} new equipment pieces carry 2+ stats",
            f"{len(single)} pieces carry a single stat: {single[:5]}")
    # weapons are categories 0-6; HP / SP / regen on a weapon do nothing in battle (user)
    def is_weapon(k):
        cat = g(m_items[k], "EquipmentCategory")
        return int(cat.rsplit("NewEnumerator", 1)[1]) <= 6
    rev = lambda k, s: g(m_items[k], "EquipmentRevision")[make_gear.STAT_FIELD[s]]
    dead = [name_of[k] for k in equip if is_weapon(k)
            and (rev(k, "HP") or rev(k, "MP") or any(
                g(a, "AilmentName").endswith("_FIXED_REGENERATION")
                for a in g(m_items[k], "Ailment")))]
    r.check(not dead, "no weapon carries HP, SP or regen (they do nothing on weapons)",
            f"{len(dead)} weapons carry dead HP/SP/regen: {dead[:5]}")
    no_sp = [name_of[k] for k in equip if tier_of[k] >= 70 and not is_weapon(k)
             and rev(k, "MP") <= 0]
    r.check(not no_sp, "every tier 70+ armour piece and accessory boosts SP",
            f"{len(no_sp)} tier 70+ pieces have no SP: {no_sp[:5]}")
    hi = [k for k in equip if tier_of[k] >= 80 and not is_weapon(k)]
    regen = [k for k in hi if any(g(a, "AilmentName") == "ADD_MP_FIXED_REGENERATION"
                                  for a in g(m_items[k], "Ailment"))]
    log.info("  SP regen on %d of %d tier 80+ armour/accessories", len(regen), len(hi))
    if hi and len(regen) < len(hi) // 3:
        r.warn(f"SP regen is rare at tier 80+ ({len(regen)}/{len(hi)})")

    # descriptions must state every stat and effect exactly - shops don't show them all.
    # Regenerate each one from the row's REAL data (stats, effect chances and durations,
    # immunities) with the same function the build uses, and require an exact match.
    disease_name = {i: n for n, i in make_gear.DISEASE_INDEX.items()}
    wrong, long_ = [], []
    for k in equip:
        row = m_items[k]
        rev = g(row, "EquipmentRevision")
        stats = {s: rev[f] for s, f in make_gear.STAT_FIELD.items() if rev[f]}
        ails = [(g(a, "AilmentName"), g(a, "InvocationValue"), g(a, "InvocationTurn"),
                 g(a, "DiseaseRate")) for a in g(row, "Ailment")
                if g(a, "AilmentName") not in ("None", "0")]
        immune = tuple(disease_name[i] for i, v in enumerate(g(row, "DiseaseResist"))
                       if v and i in disease_name)
        try:
            expect = catalogue.describe(stats, ails, immune)
        except Exception as exc:                   # noqa: BLE001
            expect = f"<cannot describe: {exc}>"
        ds = desc_of.get(k, "")
        if ds != expect:
            wrong.append((name_of[k], ds, expect))
        if ds.count(catalogue.NL) + 1 > catalogue.MAX_LINES or any(
                len(x) > catalogue.MAX_LINE_CHARS for x in ds.split(catalogue.NL)):
            long_.append(name_of[k])
    r.check(not wrong, f"all {len(equip)} descriptions match the item data exactly",
            f"{len(wrong)} descriptions disagree with the item data: {wrong[:2]}")
    r.check(not long_, f"all descriptions fit in {catalogue.MAX_LINES} lines of "
                       f"{catalogue.MAX_LINE_CHARS} chars",
            f"{len(long_)} descriptions overflow: {long_[:5]}")

    # IDs must match the registry so a rebuild never turns an owned item into another
    if os.path.exists(make_gear.REGISTRY):
        import json
        with open(make_gear.REGISTRY, encoding="utf-8") as f:
            reg = json.load(f)
        moved = [(name_of[k], g(m_items[k], "ItemID"), reg.get(name_of[k])) for k in new_keys
                 if name_of.get(k) in reg and reg[name_of[k]] != g(m_items[k], "ItemID")]
        r.check(not moved, f"all new item IDs match {os.path.basename(make_gear.REGISTRY)}",
                f"{len(moved)} item IDs moved: {moved[:5]}")
    else:
        r.warn("no item registry - IDs are not guaranteed stable across rebuilds")

    # ---- 3. shops ---------------------------------------------------------
    log.info("[3] shops")
    if PURCHASE + ".uexp" in present:
        m_pur = table(mod, PURCHASE)
        bad = [k for k, v in m_pur.items() if g(v, "ItemLabel") not in m_items]
        r.check(not bad, f"all {len(m_pur)} purchase entries point at a real item",
                f"{len(bad)} purchase entries point at a missing item: {bad[:5]}")
        m_shop = table(mod, SHOP)
        dangling = []
        for k, v in m_shop.items():
            for lab in g(v, "LabelList"):
                if lab not in m_pur:
                    dangling.append((k, lab))
        r.check(not dangling, f"all shop labels across {len(m_shop)} shops resolve",
                f"{len(dangling)} dangling shop labels: {dangling[:5]}")
        b_shop = table(base, SHOP)
        for row in ("Sea_L_A_SHOP_w", "Sea_L_A_SHOP_i"):
            before = len(g(b_shop[row], "LabelList"))
            after = len(g(m_shop[row], "LabelList"))
            log.info("  %s: %d -> %d entries", row, before, after)
        other_changed = [k for k in b_shop
                         if k not in ("Sea_L_A_SHOP_w", "Sea_L_A_SHOP_i")
                         and str(b_shop[k]) != str(m_shop[k])]
        r.check(not other_changed, "no other shop was altered",
                f"{len(other_changed)} other shops changed: {other_changed[:5]}")
    else:
        r.warn("no shop tables in pak")

    # ---- 4. enemies -------------------------------------------------------
    log.info("[4] enemies")
    b_en = table(base, B.ENEMY)
    m_en = table(mod, B.ENEMY)
    bosses, supers = B.boss_sets(base)
    drops_bad = [k for k, v in m_en.items()
                 if g(v, "HaveItemID") not in ("None", "") and g(v, "HaveItemID") not in m_items]
    r.check(not drops_bad, "every enemy drop points at a real item",
            f"{len(drops_bad)} enemies drop a missing item: {drops_bad[:5]}")

    # bosses and superbosses: stats only ever raised, and a superboss's combat stats only
    # once the world floor passes the danger it was built for
    _save, _prog = B.quests_done()
    world, _why = B.world_floor(_prog, B.party_level(_save), B.completion(_save)["share"])
    cls0 = B.enemy_classes(base, b_en)
    curve0, levels0 = B.build_curve(b_en, bosses)
    natives = B.boss_natives(base, b_en, cls0, curve0, levels0)
    pinned = (lambda k: (B.FINAL_BOSS_DANGER and k.startswith(B.FINAL_BOSS_PREFIX))
              or (B.REVENANT_MIN_DANGER > world and k.startswith(B.REVENANT_PREFIX)))
    early = [k for k in b_en if cls0[k] == "super" and natives[k] >= world and not pinned(k)
             and any(
        g(g(m_en[k], "Param"), s_) != g(g(b_en[k], "Param"), s_)
        for s_ in ("ATK", "MATK", "DEF", "MDEF", "ACC"))]
    r.check(not early, f"no superboss strengthened before the world (danger {world}) "
                       f"passes its native danger",
            f"{len(early)} superbosses scaled early: {early[:5]}")
    boss_down = [k for k in b_en if cls0[k] in ("boss", "super") and any(
        g(g(m_en[k], "Param"), s_) < g(g(b_en[k], "Param"), s_) for s_ in B.STATS)]
    r.check(not boss_down, "no boss stat lowered", f"bosses weakened: {boss_down[:5]}")

    # rows the game never rolls as random encounters must be exactly as shipped
    cls = B.enemy_classes(base, b_en)
    counts = collections.Counter(cls.values())
    log.info("  enemy classes: %s", dict(counts))
    for c, label in (("npc", "Provoke/Challenge opponents"), ("cat", "caits"),
                     ("other", "unreachable rows")):
        moved = [k for k in b_en if cls[k] == c and str(b_en[k]) != str(m_en[k])]
        r.check(not moved, f"all {counts[c]} {label} exactly as shipped",
                f"{len(moved)} {label} were changed: {moved[:5]}")

    # a drop may only be replaced if the vanilla item is still obtainable (sold somewhere)
    if PURCHASE + ".uexp" in present:
        sold = {g(v, "ItemLabel") for v in table(base, PURCHASE).values()}
        lost = [(k, g(b_en[k], "HaveItemID")) for k in b_en
                if g(b_en[k], "HaveItemID") != g(m_en[k], "HaveItemID")
                and g(b_en[k], "HaveItemID") not in sold | {"None", ""}]
        r.check(not lost, "no unique vanilla drop was replaced",
                f"{len(lost)} unique drops replaced (now unobtainable): {lost[:5]}")

    # H'aanit's summons: only ever raised, and only for capturable random enemies
    INV = B.INVADE
    if INV + ".uexp" in present:
        b_inv, m_inv = table(base, INV), table(mod, INV)
        lower = [k for k in b_inv for f in B.SUMMON_STATS
                 if g(g(m_inv[k], "Parameter"), f) < g(g(b_inv[k], "Parameter"), f)]
        r.check(not lower, "no summon was weakened",
                f"{len(lower)} summons weakened: {lower[:5]}")
        allowed = {g(v, "InvadeMonsterID") for k, v in b_en.items()
                   if cls[k] == "random" and g(v, "TameEnable")}
        stray = [k for k in b_inv if k not in allowed and str(b_inv[k]) != str(m_inv[k])]
        r.check(not stray, "summons changed only for capturable random enemies",
                f"{len(stray)} unrelated summons changed: {stray[:5]}")
        raised = sum(1 for k in b_inv if str(b_inv[k]) != str(m_inv[k]))
        log.info("  %d captured-beast summons raised", raised)

    weaker = []
    for k, v in m_en.items():
        if k in bosses:
            continue
        prm = g(v, "Param")
        bprm = g(b_en[k], "Param")
        for s in ("HP", "ATK", "DEF"):
            if g(prm, s) < g(bprm, s):
                weaker.append((k, s))
    r.check(not weaker, "no regular enemy was made weaker than it shipped",
            f"{len(weaker)} enemy stats went DOWN: {weaker[:5]}")

    lv = collections.Counter(g(v, "EnemyLevel") for k, v in m_en.items() if k not in bosses)
    log.info("  regular enemy levels: %s", dict(sorted(lv.items())[:6]))

    boss_hp = [(g(g(m_en[k], "Param"), "HP"), g(g(b_en[k], "Param"), "HP"), k)
               for k in bosses if k in m_en and k not in supers]
    if boss_hp:
        grew = sum(1 for a, b, _ in boss_hp if a > b)
        log.info("  %d/%d normal bosses gained HP", grew, len(boss_hp))
        example = max(boss_hp, key=lambda x: x[1])
        log.info("  biggest: %s %d -> %d", example[2], example[1], example[0])

    # ---- 4b. encounter rate ----------------------------------------------
    VOL = B.VOLUME
    if VOL + ".uexp" in present:
        b_vol = table(base, VOL)
        m_vol = table(mod, VOL)
        before = [g(v, "EncountStepMin") for v in b_vol.values() if g(v, "EncountStepMin") > 0]
        after = [g(m_vol[k], "EncountStepMin") for k, v in b_vol.items()
                 if g(v, "EncountStepMin") > 0]
        ratio = (sum(after) / sum(before)) if before else 1.0
        if B.PERMANENT_EVASIVE_MANEUVERS:
            r.check(ratio > 1.5,
                    f"encounter steps stretched x{ratio:.2f} (Evasive Maneuvers baked in)",
                    f"encounter steps only x{ratio:.2f}; expected a meaningful increase")
        else:
            r.check(abs(ratio - 1.0) < 0.01, "encounter rate unchanged",
                    f"encounter steps changed x{ratio:.2f} unexpectedly")
        log.info("  median steps between encounters: %d -> %d",
                 sorted(before)[len(before) // 2], sorted(after)[len(after) // 2])

    # ---- 5. global params -------------------------------------------------
    log.info("[5] tunables")
    if PARAMS + ".uexp" in present:
        m_par = table(mod, PARAMS)
        cap = {k.split("_")[0]: v for k, v in m_par["BATTLE_DAMAGE_CAP"].items()}
        r.check(int(cap["Init"]) > 9999 and int(cap["Param"]) > 9999,
                f"damage cap raised (Init={cap['Init']}, Param={cap['Param']})",
                f"damage cap not raised: {cap}")
        if B.PERMANENT_EVASIVE_MANEUVERS:
            ceil = {k.split("_")[0]: v for k, v in m_par["MAX_ENCOUNT_STEP_COUNT"].items()}
            # the per-area step counts are pointless if the counter is still clamped at 300
            r.check(int(ceil["Param"]) >= 1000,
                    f"encounter step ceiling raised (MAX_ENCOUNT_STEP_COUNT={ceil['Param']})",
                    f"step ceiling still {ceil['Param']}; doubled steps will be clamped")
        expected_rows = {"BATTLE_DAMAGE_CAP", "MAX_ENCOUNT_STEP_COUNT",
                         "PLAYER_STATUS_RANGE", "PLAYER_STATUS_HP_RANGE",
                         "STEAL_PROBABILITY_LEVEL_OVER", "STEAL_PROBABILITY_LEVEL_LESS_THAN"}
        cap = {k.split("_")[0]: v for k, v in m_par["PLAYER_STATUS_RANGE"].items()}
        r.check(int(cap["Max"]) == B.PLAYER_STAT_CAP,
                f"player stat cap = {cap['Max']}", f"player stat cap is {cap['Max']}, "
                f"expected {B.PLAYER_STAT_CAP}")
        b_par = table(base, PARAMS)
        other = [k for k in b_par if k not in expected_rows
                 and str(b_par[k]) != str(m_par[k])]
        r.check(not other, "no unexpected tunable changed",
                f"unexpected tunable changes: {other[:5]}")
    else:
        r.warn("GameParamDefineTable not in pak (damage cap unchanged)")

    # ---- 5a. blueprint patch: elemental boosts read from every equipped slot ----
    import blueprint_patch
    if blueprint_patch.ASSET + ".uexp" in present:
        problems = blueprint_patch.check(base, mod)
        r.check(not problems, "blueprint patches exactly as planned: elemental boosts on "
                              "every equipped piece (BattlePlayerBP), battle money follows "
                              "the equipment JP bonus (BattleManagerBP)",
                "; ".join(problems))
    else:
        import build_all
        if build_all.NEW_GEAR:
            r.check(False, "", "BattlePlayerBP patch missing: Sigils and Hearts do nothing")

    if blueprint_patch.ACTION + ".uexp" in present:
        try:
            good = (mod.read(blueprint_patch.ACTION + ".uexp")
                    == blueprint_patch.dash_toggle_files(base)[blueprint_patch.ACTION + ".uexp"])
        except Exception as exc:                   # noqa: BLE001
            good = False
            log.info("  dash toggle check failed: %s", exc)
        r.check(good, "dash toggle patch exactly as planned (ActionController_Impl)",
                "ActionController_Impl differs from the planned dash-toggle patch")

    # ---- 5b. battle tunables: only Tressa's Collect amounts, and only upward ----
    BP = B.BATTLE_PARAMS
    if BP + ".uexp" in present:
        b_bp, m_bp = table(base, BP), table(mod, BP)
        other = [k for k in b_bp if k not in B.TRESSA_COLLECT_ROWS and str(b_bp[k]) != str(m_bp[k])]
        r.check(not other, "only Tressa's Collect rows changed in BattleParamDefineTable",
                f"unexpected battle tunable changes: {other[:5]}")
        down = [k for k in B.TRESSA_COLLECT_ROWS
                if float(g(m_bp[k], "Param")) < float(g(b_bp[k], "Param"))]
        r.check(not down, "Tressa's Collect amounts never below vanilla",
                f"Collect amounts lowered: {down}")
        log.info("  Tressa Collect: %s -> %s leaves (top find)",
                 g(b_bp[B.TRESSA_COLLECT_ROWS[-1]], "Param"),
                 g(m_bp[B.TRESSA_COLLECT_ROWS[-1]], "Param"))

    # ---- 5c. catch-up leveling: cheaper low levels, the party's levels untouched ----
    GR = B.GROW
    if GR + ".uexp" in present:
        b_gr, m_gr = table(base, GR), table(mod, GR)
        party = B.party_level(B.quests_done()[0])
        thr = B.catchup_threshold(B.quests_done()[0])
        moved_high = [k for k in b_gr if int(k) >= thr and
                      g(b_gr[k], "TotalExp") != g(m_gr[k], "TotalExp")]
        r.check(not moved_high, f"EXP totals unchanged from level {thr} up (party {party})",
                f"EXP totals changed at levels the party has reached: {moved_high[:5]}")
        tots = [g(m_gr[k], "TotalExp") for k in sorted(m_gr, key=int)]
        nxts = [g(m_gr[k], "NextExp") for k in sorted(m_gr, key=int)]
        mono = all(b > a for a, b in zip(tots, tots[1:]))
        cons = all(nxts[i] == tots[i + 1] - tots[i] for i in range(len(tots) - 1))
        r.check(mono and cons, "EXP table increasing and NextExp consistent",
                "EXP table broken (not increasing or NextExp inconsistent)")
        stats_moved = [k for k in b_gr if str(g(b_gr[k], "Parameter")) != str(g(m_gr[k], "Parameter"))]
        r.check(not stats_moved, "level stat growth untouched",
                f"stat growth changed: {stats_moved[:5]}")

    # ---- 6. structural ----------------------------------------------------
    log.info("[6] structure")
    for path in sorted({n[:-len(".uexp")] for n in present if n.endswith(".uexp")}):
        if path in (blueprint_patch.ASSET, blueprint_patch.MANAGER, blueprint_patch.ACTION):
            continue                            # a blueprint, checked byte-exactly in [5a]
        try:
            dt.verify(mod.read(path + ".uasset"), mod.read(path + ".uexp"))
            r.ok(f"{path.split('/')[-1]} structure OK")
        except Exception as exc:                   # noqa: BLE001
            r.fail(f"{path.split('/')[-1]} structure broken: {exc}")

    log.info("")
    log.info("RESULT: %d error(s), %d warning(s)", r.errors, r.warnings)
    return r.errors


if __name__ == "__main__":
    import config
    config.apply(config.load())
    target = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        paths.mods_dir(), "ZZ_OctopathWorldOverhaul_p.pak")
    sys.exit(buildlog.run(main, target, name="validate") or 0)
