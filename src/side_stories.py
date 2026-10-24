"""Side stories: which of the game's records are real, and a walkthrough for each.

Sub_MissionRecord holds 144 records, but only 101 side stories exist: 32 records have no
title (some still have leftover scripts), 4 titled ones are never started by any event, and
"Kit, the Traveler" is eight records (one per road you might meet him on) of which only one
ever runs. A record is real when it has a title and an event script starts it (command
1300); records whose keys differ only in the last two digits are one story.

The walkthrough is read from the game's own data. A story's events are SS_<area>_<number><xx>:
xx = 00 starts it, 01-09 are people to ask around, letters are the ways to solve it (A0, B0
.. finish it; A1.. are steps on the way or afterwards). Each event is fired by an NPC or
object placed on a map (PlacementInfoData, listed per map in PlacementInfoList) when a
condition holds (EventType: 1 talk, 2 hand over an item or info, 3 guide/allure someone, 8 /
11 challenge / provoke, 14 know something, 16 know it OR hold an item, 17 bring someone OR
know something, 0 examine), or by a map itself (EventList MapID). Items come from NPCs'
Purchase/Steal lists (NPCPurchaseData -> ShopList -> PurchaseItemTable), information from
their Inquire/Scrutinize lists (NPCHearData -> HearInfoSetList -> NPCHearInfoData). Places
and regions have names in GameTextEN.
"""
import collections
import json

import pak
import paths
import uasset

C = "Octopath_Traveler/Content/"
SUB_MISSIONS = C + "Mission/Database/Sub_MissionRecord"
START, FINISH = 1300, 1310           # event script commands: begin / complete a side story
MAX_LINE = 110                       # journal line length before wrapping
TALK, GIVE, LEAD, CHALLENGE, PROVOKE = 1, 2, 3, 8, 11
KNOW, KNOW_OR_HOLD, LEAD_OR_KNOW, EXAMINE = 14, 16, 17, 0
LEAD_ALT = (10, 12)                  # guide / allure this person (no parameters)
LEAF = "⑳"                       # the leaf symbol, as Side Stories Helper writes rewards
DASH = "–"
# At Journey's End's last part is the fight with Galdera, and it finishes at Hornburg after
# it - so it can't count toward the completion (and Wayfarer's Laurel) you need for that fight
AFTER_LAST_BOSS = "SMR_SS_EX4_0137"
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
    _CACHE.update(rd=rd, smr=smr, pdata=pdata, events=events, wmap=wmap, text=text)

    def txt(k):
        return (text.get(k) or {}).get("Text")

    # event -> {(map key, placement label or None)}
    lab2map = collections.defaultdict(set)
    _CACHE["lab2map"] = lab2map
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
    _CACHE["lvl2loc"] = lvl2loc
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
    _CACHE.update(stories=stories, begins=begins, ends=ends)
    return _CACHE


def stories():
    return _data()["stories"]


def slots(countable=False):
    """-> ({area index: [(position in the save's MissionState list, story group)]}, number
    of real side stories). A group counts as done when any of its records is. countable:
    leave out the one that ends after the last boss (AFTER_LAST_BOSS)."""
    real = [s for s in stories() if s["real"]
            and not (countable and s["group"] == AFTER_LAST_BOSS)]
    out = collections.defaultdict(list)
    for s in real:
        out[s["area"]].append((s["pos"], s["group"]))
    return dict(out), len({s["group"] for s in real})




