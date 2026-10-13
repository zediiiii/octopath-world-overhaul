"""Loot that keeps pace with the world: enemy drops, treasure chests and side-story rewards.

Everything here is decided from the world's danger (the build's floor), so a new game and a
late save get the same rules: nothing depends on what the player has already opened.

- Consumables climb a ladder (LADDERS) one rung at every UPGRADE_STEPS danger. Items already
  at the top of their ladder - or with none (status cures, Olive of Life (L), the jams) -
  stay as they are and come in bigger stacks instead (count_mult).
- Gear becomes tier gear of the same equipment category with the most similar stats and
  status immunities, from the best tier the world has opened; with no match, money.
- Money, and junk sold for money, is multiplied by money_mult (1 in the vanilla opening).
- Side stories keep every reward and add a world-level counterpart of each (bigger for the
  game's later-chapter stories), in the reward slots the game leaves free; money scales.
"""
import collections
import math
import struct

import datatable as dt
import make_gear
import uasset

# Rungs are vanilla ItemDB keys or our minted items (by name); an item's rung is its first
# place in any ladder. Alfyn's concoct materials are left alone.
LADDERS = [
    ["ITM_095", "ITM_078", "ITM_079", "Vital Draught", "ITM_007", "ITM_018"],  # HP, one ally
    ["ITM_023", "ITM_078", "ITM_079", "Vital Draught", "ITM_007", "ITM_018"],  # Ali's Bread
    ["ITM_101", "ITM_086", "ITM_087", "Invigorating Draught", "ITM_007", "ITM_018"],  # SP
    ["ITM_080", "Vital Cask"],                           # HP, whole party
    ["ITM_088", "Invigorating Cask"],                    # SP, whole party
    ["ITM_093", "ITM_009", "ITM_010", "ITM_017"],        # revive: herb, olives
    ["ITM_143", "ITM_144", "ITM_145", "ITM_018"],        # BP: pomegranates, then the jam
] + [[base, m, lg, f"{el} Soulstone (XL)"] for el, base, m, lg in (
    ("Fire", "ITM_028", "ITM_029", "ITM_137"), ("Ice", "ITM_030", "ITM_031", "ITM_138"),
    ("Thunder", "ITM_032", "ITM_033", "ITM_139"), ("Wind", "ITM_034", "ITM_035", "ITM_140"),
    ("Light", "ITM_036", "ITM_115", "ITM_141"), ("Shadow", "ITM_037", "ITM_116", "ITM_142"))
] + [[s, m, lg, f"{name} (XL)"] for name, s, m, lg in (
    ("Nourishing Nut", "ITM_050", "ITM_049", "ITM_048"),
    ("Invigorating Nut", "ITM_053", "ITM_052", "ITM_051"),
    ("Fortifying Nut", "ITM_056", "ITM_055", "ITM_054"),
    ("Tough Nut", "ITM_059", "ITM_058", "ITM_057"),
    ("Magic Nut", "ITM_062", "ITM_061", "ITM_060"),
    ("Resistant Nut", "ITM_065", "ITM_064", "ITM_063"),
    ("Sharp Nut", "ITM_068", "ITM_067", "ITM_066"),
    ("Slippery Nut", "ITM_071", "ITM_070", "ITM_069"),
    ("Critical Nut", "ITM_074", "ITM_073", "ITM_072"),
    ("Light Nut", "ITM_077", "ITM_076", "ITM_075"))]
UPGRADE_STEPS = (35, 50, 65, 80)  # world danger at which loot climbs one more rung
MONEY_BASE = 12                   # money x (danger / 12): x1 in the opening, x6 at 72
STACKS = ((50, 2), (80, 3))       # top-rung / unladdered consumables: count x2 at 50, x3 at 80
MAX_COUNT = 9
# side stories: chapter-1 stories add a smaller bonus than the game's late ones
STORY_TIER_SCALE = {1: 0.5, 2: 0.75, 3: 1.0, 4: 1.25}
STAT_KEYS = ("HP", "MP", "ATK", "DEF", "MATK", "MDEF", "ACC", "EVA", "CON", "AGI")


