"""Side stories: which of the game's records are real, and where each one is finished.

Sub_MissionRecord holds 144 records, but only 101 side stories exist: 32 records have no
title (some still have leftover scripts), 4 titled ones are never started by any event, and
"Kit, the Traveler" is eight records (one per road you might meet him on) of which only one
ever runs. A record is real when it has a title and an event script starts it (command
1300); records whose keys differ only in the last two digits are one story.

Where a story is finished comes from the game's own data: the event scripts that complete
it (command 1310), the NPC placements that trigger those events (PlacementInfoData, listed
per map in PlacementInfoList) or, for events fired by a map, EventList's MapID resolved
through WorldMapTable. Map keys and world-map rows have display names in GameTextEN.
"""
import collections
import json

import pak
import paths
import uasset

C = "Octopath_Traveler/Content/"
SUB_MISSIONS = C + "Mission/Database/Sub_MissionRecord"
START, FINISH = 1300, 1310           # event script commands: begin / complete a side story
MAX_PLACES = 2                       # finishing spots named per story
MAX_LINE = 120                       # journal line length, as for item descriptions
_CACHE = {}


def _g(row, prefix):
    return next(v for k, v in row.items() if k.split("_")[0] == prefix)


def _data():
    if _CACHE:
        return _CACHE
    p = pak.Pak(paths.base_pak())

    def rd(b):
        return uasset.read_datatable(p.read(b + ".uasset"), p.read(b + ".uexp"))
    smr = rd(SUB_MISSIONS)
    pdata = rd(C + "Character/Database/PlacementInfoData")
    plist = rd(C + "Character/Database/PlacementInfoList")
    events = rd(C + "Event/Database/EventList")
    wmap = rd(C + "Level/Database/WorldMapTable")
    text = rd(C + "GameText/Database/GameTextEN")

    def txt(k):
        return (text.get(k) or {}).get("Text")

    # event -> {(map key, placement label or None)}
    lab2map = collections.defaultdict(set)
    for mk, v in plist.items():
        for lab in list(v.values())[0] or ():
            lab2map[lab].add(mk)
    where = collections.defaultdict(set)
    for lab, v in pdata.items():
        for slot in "ABCDE":
            ev = v.get(f"EventLabel_{slot}")
            if ev and ev.startswith("SS_"):
                for mk in lab2map.get(lab, ()):
                    where[ev].add((mk, lab))
    lvl2loc = {}
    for k, v in wmap.items():
        for lv in list(_g(v, "RefLevelName")) + [_g(v, "MoveLevelName")]:
            if lv and lv != "None":
                lvl2loc.setdefault(lv, k)
    for k, v in events.items():
        if k.startswith("SS_") and _g(v, "MapID") in lvl2loc:
            where[k].add((lvl2loc[_g(v, "MapID")], None))

    # which event scripts start / finish which record
    begins, ends = collections.defaultdict(set), collections.defaultdict(set)
    for e in p.entries:
        if "/Event/json/SS_" not in e:
            continue
        try:
            script = json.loads(p.read(e).decode("utf-8", "replace"))
        except ValueError:
            continue
        for step in script.values():
            opt = step.get("opt") or [""]
            if step.get("cmd") in (START, FINISH) and str(opt[0]).startswith("SMR_"):
                (begins if step["cmd"] == START else ends)[opt[0]].add(e.rsplit("/", 1)[-1])

    def place(mk):
        if mk.startswith("eMAP_"):                       # a WorldMapTable row
            return txt("eMAP_NAME_" + mk[5:]) or mk
        sub, base = txt(mk), mk                          # a map key such as T_Cliff_L_C
        while base and not txt("eMAP_NAME_" + base):
            base = base.rsplit("_", 1)[0] if "_" in base else ""
        top = txt("eMAP_NAME_" + base) if base else None
        if sub and top and top not in sub:
            return f"{top} ({sub})"
        return sub or top or mk

    stories = []
    by_area = collections.defaultdict(list)
    for k, v in smr.items():
        by_area[_g(v, "AreaIndex")].append((_g(v, "MissionIndex"), k))
    for area, recs in by_area.items():
        for pos, (_mi, k) in enumerate(sorted(recs)):
            v = smr[k]
            spots = []
            for ev in sorted(ends.get(k, ())):
                for mk, lab in sorted(where.get(ev, ()), key=str):
                    who = txt(_g(pdata[lab], "TextLabel")) if lab else None
                    inside = bool(lab) and _g(pdata[lab], "HouseInFlag") == 1
                    spots.append((place(mk), who, inside))
            stories.append(dict(key=k, area=area, pos=pos, group=k[:-2],
                                real=bool(begins.get(k) and txt(_g(v, "TitleTextLabel"))),
                                title=txt(_g(v, "TitleTextLabel")),
                                detail=_g(v, "DetailTextLabel"), finish=spots))
    _CACHE.update(stories=stories)
    return _CACHE


