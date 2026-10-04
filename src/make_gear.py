"""Mint brand-new equipment by cloning existing ItemDB rows and appending them.

New names/descriptions are appended to GameTextEN. Nothing existing is modified, so gear
you already own is untouched - these are genuinely new items with new IDs.
"""
import paths
import os
import struct
import pak
import uasset
import datatable as dt
import pakwrite

# our pak must sort last among ~mods so its tables win the override
OUT_PREFIX = "ZZ_"

ITEMS = "Octopath_Traveler/Content/Item/Database/ItemDB"
TEXT = "Octopath_Traveler/Content/GameText/Database/GameTextEN"

# FName numbers from here up are ours; nothing in the shipped data uses them.
FNUM_BASE = 9000
NEW_ID_BASE = 2700
# Every new gear row is named (ROW_ANCHOR, <unique number>). ROW_ANCHOR has to exist in the
# name table of every table that refers to the gear - ItemDB, PurchaseItemTable (shops) and
# EnemyDB (drops) - because an FName is an index into the file's own name table.
ROW_ANCHOR = "ITM_078"

STAT_FIELD = {
    "HP": "HP_38_60C1981648472447396094AC51E6861E",
    "MP": "MP_39_F930AFBC4A48BE8BF00009B7841D66D5",
    "ATK": "ATK_40_4AB44CD740D8A6BF06E3A0A6B62FF589",
    "DEF": "DEF_41_BAE3A0D84D0AD654D3F0D68D467163E3",
    "MATK": "MATK_42_6CE7342144ABD5515E1DCFB07DB6F9EA",
    "MDEF": "MDEF_43_F437EF5F447142384DD0BA91294B3A3B",
    "ACC": "ACC_44_C4B000CE4B3238F27EC316896A346DB8",
    "EVA": "EVA_45_D1A7250742962DB6306A7295D71AADE7",
    "CON": "CON_46_9BCE805749432E94492E49B0EE90D7FF",
    "AGI": "AGI_47_2F9420C345AFAAE3A5D6CC9F78B42D5D",
}


AILMENT_SLOTS = 4
# (InvocationTurn, DiseaseRate) exactly as shipped equipment uses them. Regeneration is the
# odd one out: shipped gear marks it -1 (permanent); everything passive is 0/0.
AILMENT_TIMING = {
    "ADD_HP_FIXED_REGENERATION": (-1, 0),
    "ADD_MP_FIXED_REGENERATION": (-1, 0),
    # Relic passives: battle buffs given the same permanent (-1 turn) timing that shipped
    # gear uses for regen - the closest data-only thing to an extra support skill.
    "ADD_HP_REGENERATION": (-1, 0),
    "ADD_AGI_UP": (-1, 0),
    "ADD_MDEF_UP": (-1, 0),
    "ADD_ATK_UP": (-1, 0),
    "ADD_MATK_UP": (-1, 0),
    "ADD_PARMNENT_CRITICAL": (-1, 0),
    "ADD_BP_REGENERATION": (-1, 0),
    "ADD_DIVINE_PROTECT": (-1, 0),
    "ADD_MAGIC_CRITICAL": (-1, 0),
    "ADD_RERAISE": (-1, 0),
}

# DiseaseResist slots, read off the shipped "Prevents X" talismans (ITM_AC_013..020)
DISEASE_INDEX = {"Poison": 0, "Silence": 1, "Blindness": 2, "Confusion": 3, "Sleep": 4,
                 "Terror": 5, "Unconsciousness": 6, "Instant Death": 7}

# Item IDs must never move once handed out: the save stores the ID, so a rebuild that
# reshuffled the catalogue would turn an owned item into a different one.
REGISTRY = os.path.join(paths.data_dir(), "item_registry.json")