def climb(floor):
    return sum(1 for d in UPGRADE_STEPS if floor >= d)


def money_mult(floor):
    return max(1.0, floor / MONEY_BASE)


def count_mult(floor):
    return max([1] + [m for d, m in STACKS if floor >= d])


def _g(row, pre):
    return next(v for k, v in row.items() if k.split("_")[0] == pre)


class Upgrader:
    """World-level replacements for one build (floor, minted items, open gear tiers)."""

    def __init__(self, floor, minted, base_items, open_tiers, lookahead):
        self.floor, self.minted, self.items = floor, minted, base_items
        self.open_tiers, self.lookahead = open_tiers, lookahead
        self.by_name = {m["name"]: m for m in minted}
        self.rung = {}
        for ladder in LADDERS:
            for n, item in enumerate(ladder):
                self.rung.setdefault(item, (ladder, n))
        self.climb = climb(floor)
        self.money = money_mult(floor)
        self.stack = count_mult(floor)
        self.gear = [m for m in minted if m.get("kind") in ("weapon", "armour", "accessory")]

    # ---- what an item is ------------------------------------------------------------
    def category(self, item):
        row = self.items.get(item)
        return _g(row, "EquipmentCategory") if row else None

    def is_gear(self, item):
        c = self.category(item)
        return bool(c) and not c.endswith("NewEnumerator0")

    def available(self, name):
        """A minted rung only once its tier is open (XL soulstones 70, XL nuts 80)."""
        m = self.by_name.get(name)
        return m is None or not m.get("gated") or m["tier"] <= self.floor + self.lookahead

    def price(self, item):
        row = self.items.get(item)
        return int(_g(row, "BuyPrice")) if row else 0

    # ---- replacements ------------------------------------------------------------------
    def consumable(self, item, count, steps=None):
        """-> (item, count): climbed `steps` rungs (default: the world's), or a bigger stack
        when it can climb no further."""
        steps = self.climb if steps is None else steps
        if item in self.rung:
            ladder, n = self.rung[item]
            top = min(n + steps, len(ladder) - 1)
            while top > n and not self.available(ladder[top]):
                top -= 1
            if top > n:
                return ladder[top], count
        return item, min(MAX_COUNT, count * self.stack) if self.stack > 1 else count

    def tier_gear(self, item, tier_index=-1):
        """The open-tier piece most like `item` (same category; similar stats and status
        immunities), or None. tier_index picks among the open tiers (-1 = the best)."""
        if not self.open_tiers:
            return None
        cat = self.category(item)
        tier = self.open_tiers[max(-len(self.open_tiers), tier_index)] \
            if tier_index < 0 else self.open_tiers[min(tier_index, len(self.open_tiers) - 1)]
        pool = [m for m in self.gear if m["tier"] == tier and self.category(m["template"]) == cat]
        if not pool:
            return None
        row = self.items[item]
        rev = {k.split("_")[0]: v for k, v in _g(row, "EquipmentRevision").items()}
        want = [float(rev.get(k, 0) or 0) for k in STAT_KEYS]
        imm = {i for i, x in enumerate(_g(row, "DiseaseResist")) if x}

        def score(m):
            have = [float(m["stats"].get(k, 0) or 0) for k in STAT_KEYS]
            dot = sum(a * b for a, b in zip(want, have))
            n = math.sqrt(sum(a * a for a in want)) * math.sqrt(sum(b * b for b in have))
            mimm = {make_gear.DISEASE_INDEX[s] for s in m.get("immune") or ()}
            return (dot / n if n else 0) + (0.5 * len(imm & mimm) / len(imm) if imm else 0)
        return max(pool, key=lambda m: (score(m), -m["id"]))

    def money_for(self, item, count):
        """Money standing in for an item: its shop price, world-scaled."""
        return int(max(100, self.price(item)) * count * self.money)


