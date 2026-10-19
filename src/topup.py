"""Catch-up by EXP top-up (overhaul.ini: catch_up = save).

The cheaper-levels table (catch_up = table) can't erase a lagging traveler's shortfall: the
save stores each traveler's running EXP total and every level asks for the same total, so
the first full-price level charges everything the cheap levels skipped. This instead raises
the EXP total of every traveler more than TOPUP_BEHIND levels below the highest active
party member to the normal total of that level (and anyone whose total is below their own
level's normal total - left over from the cheap table - to that). The game then hands out the
levels itself after their next battle, with normal stat growth, and they level normally
from there.

It writes the save, so: only before the game starts (the launcher), only the Exp numbers
change (the rest is rewritten byte-identically), and the save is backed up first. Off in
the vanilla opening, like the rest of the overhaul.
"""
import datetime
import os
import shutil

import gvas
import pak
import paths
import uasset

TOPUP_BEHIND = 5


def _g(row, pre):
    return next(v for k, v in row.items() if k.split("_")[0] == pre)


def normal_totals():
    """{level: TotalExp} as the game ships it (or as another mod - Larger Monster Roster -
    ships it), never the overhaul's own cheaper table."""
    import build_difficulty_mod as B
    ua, ue, _src = paths.installed_asset(B.GROW, pak.Pak(paths.base_pak()))
    return {int(k): _g(v, "TotalExp") for k, v in uasset.read_datatable(ua, ue).items()}


def plan(save_path, behind=TOPUP_BEHIND, totals=None):
    """-> (target level, [(name, level, exp, new exp)]) without writing anything."""
    import respec_core as rc
    totals = totals or normal_totals()
    s = gvas.SaveFile.load(save_path)
    slot = {x.name.split("_")[0]: x for x in s.get("slotData").value}
    ids = [getattr(x, "value", x) for x in slot["MainMemberCharacterID"].value]
    members = []
    for m in s.get("PlayerMember").value:
        f = {x.name.split("_")[0]: x.value for x in m}
        if f.get("Level", 0) > 0:
            members.append((f["CharacterID"], f["Level"], f["Exp"]))
    top = max((lv for c, lv, _e in members if c in ids), default=0)
    target = max(1, top - behind)
    out = []
    for c, lv, exp in members:
        want = totals.get(max(lv, target), exp)
        if exp < want:
            out.append((rc.CHAR_NAMES.get(c, str(c)), lv, exp, want))
    return target, out


def apply(save_path, behind=TOPUP_BEHIND, log=print):
    """Top up the save in place (backed up first). -> list of changes made."""
    target, changes = plan(save_path, behind)
    if not changes:
        log(f"catch-up: nobody is more than {behind} levels behind")
        return []
    import respec_core as rc
    data = open(save_path, "rb").read()
    s = gvas.SaveFile(data)
    if s.to_bytes() != data:
        raise RuntimeError("save would not be rewritten byte-identically; left untouched")
    want = {name: new for name, _lv, _e, new in changes}
    for m in s.get("PlayerMember").value:
        f = {x.name.split("_")[0]: x for x in m}
        name = rc.CHAR_NAMES.get(f["CharacterID"].value)
        if name in want:
            f["Exp"].value = int(want[name])
    out = s.to_bytes()
    gvas.SaveFile(out)                                   # must re-parse
    bdir = os.path.join(paths.user_dir(), "backups", "saves")
    os.makedirs(bdir, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    base = os.path.basename(save_path)
    shutil.copy2(save_path, os.path.join(bdir, f"{base[:-4]}_{stamp}.sav"))
    tmp = save_path + ".tmp"
    with open(tmp, "wb") as fh:
        fh.write(out)
    os.replace(tmp, save_path)
    for name, lv, exp, new in changes:
        log(f"catch-up: {name} (level {lv}) EXP {exp:,} -> {new:,} - reaches level "
            f"{target}+ after the next battle")
    log(f"catch-up: save backed up to {bdir}")
    return changes
