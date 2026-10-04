"""Core logic: read/modify nut ("Doping") stats and nut inventory in an Octopath Traveler save."""
import os
import shutil
import datetime
import gvas


CHAR_NAMES = {1: "Olberic", 2: "Tressa", 3: "Cyrus", 4: "Primrose",
              5: "H'aanit", 6: "Therion", 7: "Ophilia", 8: "Alfyn"}

# (label, DopingParam field prefix, nut name, [(item_id, points), ...] small->large)
STATS = [
    ("Max HP",    "HP",   "Nourishing Nut",   [(60, 75), (61, 150), (62, 300)]),
    ("Max SP",    "MP",   "Invigorating Nut", [(63, 3), (64, 6), (65, 12)]),
    ("Phys. Atk", "ATK",  "Fortifying Nut",   [(66, 7), (67, 14), (68, 28)]),
    ("Phys. Def", "DEF",  "Tough Nut",        [(69, 7), (70, 14), (71, 28)]),
    ("Elem. Atk", "MATK", "Magic Nut",        [(72, 7), (73, 14), (74, 28)]),
    ("Elem. Def", "MDEF", "Resistant Nut",    [(75, 7), (76, 14), (77, 28)]),
    ("Accuracy",  "ACC",  "Sharp Nut",        [(78, 7), (79, 14), (80, 28)]),
    ("Evasion",   "EVA",  "Slippery Nut",     [(81, 7), (82, 14), (83, 28)]),
    ("Critical",  "CON",  "Critical Nut",     [(84, 7), (85, 14), (86, 28)]),
    ("Speed",     "AGI",  "Light Nut",        [(87, 7), (88, 14), (89, 28)]),
]
STAT_KEYS = [s[1] for s in STATS]
NUT_POINTS = {iid: pts for s in STATS for iid, pts in s[3]}
MAX_STACK = 99


def _field(struct_props, prefix):
    for p in struct_props:
        if p.name.split("_")[0] == prefix:
            return p
    raise KeyError(prefix)


def find_saves():
    import paths
    out = paths.find_saves()

    def key(p):
        n = os.path.basename(p)[8:-4]
        return int(n) if n.isdigit() else 999
    return sorted(out, key=key)


def slot_summary(path):
    try:
        s = gvas.SaveFile.load(path)
        sd = s.get("slotData").value
        g = lambda n: _field(sd, n).value
        # slotData field names have no GUID suffix; match exactly
        d = {p.name: p.value for p in sd}
        t = d["PlayTime"]
        leader = CHAR_NAMES.get(d["MainMemberCharacterID"][0], "?")
        return (f"{d['SaveDate_Year']}-{d['SaveDate_Month']:02}-{d['SaveDate_Day']:02} "
                f"{d['SaveDate_Hour']:02}:{d['SaveDate_Minute']:02}  |  {leader} Lv{d['LeaderCharaLevel']}"
                f"  |  {t // 3600}h{t // 60 % 60:02}m")
    except Exception as e:  # noqa
        return f"(unreadable: {e})"


class SaveEditor:
    def __init__(self, path):
        self.path = path
        with open(path, "rb") as f:
            self.original = f.read()
        self.save = gvas.SaveFile(self.original)
        if self.save.to_bytes() != self.original:
            raise RuntimeError("Save did not round-trip cleanly; refusing to edit.")
        # characters
        self.chars = []  # (char_id, name, level, doping_struct_props)
        for m in self.save.get("PlayerMember").value:
            cid = _field(m, "CharacterID").value
            if cid not in CHAR_NAMES:
                continue
            self.chars.append((cid, CHAR_NAMES[cid], _field(m, "Level").value,
                               _field(m, "DopingParam").value))
        bp = self.save.get("PlayerBackpack").value
        self.items = _field(bp, "ItemList").value  # list of [ItemID prop, Num prop]

    # ---- reading ----
    def doping(self, cid, key):
        for c in self.chars:
            if c[0] == cid:
                return _field(c[3], key).value
        raise KeyError(cid)

    def item_count(self, item_id):
        for e in self.items:
            if e[0].value == item_id:
                return e[1].value
        return 0

    def inventory_points(self, key):
        stat = STATS[STAT_KEYS.index(key)]
        return sum(self.item_count(iid) * pts for iid, pts in stat[3])

    def total_points(self, key):
        """All points of this stat: applied to characters + held as nuts."""
        return sum(self.doping(c[0], key) for c in self.chars) + self.inventory_points(key)

    # ---- writing ----
    def _set_item_count(self, item_id, count):
        for i, e in enumerate(self.items):
            if e[0].value == item_id:
                if count > 0:
                    e[1].value = count
                else:
                    # remove and compact, keeping list length constant
                    empty = self.items.pop(i)
                    empty[0].value = 0
                    empty[1].value = 0
                    self.items.append(empty)
                return
        if count <= 0:
            return
        for e in self.items:
            if e[0].value == 0 and e[1].value == 0:
                e[0].value = item_id
                e[1].value = count
                return
        raise RuntimeError("Inventory is full")

    @staticmethod
    def nuts_for(key, points):
        """Greedy large->small breakdown of `points` into nut counts. Returns {item_id: count}."""
        stat = STATS[STAT_KEYS.index(key)]
        out = {}
        rem = points
        for iid, pts in reversed(stat[3]):
            n = min(MAX_STACK, rem // pts)
            out[iid] = n
            rem -= n * pts
        if rem:
            raise ValueError(f"{stat[0]}: {points} points can't be expressed as whole nuts "
                             f"(leftover {rem}, or more than {MAX_STACK} of a nut).")
        return out

    def apply(self, alloc):
        """alloc: {char_id: {stat_key: value}}. Unassigned points become nuts in the inventory.
        Only stats whose allocation changed get their nut stacks rebuilt."""
        plan = {}
        for key in STAT_KEYS:
            total = self.total_points(key)
            assigned = sum(alloc[c[0]][key] for c in self.chars)
            changed = any(alloc[c[0]][key] != self.doping(c[0], key) for c in self.chars)
            if assigned > total:
                raise ValueError(f"{key}: assigned {assigned} > available {total}")
            if changed:
                plan[key] = self.nuts_for(key, total - assigned)
        for c in self.chars:
            for key in STAT_KEYS:
                _field(c[3], key).value = int(alloc[c[0]][key])
        for key, nuts in plan.items():
            for iid, n in nuts.items():
                self._set_item_count(iid, n)
        return plan

    def write(self, backup_dir):
        os.makedirs(backup_dir, exist_ok=True)
        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        base = os.path.basename(self.path)
        bak = os.path.join(backup_dir, f"{base[:-4]}_{stamp}.sav")
        shutil.copy2(self.path, bak)
        data = self.save.to_bytes()
        gvas.SaveFile(data)  # sanity: must re-parse
        tmp = self.path + ".tmp"
        with open(tmp, "wb") as f:
            f.write(data)
        os.replace(tmp, self.path)
        return bak
