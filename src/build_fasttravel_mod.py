"""Build a mod pak that lets you fast travel to every *visited* location, not just towns.

It flips the CanFastTravel flag in WorldMapTable for every real location (fields, dungeons,
caves, shrines). It does NOT touch the save's VisitedMap, so places you have never been to
stay locked exactly as before.

It also clears LevelTable's ImpossibleFCFlag (no fast travel from here; the world map reads
it) on the Gate of Finis, so you can travel out to restock and come back - the game sets it
on those two levels only (plus one small event room, left alone).

The 10 leftover demo rows (indexes 0-9, duplicates of real Cobbleston/Sunshade levels)
are left alone so the world map doesn't get duplicate icons.
"""
import paths
import os
import re
import struct
import sys

import pak
import uasset
import pakwrite

TABLE = "Octopath_Traveler/Content/Level/Database/WorldMapTable"
SKIP_ROWS = set(range(10))   # leftover demo rows duplicating real level IDs
OUT_NAME = "FastTravelAnywhere_p.pak"
LEVELS = "Octopath_Traveler/Content/Level/Database/LevelTable"
TRAVEL_OUT_OF = ("D_Mount_3_3_A", "D_Mount_3_3_B")   # The Gate of Finis


def flag_offsets(ua, ue, field="CanFastTravel"):
    """Byte offset of each row's `field` (a BoolProperty) value, in row order."""
    names, _ = uasset.names_of(ua)
    prop = [n for n in names if n.startswith(field)]
    if len(prop) != 1:
        raise RuntimeError(f"{field} name entry not found")
    idx = names.index(prop[0])
    pat = struct.pack("<ii", idx, 0)
    offs = []
    for m in re.finditer(re.escape(pat), ue):
        o = m.start()
        tname = names[struct.unpack_from("<i", ue, o + 8)[0]]
        size, _i = struct.unpack_from("<ii", ue, o + 16)
        if tname != "BoolProperty" or size != 0:
            raise RuntimeError(f"unexpected {field} layout")
        offs.append(o + 24)      # name(8) type(8) size(4) index(4) -> value byte
    return offs


def patched_files(p=None, verbose=False):
    """-> {path: bytes} for WorldMapTable with CanFastTravel on every real location, and
    LevelTable letting you travel out of the Gate of Finis."""
    p = p or pak.Pak(paths.base_pak())
    files = build(p=p, verbose=verbose, pack=False)
    files.update(gate_files(p))
    return files


def gate_files(p):
    """LevelTable (as installed - another mod's copy if any) with ImpossibleFCFlag cleared on
    the Gate of Finis levels."""
    ua, ue, _src = paths.installed_asset(LEVELS, p)
    ue = bytearray(ue)
    rows = list(uasset.read_datatable(ua, bytes(ue)).items())
    offs = flag_offsets(ua, bytes(ue), "ImpossibleFCFlag")
    if len(offs) != len(rows):
        raise RuntimeError(f"{len(offs)} ImpossibleFCFlag vs {len(rows)} LevelTable rows")
    done = []
    for (_k, v), o in zip(rows, offs):
        name = next(vv for kk, vv in v.items() if kk.split("_")[0] == "LevelName")
        if name in TRAVEL_OUT_OF and ue[o] == 1:
            ue[o] = 0
            done.append(name)
    after = uasset.read_datatable(ua, bytes(ue))
    if len(after) != len(rows):
        raise RuntimeError("LevelTable no longer parses")
    return {LEVELS + ".uasset": ua, LEVELS + ".uexp": bytes(ue)} if done else {}


def build(out_path=None, verbose=True, p=None, pack=True):
    p = p or pak.Pak(paths.base_pak())
    ua = p.read(TABLE + ".uasset")
    ue = bytearray(p.read(TABLE + ".uexp"))

    rows = list(uasset.read_datatable(ua, bytes(ue)).items())
    offs = flag_offsets(ua, bytes(ue))
    if len(offs) != len(rows):
        raise RuntimeError(f"{len(offs)} flags vs {len(rows)} rows")

    before = [ue[o] for o in offs]
    parsed = [next(vv for kk, vv in v.items() if kk.split("_")[0] == "CanFastTravel")
              for _k, v in rows]
    if before != parsed:
        raise RuntimeError("flag offsets do not line up with parsed rows")

    changed = []
    for i, o in enumerate(offs):
        if i in SKIP_ROWS:
            continue
        if ue[o] == 0:
            ue[o] = 1
            changed.append(rows[i][0])
    if verbose:
        print(f"rows: {len(rows)}, already travelable: {sum(before)}, newly enabled: {len(changed)}")

    # sanity: nothing but the intended bytes moved
    orig = p.read(TABLE + ".uexp")
    diff = [i for i in range(len(orig)) if orig[i] != ue[i]]
    assert len(ue) == len(orig), "size changed"
    assert diff == sorted(offs[i] for i in range(len(offs))
                          if i not in SKIP_ROWS and before[i] == 0), "unexpected byte diff"

    # verify the patched table still parses and only the flag changed
    after_rows = uasset.read_datatable(ua, bytes(ue))
    for (k, v), (k2, v2) in zip(rows, after_rows.items()):
        assert k == k2
        for key in v:
            if key.split("_")[0] != "CanFastTravel":
                assert v[key] == v2[key], f"{k}.{key} changed"
    enabled = sum(1 for v in after_rows.values()
                  if next(vv for kk, vv in v.items() if kk.split("_")[0] == "CanFastTravel"))
    if verbose:
        print(f"after patch, travelable rows: {enabled}")

    files = {TABLE + ".uasset": ua, TABLE + ".uexp": bytes(ue)}
    if not pack:
        return files
    out_path = out_path or os.path.join(paths.mods_dir(), OUT_NAME)
    size = pakwrite.write_pak(out_path, files)

    # read our own pak back and confirm the payload survives the round trip
    q = pak.Pak(out_path)
    assert q.read(TABLE + ".uexp") == bytes(ue), "pak round-trip failed (uexp)"
    assert q.read(TABLE + ".uasset") == ua, "pak round-trip failed (uasset)"
    if verbose:
        print(f"wrote {out_path} ({size} bytes); pak re-read OK, mount {q.mount!r}, "
              f"{len(q.entries)} files")
    return out_path, changed


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else None)