class IdRegistry:
    """name -> ItemID, persisted. New names get fresh IDs; old IDs are never reused."""

    def __init__(self, path=REGISTRY):
        import json
        self.path = path
        self.ids = {}
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                self.ids = json.load(f)
        self.used = set()

    def id_for(self, name):
        if name in self.used:
            raise RuntimeError(f"duplicate item name in catalogue: {name}")
        self.used.add(name)
        if name not in self.ids:
            self.ids[name] = max([NEW_ID_BASE - 1] + list(self.ids.values())) + 1
        return self.ids[name]

    def save(self):
        """Write only if a new name was added (the shipped registry already covers every
        item, and an install folder may be read-only)."""
        import json
        if os.path.exists(self.path):
            with open(self.path, encoding="utf-8") as f:
                if json.load(f) == self.ids:
                    return
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self.ids, f, indent=1, sort_keys=True)


class GearForge:
    def __init__(self, registry=None):
        self.registry = registry
        self.p = pak.Pak(paths.base_pak())
        self.item_ua = self.p.read(ITEMS + ".uasset")
        self.item_ue = self.p.read(ITEMS + ".uexp")
        self.text_ua, self.text_ue, self.text_source = self._base_text()
        self.item_names, _ = uasset.names_of(self.item_ua)
        self.text_names, _ = uasset.names_of(self.text_ua)
        self.item_spans = {s[0]: s for s in dt.row_spans(self.item_ua, self.item_ue)}
        self.rows = uasset.read_datatable(self.item_ua, self.item_ue)
        self.new_items = []
        self.new_texts = []
        self.text_specs = []          # (FName number, key, string) - reused per language
        self.counter = 0
        g = lambda d, pre: next(vv for kk, vv in d.items() if kk.split("_")[0] == pre)
        self.max_id = max(g(v, "ItemID") for v in self.rows.values())

    def other_languages(self):
        """-> {table path: (uasset, uexp, source)} for every non-English GameText table,
        taking whichever version currently wins (another mod may ship one)."""
        out = {}
        for e in self.p.entries:
            if "/GameText/Database/GameText" in e and e.endswith(".uasset") \
                    and not e.endswith("GameTextEN.uasset"):
                base = e[:-len(".uasset")]
                out[base] = (self.p.read(base + ".uasset"), self.p.read(base + ".uexp"),
                             "(base game)")
        import glob
        for f in sorted(glob.glob(os.path.join(paths.mods_dir(), "*.pak"))):
            if os.path.basename(f).startswith(OUT_PREFIX):
                continue
            q = pak.Pak(f)
            for base in list(out):
                if base + ".uasset" in q.entries and base + ".uexp" in q.entries:
                    out[base] = (q.read(base + ".uasset"), q.read(base + ".uexp"),
                                 os.path.basename(f))
        return out

    def text_rows_for(self, ua):
        """The new text rows, built against another GameText table's name list. English
        strings: better than the blank names a missing row would show."""
        names, _ = uasset.names_of(ua)
        anchor = self._text_anchor()
        for need in (anchor, "Text", "TextProperty", "None"):
            if need not in names:
                raise RuntimeError(f"text table lacks name {need}")
        return [dt.build_text_row(names, names.index(anchor), num, key, s)
                for num, key, s in self.text_specs]

    def _base_text(self):
        """Append onto whichever GameTextEN currently wins, not the vanilla one.

        BetterDescriptions and SideStoriesHelper both ship their own GameTextEN. Paks mount
        in filename order and the last one wins, so replacing it with a vanilla-based copy
        would silently undo those mods. Build on top of the current winner instead (and name
        our pak so it sorts last).
        """
        import glob
        best = None
        for f in sorted(glob.glob(os.path.join(paths.mods_dir(), "*.pak"))):
            if os.path.basename(f).startswith(OUT_PREFIX):
                continue                      # don't stack on our own previous build
            q = pak.Pak(f)
            ua = [n for n in q.entries if n.endswith("GameTextEN.uasset")]
            ue = [n for n in q.entries if n.endswith("GameTextEN.uexp")]
            if ua and ue:
                best = (q.read(ua[0]), q.read(ue[0]), os.path.basename(f))
        if best:
            return best
        return self.p.read(TEXT + ".uasset"), self.p.read(TEXT + ".uexp"), "(base game)"

    # ---- name plumbing -------------------------------------------------
    def _text_anchor(self):
        """A name present in BOTH tables, reused with fresh FName numbers."""
        for n in ("TX_NA_ITM_078", "TX_CO_ITM_078"):
            if n in self.item_names and n in self.text_names:
                return n
        raise RuntimeError("no shared anchor name")

    def add_text(self, s):
        """Append a GameTextEN row holding `s`; returns its FName number."""
        anchor = self._text_anchor()
        num = FNUM_BASE + self.counter
        self.counter += 1
        key = ("%032X" % (0xC1A0DE0000000000 + num))
        row = dt.build_text_row(self.text_names, self.text_names.index(anchor), num, key, s)
        self.new_texts.append(row)
        self.text_specs.append((num, key, s))
        return num

    # ---- gear ----------------------------------------------------------
    def forge(self, template, name, desc, stats, ailment=None, price=None, item_id=None,
              immune=()):
        """Clone `template` (an existing row key) into a new item.

        stats   : {"ATK": 1200, ...} absolute values for EquipmentRevision
        ailment : (ailment_name, value) e.g. ("THUNDER_ABILITY_UP", 120)
        """
        span = self.item_spans[template]
        _nm, idx, _num, s, e = span
        buf = bytearray(self.item_ue[s:e])
        names = self.item_names
        lo, hi = 0, len(buf)

        name_num = self.add_text(name)
        desc_num = self.add_text(desc)
        if item_id is not None:
            new_id = item_id
        elif self.registry is not None:
            new_id = self.registry.id_for(name)
        else:
            new_id = NEW_ID_BASE + len(self.new_items)

        # row name: shared anchor + an FName number derived from the (stable) ID, so shops
        # and drops can name it too
        row_num = FNUM_BASE + 500 + (new_id - NEW_ID_BASE)
        dt.set_fname(buf, 0, names.index(ROW_ANCHOR), row_num)

        def one(field, kind="IntProperty", exact=False):
            offs = dt.field_offsets_in(buf, names, lo, hi, field, kind, exact)
            if len(offs) != 1:
                raise RuntimeError(f"{template}/{field}: {len(offs)} hits")
            return offs[0]

        dt.set_int(buf, one("ItemID"), new_id)
        anchor_i = names.index(self._text_anchor())
        dt.set_fname(buf, one("ItemNameID", "NameProperty"), anchor_i, name_num)
        dt.set_fname(buf, one("DetailTextID", "NameProperty"), anchor_i, desc_num)
        if price is not None:
            dt.set_int(buf, one("BuyPrice"), price)
            dt.set_int(buf, one("SellPrice"), max(1, price // 10))

        # Start from zero: templates carry their own stats (the sword template has +150
        # Critical) which would otherwise leak onto new gear unlisted.
        for stat, field in STAT_FIELD.items():
            dt.set_int(buf, one(field, exact=True), int(stats.get(stat, 0)))

        # Write ALL four Ailment slots. Templates carry their own effects (the axe template
        # has Thunder+Ice boosts, the shield HP+SP regen, most weapons a 5-turn/10% status
        # proc); patching only slot 0 used to leak those onto new gear invisibly.
        if ailment is None:
            ails = []
        elif isinstance(ailment, tuple):
            ails = [ailment]
        else:
            ails = list(ailment)
        an = dt.field_offsets_in(buf, names, lo, hi, "AilmentName", "NameProperty")
        iv = dt.field_offsets_in(buf, names, lo, hi, "InvocationValue")
        it = dt.field_offsets_in(buf, names, lo, hi, "InvocationTurn")
        dr = dt.field_offsets_in(buf, names, lo, hi, "DiseaseRate")
        if not (len(an) == len(iv) == len(it) == len(dr) == AILMENT_SLOTS):
            raise RuntimeError(f"{template}: expected {AILMENT_SLOTS} ailment slots, got "
                               f"{len(an)}/{len(iv)}/{len(it)}/{len(dr)}")
        if len(ails) > AILMENT_SLOTS:
            raise RuntimeError(f"{name}: {len(ails)} effects, only {AILMENT_SLOTS} slots")
        for slot in range(AILMENT_SLOTS):
            if slot < len(ails):
                entry = ails[slot]
                aname, aval = entry[0], entry[1]
                if aname not in names:
                    # effects no shipped item uses (the relic buffs) aren't in ItemDB's
                    # name table yet; append them (existing indices are unchanged)
                    self.item_ua = dt.add_names(self.item_ua, [aname])
                    self.item_names, _ = uasset.names_of(self.item_ua)
                    names = self.item_names
                # on-hit procs carry their own duration and % chance; passives use the
                # timing shipped gear uses
                turn, rate = entry[2:4] if len(entry) == 4 else AILMENT_TIMING.get(aname, (0, 0))
            else:
                # empty slots: consumables mark them "0", equipment "None"; keep whichever
                # the template uses and only clear a slot that holds a real effect
                cur = names[struct.unpack_from("<i", buf, an[slot])[0]]
                if cur in ("None", "0"):
                    continue
                marks = [names[struct.unpack_from("<i", buf, o)[0]] for o in an]
                aname = "0" if "0" in marks else "None"
                aval, turn, rate = 0, 0, 0
            dt.set_fname(buf, an[slot], names.index(aname), 0)
            dt.set_int(buf, iv[slot], int(aval))
            dt.set_int(buf, it[slot], turn)
            dt.set_int(buf, dr[slot], rate)

        # status immunities: DiseaseResist is a bool array (one byte each), 1 = immune,
        # exactly as the shipped "Prevents X" talismans store it
        dr_off = self._array_data(buf, "DiseaseResist")
        count = struct.unpack_from("<i", buf, dr_off)[0]
        for i in range(count):
            buf[dr_off + 4 + i] = 0
        for st in immune:
            buf[dr_off + 4 + DISEASE_INDEX[st]] = 1

        self.new_items.append(bytes(buf))
        return dict(id=new_id, row_num=row_num, name=name, template=template, immune=immune,
                    stats=stats, ailment=ailment, price=price)

    def _array_data(self, buf, field):
        """Offset of the element count of a bool ArrayProperty inside a row."""
        names = self.item_names
        cand = [n for n in names if n.split("_")[0] == field]
        if len(cand) != 1:
            raise RuntimeError(f"{field}: {len(cand)} name entries")
        pos = bytes(buf).find(struct.pack("<ii", names.index(cand[0]), 0))
        if pos < 0 or names[struct.unpack_from("<i", buf, pos + 8)[0]] != "ArrayProperty":
            raise RuntimeError(f"{field} array not found")
        if names[struct.unpack_from("<i", buf, pos + 24)[0]] != "BoolProperty":
            raise RuntimeError(f"{field} is not a bool array")
        # name8 type8 size4 index4 innertype8 hasguid1 -> count
        return pos + 33

    # ---- output --------------------------------------------------------
    def build(self, out_path, verbose=True):
        iua, iue = dt.append_rows(self.item_ua, self.item_ue, self.new_items)
        tua, tue = dt.append_rows(self.text_ua, self.text_ue, self.new_texts)
        dt.verify(iua, iue, expect_count=len(self.rows) + len(self.new_items))
        dt.verify(tua, tue)
        # the appended rows must read back exactly as intended
        back = uasset.read_datatable(iua, iue)
        assert len(back) == len(self.rows) + len(self.new_items), "row count mismatch after append"
        tback = uasset.read_datatable(tua, tue)
        files = {ITEMS + ".uasset": iua, ITEMS + ".uexp": iue,
                 TEXT + ".uasset": tua, TEXT + ".uexp": tue}
        size = pakwrite.write_pak(out_path, files)
        q = pak.Pak(out_path)
        for n, d in files.items():
            assert q.read(n) == d, f"pak round-trip failed: {n}"
        if verbose:
            print(f"appended {len(self.new_items)} items + {len(self.new_texts)} text rows")
            print(f"wrote {out_path} ({size:,} bytes)")
        return back, tback
