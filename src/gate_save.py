"""A save point in the Gate of Finis.

The game has 197 save points, all the same placement (the "Saveman" NPC, talk event
SC_SYS_SA0_000000) listed per map in PlacementInfoList - and none in the Gate of Finis, so
nothing in there could be saved. This clones one into the Gate's first hall, beside the
party monument, as a new PlacementInfoData row (the template's name with a fresh FName
number, so both tables can name it without a name-table edit) added to that map's list.
"""
import struct

import datatable as dt
import paths
import uasset

C = "Octopath_Traveler/Content/Character/Database/"
PLACEMENTS = C + "PlacementInfoData"
LISTS = C + "PlacementInfoList"
TEMPLATE = "NPC_DMnt31_A_N000"          # a save point in another Highlands dungeon
GATE_MAP = "D_Mount_3_3_A"              # the Gate's first hall
SPOT = (-755.0, 260.0, 483.0)           # beside the party monument (-755, 0, 483)
NEW_NUMBER = 0x5A7E                     # FName number of the new row (TEMPLATE_<n-1>)


def _array_names(ue, names, lo, hi):
    """(tag offset, count) of the one NameProperty array in a PlacementInfoList row."""
    for p in range(lo, hi - 33):
        idx, num = struct.unpack_from("<ii", ue, p)
        if num == 0 and 0 <= idx < len(names) and names[idx].startswith("LabelList"):
            tidx = struct.unpack_from("<i", ue, p + 8)[0]
            if 0 <= tidx < len(names) and names[tidx] == "ArrayProperty":
                return p, struct.unpack_from("<i", ue, p + 33)[0]
    raise RuntimeError("LabelList array not found")


def patch(files, base, log=print):
    """Add the save point to `files` (on top of any PlacementInfoData / List already there)."""
    def get(path):
        if path + ".uasset" in files:
            return files[path + ".uasset"], files[path + ".uexp"]
        ua, ue, _src = paths.installed_asset(path, base)
        return ua, ue

    # the placement: a copy of the template row, renamed and moved
    ua, ue = get(PLACEMENTS)
    names, _ = uasset.names_of(ua)
    spans = {s[0]: s for s in dt.row_spans(ua, ue)}
    new_key = f"{TEMPLATE}_{NEW_NUMBER - 1}"
    if new_key in spans:
        return
    _nm, idx, _num, lo, hi = spans[TEMPLATE]
    row = bytearray(ue[lo:hi])
    struct.pack_into("<ii", row, 0, idx, NEW_NUMBER)
    for field, val in zip(("SpawnPosX", "SpawnPosY", "SpawnPosZ"), SPOT):
        offs = dt.field_offsets_in(bytes(row), names, 0, len(row), field, "FloatProperty")
        if len(offs) != 1:
            raise RuntimeError(f"{TEMPLATE}: {len(offs)} {field} fields")
        struct.pack_into("<f", row, offs[0], val)
    ua, ue = dt.append_rows(ua, ue, [bytes(row)])
    rows = uasset.read_datatable(ua, ue)
    got = rows.get(new_key) or {}
    if got.get("ActionID") != "NpcCmn_Saveman" or got.get("SpawnPosY") != SPOT[1]:
        raise RuntimeError("the new save point row did not read back")
    dt.verify(ua, ue)
    files[PLACEMENTS + ".uasset"], files[PLACEMENTS + ".uexp"] = ua, ue

    # the Gate's placement list: one more name in its array
    la, le = get(LISTS)
    lnames, _ = uasset.names_of(la)
    if TEMPLATE not in lnames:
        raise RuntimeError(f"{TEMPLATE} not in PlacementInfoList's names")
    lspans = {s[0]: s for s in dt.row_spans(la, le)}
    _nm, _i, _n, lo, hi = lspans[GATE_MAP]
    lrow = bytearray(le[lo:hi])
    tag, count = _array_names(bytes(lrow), lnames, 0, len(lrow))
    end = tag + 37 + 8 * count
    lrow[end:end] = struct.pack("<ii", lnames.index(TEMPLATE), NEW_NUMBER)
    struct.pack_into("<i", lrow, tag + 33, count + 1)
    size = struct.unpack_from("<i", lrow, tag + 16)[0]
    struct.pack_into("<i", lrow, tag + 16, size + 8)
    la, le = dt.replace_rows(la, le, {GATE_MAP: bytes(lrow)})
    labels = list(uasset.read_datatable(la, le)[GATE_MAP].values())[0]
    if labels[-1] != new_key or len(labels) != count + 1:
        raise RuntimeError("the Gate's placement list did not read back")
    dt.verify(la, le)
    files[LISTS + ".uasset"], files[LISTS + ".uexp"] = la, le
    log("Gate of Finis: a save point in the first hall, beside the party monument")