# ---- writing references ----------------------------------------------------------------------
class _Names:
    """FName references into one table's name list, adding vanilla keys as needed."""

    def __init__(self, ua):
        self.ua = ua
        self.names, _ = uasset.names_of(ua)

    def ref(self, key, minted_by_name):
        if key in minted_by_name:
            if make_gear.ROW_ANCHOR not in self.names:
                self._add(make_gear.ROW_ANCHOR)
            return self.names.index(make_gear.ROW_ANCHOR), minted_by_name[key]["row_num"]
        if key not in self.names:
            self._add(key)
        return self.names.index(key), 0

    def _add(self, key):
        self.ua = dt.add_names(self.ua, [key])
        self.names, _ = uasset.names_of(self.ua)


def _bool_offsets(ue, names, field):
    """Value bytes of every BoolProperty named `field` (stored in the tag itself)."""
    idx = next(i for i, n in enumerate(names) if n.split("_")[0] == field)
    pat = struct.pack("<ii", idx, 0)
    out, p = [], 0
    while True:
        p = ue.find(pat, p)
        if p < 0:
            return out
        if names[struct.unpack_from("<i", ue, p + 8)[0]] == "BoolProperty":
            out.append(p + 24)
        p += 4


# ---- treasure chests ----------------------------------------------------------------------------
OBJECTS = "Octopath_Traveler/Content/Object/Database/ObjectData"