class _Guide:
    """Names, places and sources for writing walkthroughs (built once, from _data())."""

    def __init__(self):
        d = _data()
        rd, self.pdata, self.events = d["rd"], d["pdata"], d["events"]
        self.wmap, self.text = d["wmap"], d["text"]
        self.lab2map, self.lvl2loc = d["lab2map"], d["lvl2loc"]
        import make_gear
        self.items = rd(make_gear.ITEMS)
        buy = rd(C + "Character/Database/NPCPurchaseData")
        hear = rd(C + "Character/Database/NPCHearData")
        hset = rd(C + "Character/Database/HearInfoSetList")
        hinfo = rd(C + "Character/Database/NPCHearInfoData")
        shops = rd(C + "Shop/Database/ShopList")
        pitems = rd(C + "Shop/Database/PurchaseItemTable")
        self.sells = collections.defaultdict(list)     # item -> [placement label]
        self.tells = collections.defaultdict(list)     # info -> [placement label]
        self.by_uniq = collections.defaultdict(list)   # NPC_UnqIndex -> [placement label]
        self.trig = collections.defaultdict(list)      # event -> [(label, type, params)]
        for lab, v in self.pdata.items():
            if v.get("NPC_UnqIndex") is not None:
                self.by_uniq[v["NPC_UnqIndex"]].append(lab)
            b = buy.get(v.get("FCmd_Purchase_ID"))
            if b and _g(b, "CommandEnable"):
                for e in (list(shops.get(_g(b, "ShopID"), {}).values()) or [[]])[0] or ():
                    if e in pitems:
                        self.sells[pitems[e]["ItemLabel"]].append(lab)
            h = hear.get(v.get("FCmd_Search_ID"))
            if h and _g(h, "CommandEnable"):
                for e in (list(hset.get(_g(h, "GetInfoSetID"), {}).values()) or [[]])[0] or ():
                    if e in hinfo:
                        self.tells[_g(hinfo[e], "ItemID")].append(lab)
            for slot in "ABCDE":
                ev = v.get(f"EventLabel_{slot}")
                if ev and ev.startswith("SS_"):
                    prm = [v[f"EventParam_{slot}_{i}"] for i in range(1, 11)
                           if v.get(f"EventParam_{slot}_{i}") not in (None, "None")]
                    self.trig[ev].append((lab, v[f"EventType_{slot}"], prm))

    def txt(self, k):
        return (self.text.get(k) or {}).get("Text")

    def _row(self, mk):
        base = mk[5:] if mk.startswith("eMAP_") else mk
        while base:
            if "eMAP_" + base in self.wmap:
                return base
            base = base.rsplit("_", 1)[0] if "_" in base else ""
        return None

    def place(self, mk):
        """'Bolderfall (Ravus Manor Gate), Cliftlands' for a map key or world-map row."""
        base = self._row(mk)
        top = (self.txt(_g(self.wmap["eMAP_" + base], "MapName"))
               or self.txt("eMAP_NAME_" + base)) if base else None
        sub = None if mk.startswith("eMAP_") else self.txt(mk)
        name = f"{top} ({sub})" if sub and top and top not in sub else (sub or top or mk)
        region = self.txt(_g(self.wmap["eMAP_" + base], "RegionName")) if base else None
        return name + (f", {region}" if region else "")

    def where(self, lab):
        mks = sorted(self.lab2map.get(lab, ()))
        if not mks:
            return None
        inside = self.pdata[lab].get("HouseInFlag") == 1
        return self.place(mks[0]) + (" (indoors)" if inside else "")

    def who(self, lab):
        return self.txt(self.pdata[lab].get("TextLabel")) or "the marked spot"

    def at(self, lab):
        w = self.where(lab)
        return f"{self.who(lab)} {DASH} {w}" if w else self.who(lab)

    def item(self, i):
        r = self.items.get(i)
        return (self.txt(_g(r, "ItemNameID")) if r else None) or i

    def source(self, i, story_code):
        """'Inquire/Scrutinize Muttering Codger - Flamesgrace, Frostlands', or None for
        common items sold all over."""
        info = i.startswith("INFO_")
        labs = (self.tells if info else self.sells).get(i, [])
        mine = [x for x in labs if story_code in x]
        if not mine and len(labs) > 3:
            return None
        pick = (mine or labs or [None])[0]
        if not pick:
            return None
        return ("Inquire/Scrutinize " if info else "Purchase/Steal ") + self.at(pick)

    def person(self, uniq, story_code):
        labs = self.by_uniq.get(int(uniq), []) if str(uniq).lstrip("-").isdigit() else []
        mine = [x for x in labs if story_code in x]
        return (mine or labs or [None])[0]


