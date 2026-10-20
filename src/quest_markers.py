"""Side stories you haven't started, marked in the game (rebuilt from the save at each launch).

The journal only lists stories that have begun, so the givers of the rest are marked where
you meet them:

- the person who starts the story is renamed "<name> ⑳" (the leaf, as the journal writes
  rewards) - only their placement that starts it, so the same person later on keeps the
  plain name;
- the world map names a location "<name> ⑳" (or "⑳3" for three) when side stories you
  haven't started begin there.

Both come off at the next launch after the story begins. Shown from a point in the story
(MODE / FROM, set from overhaul.ini; the save picker has a checkbox). Givers who only appear after a
later chapter are counted too. A new name is a new text row (make_gear's anchor name with
a fresh FName number) and an in-place FName swap of PlacementInfoData.TextLabel /
WorldMapTable.MapName.
"""
import collections
import hashlib
import os
import struct

import datatable as dt
import gvas
import paths
import side_stories as S
import uasset

MODE = "auto"        # overhaul.ini side_story_markers: auto / on / off
FROM = 24            # auto: from this many chapters done (24 = every chapter 3)
PLACEMENTS = S.C + "Character/Database/PlacementInfoData"
WORLD_MAP = S.C + "Level/Database/WorldMapTable"


def states(save):
    """-> {story group: 0 not started / 1 in progress / 2 done} for every real side story."""
    slots, _total = S.slots()
    grps = gvas.SaveFile.load(save).get("SubMissionData").value
    out = {grp: 0 for area in slots.values() for _pos, grp in area}
    for a, grp in enumerate(grps):
        st = {q.name.split("_")[0]: q.value for q in grp}["MissionState"]
        for pos, story in slots.get(a, ()):
            if pos < len(st):
                out[story] = max(out[story], st[pos])
    return out


def wanted(save):
    """Are markers shown for this save? (MODE, and for auto the chapters done.)"""
    if MODE == "off" or not save or not os.path.isfile(save):
        return False
    if MODE == "on":
        return True
    try:
        import build_difficulty_mod as B
        return B.chapters_done(gvas.SaveFile.load(save)) >= FROM
    except Exception:                                    # noqa: BLE001 (odd save: no markers)
        return False


def open_key(save):
    """A short fingerprint of which side stories have begun (rebuild when it changes);
    empty when no markers are shown."""
    if not wanted(save):
        return ""
    try:
        st = states(save)
    except Exception:                                    # noqa: BLE001 (new game / odd save)
        return ""
    return hashlib.md5(",".join(sorted(k for k, v in st.items() if v)).encode()).hexdigest()[:12]


def starts(g=None):
    """-> {story group: [(placement label or None, world-map row key or None)]}: where each
    side story begins. Sequels that begin when the previous part ends have none."""
    g = g or S._Guide()
    d = S._data()
    out = collections.defaultdict(list)
    for story in S.stories():
        if not story["real"]:
            continue
        for e in sorted(d["begins"].get(story["key"], ())):
            hits = [lab for lab, _t, _p in g.trig.get(e, ())]
            for lab in dict.fromkeys(hits):
                mks = sorted(g.lab2map.get(lab, ()))
                base = g._row(mks[0]) if mks else None
                out[story["group"]].append((lab, "eMAP_" + base if base else None))
            if not hits and e in g.events:
                m = S._g(g.events[e], "MapID")
                if m in g.lvl2loc:
                    out[story["group"]].append((None, g.lvl2loc[m]))
    return dict(out)


def _swap(ua, ue, field, refs):
    """Point `field` (a NameProperty) of each row at refs[row] = (name, number)."""
    ua = dt.add_names(ua, sorted({n for n, _num in refs.values()}))
    names, _ = uasset.names_of(ua)
    ue = bytearray(ue)
    spans = {s[0]: s for s in dt.row_spans(ua, bytes(ue))}
    done = 0
    for row, (nm, num) in refs.items():
        if row not in spans:
            continue
        _r, _i, _n, lo, hi = spans[row]
        offs = dt.field_offsets_in(bytes(ue), names, lo, hi, field, "NameProperty")
        if len(offs) != 1:
            raise RuntimeError(f"{row}: {len(offs)} {field} fields")
        struct.pack_into("<ii", ue, offs[0], names.index(nm), num)
        done += 1
    return ua, bytes(ue), done


class Markers:
    """Plan the new names (text rows go through `forge`), then patch the two tables."""

    def __init__(self, forge, save, log=print):
        self.forge, self.log = forge, log
        self.people, self.places = {}, {}
        st = states(save)
        todo = {grp for grp, v in st.items() if v == 0}
        g = S._Guide()
        anchor = forge._text_anchor()
        count = collections.Counter()
        for grp, spots in starts(g).items():
            if grp not in todo:
                continue
            for lab, loc in spots:
                if lab and not lab.startswith(("BOX", "TrsrBx")) and lab not in self.people:
                    who = g.txt(g.pdata[lab].get("TextLabel"))
                    if who:
                        self.people[lab] = (anchor, forge.add_text(f"{who} {S.LEAF}"))
            for loc in dict.fromkeys(loc for _lab, loc in spots if loc):
                count[loc] += 1
        for loc, n in count.items():
            name = g.txt(S._g(g.wmap[loc], "MapName")) if loc in g.wmap else None
            if name:
                tag = S.LEAF + (str(n) if n > 1 else "")
                self.places[loc] = (anchor, forge.add_text(f"{name} {tag}"))
        self.stories = len(todo)

    def apply(self, files, base):
        """Patch PlacementInfoData and WorldMapTable into `files` (on top of what's there)."""
        out = {}
        for path, field, refs in ((PLACEMENTS, "TextLabel", self.people),
                                  (WORLD_MAP, "MapName", self.places)):
            if not refs:
                continue
            if path + ".uasset" in files:
                ua, ue = files[path + ".uasset"], files[path + ".uexp"]
            else:
                ua, ue, _src = paths.installed_asset(path, base)
            ua, ue, n = _swap(ua, ue, field, refs)
            dt.verify(ua, ue)
            files[path + ".uasset"], files[path + ".uexp"] = ua, ue
            out[field] = n
        self.log(f"side stories not started ({self.stories}): {out.get('TextLabel', 0)} "
                 f"quest-givers and {out.get('MapName', 0)} world-map places marked with the leaf")