def stories():
    return _data()["stories"]


def slots():
    """-> ({area index: [(position in the save's MissionState list, story group)]}, number
    of real side stories). A group counts as done when any of its records is."""
    out = collections.defaultdict(list)
    for s in stories():
        if s["real"]:
            out[s["area"]].append((s["pos"], s["group"]))
    return dict(out), len({s["group"] for s in stories() if s["real"]})


def where_line(story, current_text=""):
    """'Finish at: Mysterious Knight, South Orewell Pass' for a story's finishing spot(s), or
    None when the data has none or the journal text already names them all."""
    named = [(pl, who, inside) for pl, who, inside in story["finish"] if who]
    spots = named or story["finish"]
    seen, parts = set(), []
    for pl, who, inside in spots:
        if (pl, who) in seen:
            continue
        seen.add((pl, who))
        parts.append(((f"{who}, " if who else "") + pl + (" (indoors)" if inside else ""),
                      pl, who))
    if not parts:
        return None
    whos = {w for _s, _p, w in parts}
    if len(parts) > MAX_PLACES and len(whos) == 1 and None not in whos:
        # one character met in one of several places (Kit, the Traveler: eight roads)
        head, places = f"Finish at: {parts[0][2]}, one of: ", [pl for _s, pl, _w in parts]
        for n in range(len(places), 0, -1):
            line = head + ", ".join(places[:n]) + ("" if n == len(places) else ", ...")
            if len(line) <= MAX_LINE:
                return line
        return None
    parts = parts[:MAX_PLACES]
    low = current_text.lower()
    if all(pl.split(" (")[0].lower() in low and (not who or who.lower() in low)
           for _s, pl, who in parts):
        return None
    for n in range(len(parts), 0, -1):
        line = "Finish at: " + " / ".join(s for s, _p, _w in parts[:n])
        if len(line) <= MAX_LINE:
            return line
    return None


def add_where(ua, ue, nl="\\n", log=print):
    """Append a "Finish at:" line to every real side story's journal entry in a GameTextEN
    table (whichever one wins, so Side Stories Helper's text is kept). -> (ua, ue)."""
    import datatable as dt
    import hashlib
    rows = uasset.read_datatable(ua, ue)
    names, _ = uasset.names_of(ua)
    spans = {s[0]: s for s in dt.row_spans(ua, ue)}
    merged = {}                      # records sharing one journal entry (Kit's eight roads)
    for s in stories():
        if s["real"] and s["detail"] in rows:
            if s["detail"] in merged:
                merged[s["detail"]]["finish"] = merged[s["detail"]]["finish"] + s["finish"]
            else:
                merged[s["detail"]] = dict(s)
    new, skipped = {}, 0
    for s in merged.values():
        cur = (rows[s["detail"]] or {}).get("Text") or ""
        line = where_line(s, cur)
        if not line:
            skipped += 1
            continue
        _nm, idx, num, _a, _b = spans[s["detail"]]
        key = hashlib.md5(("where:" + s["detail"]).encode()).hexdigest().upper()
        new[s["detail"]] = dt.build_text_row(names, idx, num, key,
                                             (cur + nl if cur else "") + line)
    if new:
        ua, ue = dt.replace_rows(ua, ue, new)
    log(f"side-story journal: 'Finish at:' added to {len(new)} entries "
        f"({skipped} already name their place or have no data)")
    return ua, ue
