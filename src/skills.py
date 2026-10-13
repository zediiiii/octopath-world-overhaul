"""Party skills with fixed numbers grow with the world; elemental runes cover the party.

Most skills scale with the user's stats, but some restore a fixed amount: Alfyn's concoctions
(Restore Health 500 .. Concoct Panacea 9,999), Rest's 25-100 SP, hired helpers' First Aid /
Prayer. They were tuned for vanilla endgame HP (~2,900: Restore Health heals ~70%, Incredible
Heal is a full heal), so their HP amounts grow with the party's HP (hp_mult = expected max HP
at the world's danger / vanilla's) and SP amounts by SP_SHARE of that growth.
Items keep their own values (they climb loot ladders instead, see rewards.py); enemy and
boss skills are left alone.
"""
import re
import struct

import uasset

ABILITIES = "Octopath_Traveler/Content/Ability/Database/AbilityData"
FIXED = ("HP_FIXED_RECOVERY", "HP_FIXED_RECOVERY_SELF", "MP_FIXED_RECOVERY")
PARTY_KEY = re.compile(r"BT_(ABI|MAKA_ABI)_\d+$")     # party and concoct skills, not BOS_/ENE_
SP_SHARE = 0.4                 # SP pools grow less than HP pools
HP_CAP, SP_CAP = 99999, 9999


def sp_mult(hp_mult):
    return 1 + SP_SHARE * (hp_mult - 1)


def _g(row, pre):
    return next(v for k, v in row.items() if k.split("_")[0] == pre)


def scale(ua, ue, hp_mult, item_names, text, floor, log=print):
    """-> (ua, ue) with every party skill's fixed HP / SP restore scaled for the world.
    item_names: display names of items, whose use-abilities are left alone."""
    mult = max(1.0, hp_mult)
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
                sp = name.startswith("MP_")
                cap = SP_CAP if sp else HP_CAP
                o = offs[s]
                if struct.unpack_from("<i", out, o)[0] != val:
                    raise RuntimeError(f"{k}: InvocationValue offset mismatch")
                m = sp_mult(mult) if sp else mult
                struct.pack_into("<i", out, o, min(cap, int(round(val * m))))
                changed += 1
    log(f"skills: {changed} fixed restores of party skills: HP x{mult:.2f}, SP "
        f"x{sp_mult(mult):.2f} at danger {floor}")
    return ua, bytes(out)


# ---- elemental runes cover the party -------------------------------------------------------
# The Runelord's six elemental runes enchant only the caster's weapons, so they felt weak; they
# now target every ally, as Heal Wounds does (Transfer Rune keeps its own job). The extra
# damage itself is worked out in the game's code, not in data.
# (Better Descriptions documents the damage: the equipped weapon's Elem. Atk. x 8 - so runes grow
# with elemental-attack weapons.)
RUNES = ("Fire Rune", "Ice Rune", "Thunder Rune", "Wind Rune", "Light Rune", "Dark Rune")
ALL_ALLIES = "ETARGET_TYPE::NewEnumerator2"      # Heal Wounds' target type


def rune_rows(rows, text):
    return [k for k, v in rows.items() if PARTY_KEY.match(k)
            and (text.get(_g(v, "DisplayName")) or {}).get("Text") in RUNES]


def runes_for_all(ua, ue, text, log=print):
    """-> (ua, ue, [rune Detail labels]) with every elemental rune targeting all allies."""
    import datatable as dt
    rows = uasset.read_datatable(ua, ue)
    names, _ = uasset.names_of(ua)
    if ALL_ALLIES not in names:
        raise RuntimeError(f"{ALL_ALLIES} not in AbilityData names")
    tidx = next(i for i, n in enumerate(names) if n.split("_")[0] == "TargetType")
    pat = struct.pack("<ii", tidx, 0)
    spans = {s[0]: (s[3], s[4]) for s in dt.row_spans(ua, ue)}
    out = bytearray(ue)
    keys = rune_rows(rows, text)
    for k in keys:
        lo, hi = spans[k]
        p = ue.find(pat, lo, hi)
        if p < 0 or names[struct.unpack_from("<i", ue, p + 8)[0]] not in ("EnumProperty",
                                                                          "ByteProperty"):
            raise RuntimeError(f"{k}: TargetType not found")
        # name8 type8 size4 index4 enum-name8 hasguid1, then the value (an FName)
        dt.set_fname(out, p + 33, names.index(ALL_ALLIES), 0)
    log(f"runes: {len(keys)} elemental rune skills now enchant the whole party")
    return ua, bytes(out), sorted({_g(rows[k], "Detail") for k in keys})


def rune_text(ua, ue, labels, log=print):
    """Rune descriptions say they cover the party (the game's wording and Better
    Descriptions')."""
    import datatable as dt
    import hashlib
    rows = uasset.read_datatable(ua, ue)
    names, _ = uasset.names_of(ua)
    spans = {s[0]: s for s in dt.row_spans(ua, ue)}
    new = {}
    for lab in labels:
        cur = (rows.get(lab) or {}).get("Text") or ""
        txt = cur.replace("Weapons the user attacks with", "Weapons the party attacks with")
        if txt.startswith("Physical attacks will"):
            txt = "The party's physical attacks will" + txt[len("Physical attacks will"):]
        if "x 8" not in txt:
            txt += "\\nDamage: Elem. Atk. of equipped weapon x 8"   # the game's line break
        if txt != cur:
            _n, idx, num, _a, _b = spans[lab]
            key = hashlib.md5(("rune:" + lab).encode()).hexdigest().upper()
            new[lab] = dt.build_text_row(names, idx, num, key, txt)
    if new:
        ua, ue = dt.replace_rows(ua, ue, new)
    log(f"runes: {len(new)} descriptions say they cover the party")
    return ua, ue