def chests(ua, ue, up, log=print):
    """Rewrite every treasure chest in ObjectData for the world. -> (ua, ue)."""
    import build_difficulty_mod as B
    rows = uasset.read_datatable(ua, ue)
    keys = list(rows)
    ue = bytearray(ue)
    names = _Names(ua)
    item_offs = dt.field_offsets_in(bytes(ue), names.names, 0, len(ue), "HaveItemLabel",
                                    "NameProperty")
    cnt_offs = B.int_offsets(ua, bytes(ue), "HaveItemCnt", expect=len(keys))
    money_offs = _bool_offsets(bytes(ue), names.names, "IsMoney")
    if not (len(item_offs) == len(money_offs) == len(keys)):
        raise RuntimeError("ObjectData layout not as expected")
    did = collections.Counter()
    for i, k in enumerate(keys):
        if not k.startswith("TrsrBx"):
            continue
        v = rows[k]
        cnt = v["HaveItemCnt"]
        if v["IsMoney"]:
            new = int(cnt * up.money)
            if new != cnt:
                struct.pack_into("<i", ue, cnt_offs[i], new)
                did["money"] += 1
            continue
        item = v["HaveItemLabel"]
        if item in (None, "None") or item not in up.items:
            continue
        if up.is_gear(item):
            m = up.tier_gear(item)
            if m:
                dt.set_fname(ue, item_offs[i], *names.ref(m["name"], up.by_name))
                did["gear"] += 1
            elif up.open_tiers:
                ue[money_offs[i]] = 1
                struct.pack_into("<i", ue, cnt_offs[i], up.money_for(item, cnt))
                did["gear -> money"] += 1
            continue
        detail = str(_g(up.items[item], "UseType"))
        if detail.endswith("NewEnumerator0") and up.money > 1 and item not in up.rung:
            # treasures that only sell ("fetches a fair price"): their worth, world-scaled
            ue[money_offs[i]] = 1
            struct.pack_into("<i", ue, cnt_offs[i], up.money_for(item, cnt) // 2)
            did["valuables -> money"] += 1
            continue
        new_item, new_cnt = up.consumable(item, cnt)
        if new_item != item:
            dt.set_fname(ue, item_offs[i], *names.ref(new_item, up.by_name))
            did["consumable upgraded"] += 1
        if new_cnt != cnt:
            struct.pack_into("<i", ue, cnt_offs[i], new_cnt)
            did["bigger stack"] += 1
    ua = names.ua
    uasset.read_datatable(ua, bytes(ue))                 # must still parse
    log(f"treasure chests at danger {up.floor}: " + (", ".join(
        f"{n} {what}" for what, n in did.items()) or "as shipped"))
    return ua, bytes(ue)


# ---- side-story rewards ------------------------------------------------------------------------
MISSIONS = "Octopath_Traveler/Content/Mission/Database/Sub_MissionRecord"


def _array_offsets(ue, names, field):
    """-> [offset of the first element] of every NameProperty ArrayProperty `field`."""
    idx = next(i for i, n in enumerate(names) if n.split("_")[0] == field)
    pat = struct.pack("<ii", idx, 0)
    out, p = [], 0
    while True:
        p = ue.find(pat, p)
        if p < 0:
            return out
        if names[struct.unpack_from("<i", ue, p + 8)[0]] == "ArrayProperty":
            # name8 type8 size4 index4 inner8 hasguid1, then the element count
            out.append(p + 33 + 4)
        p += 4


def side_stories(ua, ue, up, log=print):
    """Scale every side story's money and add world-level counterparts of its rewards in
    the free reward slots (the existing rewards are kept). -> (ua, ue)."""
    import build_difficulty_mod as B
    rows = uasset.read_datatable(ua, ue)
    keys = list(rows)
    ue = bytearray(ue)
    names = _Names(ua)
    money_offs = B.int_offsets(ua, bytes(ue), "RewardMoney", expect=len(keys))
    par_offs = _array_offsets(bytes(ue), names.names, "RewardParam")
    if len(par_offs) != len(keys):
        raise RuntimeError("Sub_MissionRecord layout not as expected")
    added = collections.Counter()
    for i, k in enumerate(keys):
        v = rows[k]
        money = _g(v, "RewardMoney")
        if money and up.money > 1:
            struct.pack_into("<i", ue, money_offs[i], int(money * up.money))
            added["money scaled"] += 1
        if not up.climb and not up.open_tiers:
            continue
        # SMR_SS_<area><chapter>_..: the chapter-1 towns' stories are tier 1; EX ones late
        code = k[7:10]
        tier = 4 if code.startswith("EX") or not code[2:].isdigit() else max(1, int(code[2]))
        scale = STORY_TIER_SCALE.get(tier, 1.0)
        par = list(_g(v, "RewardParam"))
        pairs = [(par[j], par[j + 1]) for j in range(0, len(par) - 1, 2)
                 if par[j] not in (None, "None")]
        free = 3 - len(pairs)
        bonus = []
        for item, n in pairs:
            if item not in up.items:
                continue
            if up.is_gear(item):
                m = up.tier_gear(item, -1 if tier >= 3 else -2)
                if m:
                    bonus.append((m["name"], 1))
            else:
                steps = max(1, round(up.climb * scale)) if up.climb else 0
                new, cnt = up.consumable(item, int(n) if str(n).isdigit() else 1, steps)
                if new != item or cnt > 1:
                    bonus.append((new, max(1, round(cnt * scale))))
        if not pairs and up.climb:
            # stories that paid only money: a stack of the world's best restorative
            new, _ = up.consumable("ITM_078", 1, up.climb)
            bonus.append((new, max(1, round(2 * scale))))
        for item, cnt in bonus[:free]:
            j = len(pairs) * 2
            dt.set_fname(ue, par_offs[i] + 8 * j, *names.ref(item, up.by_name))
            dt.set_fname(ue, par_offs[i] + 8 * (j + 1), *names.ref(str(min(MAX_COUNT, cnt)), {}))
            pairs.append((item, cnt))
            added["item added"] += 1
    ua = names.ua
    uasset.read_datatable(ua, bytes(ue))
    log(f"side-story rewards at danger {up.floor}: " + (", ".join(
        f"{n} {what}" for what, n in added.items()) or "as shipped"))
    return ua, bytes(ue)