def walkthrough(story, g=None):
    """-> journal lines for one side story: Start, Ask around, Get / Learn (who provides
    each item or piece of information), the steps, the Finish options and the Reward."""
    g = g or _Guide()
    d = _data()
    code = story["key"][7:-2]                              # e.g. SN1_0002
    pre = "SS_" + code
    begin = d["begins"].get(story["key"], set())
    end = d["ends"].get(story["key"], set())
    # events are named after the story, except where the game misnumbers them
    # (A Royal Secret, SMR_SS_MO2_004900, runs SS_MO2_0094..): follow its start/finish events
    pres = {pre} | {e[:len(pre)] for e in begin | end}
    evs = sorted(e for e in set(g.events) | set(g.trig) if e[:len(pre)] in pres)
    if sum(1 for s in d["stories"] if s["group"] == story["group"]) > 1:
        # one of several versions (Kit's roads): its events end in the version's digit
        evs = [e for e in evs if e[len(pre) + 1:len(pre) + 2] == story["key"][-1]]
    start, ask, need, steps, finish = [], [], [], [], []
    starters = set()
    noted = set()

    def wants(i):
        """Name an item / info, noting once where it comes from."""
        nm = g.item(i)
        if i not in noted:
            noted.add(i)
            src = g.source(i, code)
            if src:
                need.append(("Learn " if i.startswith("INFO_") else "Get ") + f"{nm}: {src}")
        return nm

    def lead(uniq, to):
        f = g.person(uniq, code)
        return f"Guide/Allure {g.at(f) if f else 'them'} to {to}"

    for e in evs:
        suf = e[len(pre):]
        acts, talks = [], []          # acts: (text, placement label)
        by_lab = collections.OrderedDict()
        for lab, t, prm in g.trig.get(e, ()):
            by_lab.setdefault(lab, {})[t] = prm
        for lab, ts in by_lab.items():
            box = lab.startswith(("BOX", "TrsrBx"))
            here = (g.where(lab) or "the area") if box else g.at(lab)
            if CHALLENGE in ts or PROVOKE in ts:
                acts.append((f"Challenge/Provoke {here}", lab))
            for t, prm in ts.items():
                if t == GIVE and prm:
                    nm = wants(prm[0])
                    if prm[0].startswith("INFO_"):
                        acts.append((f"Tell {here} about {nm}", lab))
                    else:
                        acts.append((f"Give {nm} to {here}", lab))
                elif t == LEAD and prm:
                    acts.append((lead(prm[0], here), lab))
                elif t == KNOW and prm:
                    nm = wants(prm[0])
                    acts.append(((f"Examine the spot in {here}" if box else f"Talk to {here}")
                                 + f", knowing {nm}", lab))
                elif t == KNOW_OR_HOLD and len(prm) >= 2:
                    a, b = wants(prm[0]), wants(prm[1])
                    acts.append((f"Talk to {here}, knowing {a} or holding {b}", lab, "either"))
                elif t == LEAD_OR_KNOW and len(prm) >= 2:
                    nm = wants(prm[1])
                    acts.append((f"{lead(prm[0], here)}, or tell them about {nm}", lab, "either"))
                elif t in LEAD_ALT:
                    acts.append((f"Guide/Allure {here}", lab))
                elif t == EXAMINE:
                    acts.append(((f"Examine the spot in {here}" if box else f"Talk to {here}"),
                                 lab))
                elif t == TALK:
                    talks.append(lab)
        if not by_lab and e in g.events:
            m = _g(g.events[e], "MapID")
            if m in g.lvl2loc:
                acts.append((f"Go to {g.place(g.lvl2loc[m])}", None))
        if e in begin:
            start += [a[0] for a in acts] or [g.at(x) for x in talks]
            starters |= set(talks) | {a[1] for a in acts}
        elif e in end:
            finish += acts or [(f"Talk to {g.at(x)}", x) for x in talks]
        elif suf[:1].isdigit():
            steps += [a[0] for a in acts]
            ask += talks
        else:
            steps += [a[0] for a in acts]    # talk-only letter events: reactions afterwards
    # an either/or finish makes the single-requirement finishes at the same person redundant
    either = {f[1] for f in finish if len(f) > 2}
    finish = [f[0] for f in finish if len(f) > 2 or f[1] not in either]
    lines = []
    if start:
        lines.append("Start: " + start[0].replace("Talk to ", ""))
    elif story["title"] and story["title"].endswith(")"):
        lines.append("Start: begins as soon as the previous part ends")
    starter_names = {g.who(x) for x in starters if x}
    ask = [x for x in ask if x not in starters and g.who(x) not in starter_names]
    if ask:
        groups = collections.OrderedDict()
        for lab in ask:
            names = groups.setdefault(g.where(lab) or "", [])
            if g.who(lab) not in names:
                names.append(g.who(lab))
        lines.append("Ask around: " + "; ".join(
            ", ".join(n) + (f" {DASH} {w}" if w else "") for w, n in groups.items()))
    lines += need
    for st in dict.fromkeys(steps):
        if st.startswith("Go to ") and lines and st[6:] in lines[-1]:
            continue                       # the step before already took you there
        lines.append(st)
    for n, f in enumerate(dict.fromkeys(finish)):
        lines.append(("Finish: " if n == 0 else "  or: ") + f)
    rec = d["smr"][story["key"]]
    reward = [f"{LEAF}{_g(rec, 'RewardMoney'):,}"] if _g(rec, "RewardMoney") else []
    prm = list(_g(rec, "RewardParam"))
    for i in range(0, len(prm) - 1, 2):
        if prm[i] not in (None, "None"):
            n = int(prm[i + 1]) if str(prm[i + 1]).isdigit() else 1
            reward.append(g.item(prm[i]) + (f" x{n}" if n > 1 else ""))
    if reward:
        lines.append("Reward: " + ", ".join(reward))
    return _wrap(lines)


