"""Party skills with fixed numbers grow with the world.

Most skills scale with the user's stats, but some restore a fixed amount: Alfyn's concoctions
(Restore Health 500 .. Concoct Panacea 9,999), Rest's 25-100 SP, hired helpers' First Aid /
Prayer. Against the 20,000+ HP pools of a world at danger 70 they stop mattering, so their
fixed HP / SP amounts are multiplied by heal_mult (x1 up to danger 35, then danger / 35).
Items keep their own values (they climb loot ladders instead, see rewards.py); enemy and
boss skills are left alone.
"""
import re
import struct

import uasset

ABILITIES = "Octopath_Traveler/Content/Ability/Database/AbilityData"
FIXED = ("HP_FIXED_RECOVERY", "HP_FIXED_RECOVERY_SELF", "MP_FIXED_RECOVERY")
PARTY_KEY = re.compile(r"BT_(ABI|MAKA_ABI)_\d+$")     # party and concoct skills, not BOS_/ENE_
HEAL_BASE = 35
HP_CAP, SP_CAP = 99999, 9999


def heal_mult(floor):
    return max(1.0, floor / HEAL_BASE)


def _g(row, pre):
    return next(v for k, v in row.items() if k.split("_")[0] == pre)


def scale(ua, ue, floor, item_names, text, log=print):
    """-> (ua, ue) with every party skill's fixed HP / SP restore scaled for the world.
    item_names: display names of items, whose use-abilities are left alone."""
    mult = heal_mult(floor)
    rows = uasset.read_datatable(ua, ue)
    names, _ = uasset.names_of(ua)
    cand = [n for n in names if n.split("_")[0] == "InvocationValue"]
    if len(cand) != 1:
        raise RuntimeError(f"InvocationValue: {cand}")
    idx = names.index(cand[0])
    import datatable as dt
    pat = struct.pack("<ii", idx, 0)
    spans = {s[0]: (s[3], s[4]) for s in dt.row_spans(ua, ue)}

    def row_offsets(key):
        """InvocationValue offsets inside one row; the Ailment array's come first (later
        ones belong to nested effect structs)."""
        lo, hi = spans[key]
        out, p = [], lo
        while True:
            p = ue.find(pat, p, hi)
            if p < 0:
                return out
            if names[struct.unpack_from("<i", ue, p + 8)[0]] == "IntProperty":
                out.append(p + 25)
            p += 4
    if mult <= 1:
        return ua, ue
    out = bytearray(ue)
    changed = 0
    for k, v in rows.items():
        if not PARTY_KEY.match(k):
            continue
        shown = (text.get(_g(v, "DisplayName")) or {}).get("Text")
        if shown in item_names:
            continue
        offs = row_offsets(k)
        for s, a in enumerate(_g(v, "Ailment")):
            name, val = _g(a, "AilmentName"), _g(a, "InvocationValue")
            if name in FIXED and val > 0:
                cap = SP_CAP if name.startswith("MP_") else HP_CAP
                o = offs[s]
                if struct.unpack_from("<i", out, o)[0] != val:
                    raise RuntimeError(f"{k}: InvocationValue offset mismatch")
                struct.pack_into("<i", out, o, min(cap, int(round(val * mult))))
                changed += 1
    log(f"skills: {changed} fixed HP/SP restores of party skills x{mult:.2f} at danger {floor}")
    return ua, bytes(out)