def _wrap(lines):
    out = []
    for ln in lines:
        while len(ln) > MAX_LINE:
            cut = max(ln.rfind(sep, 0, MAX_LINE) for sep in ("; ", ", ", " "))
            if cut <= 10:
                break
            out.append(ln[:cut + 1].rstrip())
            ln = "    " + ln[cut + 1:].lstrip()
        out.append(ln)
    return out


def add_walkthroughs(ua, ue, nl="\\n", log=print):
    """Replace every real side story's journal entry in a GameTextEN table with its full
    walkthrough. -> (ua, ue). Stories that share one entry (Kit, the Traveler: eight roads)
    get one walkthrough that lists the places he can be met."""
    import datatable as dt
    import hashlib
    rows = uasset.read_datatable(ua, ue)
    names, _ = uasset.names_of(ua)
    spans = {s[0]: s for s in dt.row_spans(ua, ue)}
    g = _Guide()
    by_detail = collections.OrderedDict()
    for s in stories():
        if s["real"] and s["detail"] in rows:
            by_detail.setdefault(s["detail"], []).append(s)
    new = {}
    for detail, recs in by_detail.items():
        lines = walkthrough(recs[0], g)
        if len(recs) > 1:
            met = []
            for r in recs:
                first = walkthrough(r, g)[:1]
                if first and f" {DASH} " in first[0]:
                    met.append(first[0].split(f" {DASH} ", 1)[1])
            who = lines[0][7:].split(f" {DASH} ")[0] if lines else "They"
            spot = met[0] if met else None
            body = [ln.replace(f" {DASH} {spot}", "") if spot else ln for ln in lines[1:]
                    if not (spot and ln.startswith("Examine the spot in " + spot))]
            lines = _wrap([f"Start: {who}, met in one of: " + "; ".join(dict.fromkeys(met))]
                          + [ln for ln in body if not ln.startswith("  or: ")])
        if not lines:
            continue
        _nm, idx, num, _a, _b = spans[detail]
        key = hashlib.md5(("walk:" + detail).encode()).hexdigest().upper()
        new[detail] = dt.build_text_row(names, idx, num, key, nl.join(lines))
    if new:
        ua, ue = dt.replace_rows(ua, ue, new)
    log(f"side-story journal: step-by-step walkthroughs written for {len(new)} side stories")
    return ua, ue
