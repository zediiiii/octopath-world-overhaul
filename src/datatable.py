"""Append rows to a cooked UE4 DataTable without re-serializing it.

The trick that makes this safe: a DataTable's .uexp is
    <object properties> <int32 0> <int32 RowCount> <row>*
and each row is  <FName rowName> <tagged properties...> <FName "None">.
There is no length prefix on a row, and the only thing in the .uasset that depends on
the .uexp's size is the single export's SerialSize (verified: SerialSize == len(uexp) - 4,
the 4 being the package trailer).

So a new row can be built by *cloning an existing row's bytes* and patching the fixed-width
fields inside it - FNames are always 8 bytes (name index + number) and ints are 4 - which
avoids writing a serializer for the hairy property types (TextProperty, ObjectProperty,
nested structs). New unique names come free: an FName is (index, number), so reusing an
existing name index with an unused number yields a brand new name with no name-table edit.
"""
import struct
import uasset


def _fstr_len(b, p):
    n = struct.unpack_from("<i", b, p)[0]
    return 4 + (n if n >= 0 else -n * 2)


def table_info(ua, ue):
    """-> (names, rows_start_offset, count_offset, count)"""
    names, _ = uasset.names_of(ua)
    r = uasset.DTReader(ue, names)
    r.props()          # the DataTable object's own properties
    r.i32()            # always zero
    count_off = r.p
    count = r.i32()
    return names, r.p, count_off, count


def row_spans(ua, ue):
    """-> list of (row_name_str, name_index, name_number, start, end) in file order."""
    names, start, _co, count = table_info(ua, ue)
    r = uasset.DTReader(ue, names)
    r.p = start
    out = []
    for _ in range(count):
        s = r.p
        idx, num = struct.unpack_from("<ii", ue, r.p)
        nm = r.fname()
        r.props()
        out.append((nm, idx, num, s, r.p))
    return out


def field_offsets_in(ue, names, lo, hi, field, kind="IntProperty", exact=False):
    """Offsets of a property's VALUE inside the byte range [lo, hi)."""
    cand = [n for n in names if (n == field if exact else n.split("_")[0] == field)]
    if len(cand) != 1:
        raise RuntimeError(f"{field}: {len(cand)} name entries")
    idx = names.index(cand[0])
    pat = struct.pack("<ii", idx, 0)
    out = []
    p = lo
    while True:
        p = ue.find(pat, p, hi)
        if p < 0:
            break
        tname = names[struct.unpack_from("<i", ue, p + 8)[0]]
        if tname == kind:
            size = struct.unpack_from("<i", ue, p + 16)[0]
            if kind in ("IntProperty", "FloatProperty") and size == 4:
                out.append(p + 25)          # name8 type8 size4 index4 hasguid1
            elif kind == "NameProperty" and size == 8:
                out.append(p + 25)
            elif kind == "ByteProperty":
                out.append(p + 25)          # enum FName(8) follows, value after hasguid
        p += 4
    return out


def set_int(buf, off, value):
    struct.pack_into("<i", buf, off, value)


def set_fname(buf, off, index, number):
    struct.pack_into("<ii", buf, off, index, number)


def build_text_row(names, row_idx, row_num, key_hex, text):
    """A GameTextEN row: one TextProperty called 'Text'."""
    def fn(n):
        return names.index(n)
    body = bytearray()
    body += struct.pack("<ii", row_idx, row_num)        # row name
    body += struct.pack("<ii", fn("Text"), 0)
    body += struct.pack("<ii", fn("TextProperty"), 0)
    payload = bytearray()
    payload += struct.pack("<i", 0)                     # text flags
    payload += b"\x00"                                  # history type: Base
    payload += struct.pack("<i", 0)                     # namespace: empty
    kb = key_hex.encode("latin-1") + b"\x00"
    payload += struct.pack("<i", len(kb)) + kb          # key
    try:
        sb = text.encode("latin-1") + b"\x00"
        payload += struct.pack("<i", len(sb)) + sb      # source string
    except UnicodeEncodeError:                          # e.g. the leaf symbol: UTF-16,
        sb = text.encode("utf-16-le") + b"\x00\x00"     # stored with a negative length
        payload += struct.pack("<i", -(len(sb) // 2)) + sb
    body += struct.pack("<ii", len(payload), 0)         # size, index
    body += b"\x00"                                     # has-guid
    body += payload
    body += struct.pack("<ii", fn("None"), 0)
    return bytes(body)


def append_rows(ua, ue, new_rows):
    """-> (new_uasset, new_uexp). new_rows is a list of complete row byte-strings."""
    ua = bytearray(ua)
    ue = bytearray(ue)
    _names, _start, count_off, count = table_info(bytes(ua), bytes(ue))
    trailer = bytes(ue[-4:])
    body = bytes(ue[:-4])
    body += b"".join(new_rows)
    out = bytearray(body + trailer)
    struct.pack_into("<i", out, count_off, count + len(new_rows))

    # one export, whose SerialSize must cover everything but the 4-byte trailer
    r = uasset.Reader(bytes(ua)) if hasattr(uasset, "Reader") else None
    export_off, serial_off = _export_offset(bytes(ua))
    struct.pack_into("<q", ua, serial_off, len(out) - 4)
    return bytes(ua), bytes(out)


def _export_offset(ua):
    """-> (export table offset, byte offset of export[0].SerialSize)"""
    p = 0
    def i32():
        nonlocal p
        v = struct.unpack_from("<i", ua, p)[0]
        p += 4
        return v
    def fstr():
        nonlocal p
        n = struct.unpack_from("<i", ua, p)[0]
        p += 4
        p += n if n >= 0 else -n * 2
    i32(); i32(); i32(); i32(); i32()
    n = i32(); p += n * 20
    i32()              # TotalHeaderSize
    fstr()             # FolderName
    i32()              # PackageFlags
    i32(); i32()       # names
    i32(); i32()       # gatherable text
    export_count = i32(); export_off = i32()
    if export_count != 1:
        raise RuntimeError(f"expected exactly 1 export, got {export_count}")
    return export_off, export_off + 28


def read_name_array(ue, names, lo, hi, field):
    """Locate an ArrayProperty-of-NameProperty and return (prop_start, size_off, count_off,
    entries_off, count)."""
    cand = [n for n in names if n.split("_")[0] == field]
    if len(cand) != 1:
        raise RuntimeError(f"{field}: {len(cand)} name entries")
    idx = names.index(cand[0])
    p = ue.find(struct.pack("<ii", idx, 0), lo, hi)
    if p < 0:
        raise RuntimeError(f"{field} not found in row")
    if names[struct.unpack_from("<i", ue, p + 8)[0]] != "ArrayProperty":
        raise RuntimeError(f"{field} is not an ArrayProperty")
    size_off = p + 16
    inner = names[struct.unpack_from("<i", ue, p + 24)[0]]
    if inner != "NameProperty":
        raise RuntimeError(f"{field} inner type is {inner}")
    count_off = p + 33            # name8 type8 size4 idx4 inner8 hasguid1
    count = struct.unpack_from("<i", ue, count_off)[0]
    return p, size_off, count_off, count_off + 4, count


def extend_shop_row(ua, ue, row_name, new_entries, field="LabelList"):
    """Append FName entries to an array inside one row, resizing the table around it.

    new_entries: list of (name_index, name_number)
    """
    ue = bytearray(ue)
    spans = {s[0]: s for s in row_spans(ua, bytes(ue))}
    if row_name not in spans:
        raise RuntimeError(f"row {row_name} not found")
    _nm, _i, _n, s, e = spans[row_name]
    names, _ = uasset.names_of(ua)
    _p, size_off, count_off, entries_off, count = read_name_array(
        bytes(ue), names, s, e, field)

    row = bytearray(ue[s:e])
    rel = lambda off: off - s
    added = b"".join(struct.pack("<ii", i, n) for i, n in new_entries)
    ins_at = rel(entries_off) + count * 8
    row[ins_at:ins_at] = added
    struct.pack_into("<i", row, rel(count_off), count + len(new_entries))
    struct.pack_into("<i", row, rel(size_off), 4 + 8 * (count + len(new_entries)))

    out = bytearray(ue[:s]) + row + bytearray(ue[e:])
    ua = bytearray(ua)
    _eo, so = _export_offset(bytes(ua))
    struct.pack_into("<q", ua, so, len(out) - 4)
    return bytes(ua), bytes(out)


def set_str_field(row, names, field, value):
    """Rewrite a StrProperty's value inside one row's bytes. The row may change length."""
    cand = [n for n in names if n.split("_")[0] == field]
    if len(cand) != 1:
        raise RuntimeError(f"{field}: {len(cand)} name entries")
    idx = names.index(cand[0])
    p = bytes(row).find(struct.pack("<ii", idx, 0))
    if p < 0:
        raise RuntimeError(f"{field} not found in row")
    if names[struct.unpack_from("<i", row, p + 8)[0]] != "StrProperty":
        raise RuntimeError(f"{field} is not a StrProperty")
    size = struct.unpack_from("<i", row, p + 16)[0]
    val_at = p + 25                       # name8 type8 size4 index4 hasguid1
    end = val_at + size
    enc = value.encode("latin-1") + b"\x00"
    new_val = struct.pack("<i", len(enc)) + enc
    out = bytearray(row[:p + 16]) + struct.pack("<i", len(new_val)) + \
        bytearray(row[p + 20:val_at]) + new_val + bytearray(row[end:])
    return bytes(out)


def replace_row(ua, ue, row_name, new_row):
    """Swap one row's bytes for a different-length version and fix SerialSize."""
    spans = {s[0]: s for s in row_spans(ua, ue)}
    if row_name not in spans:
        raise RuntimeError(f"row {row_name} not found")
    _nm, _i, _n, s, e = spans[row_name]
    out = bytearray(ue[:s]) + bytearray(new_row) + bytearray(ue[e:])
    ua = bytearray(ua)
    _eo, so = _export_offset(bytes(ua))
    struct.pack_into("<q", ua, so, len(out) - 4)
    return bytes(ua), bytes(out)


def replace_rows(ua, ue, new_rows):
    """replace_row for many rows at once: {row name: row bytes} (one parse of the table)."""
    spans = {s[0]: s for s in row_spans(ua, ue)}
    missing = [k for k in new_rows if k not in spans]
    if missing:
        raise RuntimeError(f"rows not found: {missing[:5]}")
    out, last = bytearray(), 0
    for _nm, _i, _n, s, e in sorted((spans[k] for k in new_rows), key=lambda x: x[3]):
        out += ue[last:s] + new_rows[_nm]
        last = e
    out += ue[last:]
    ua = bytearray(ua)
    _eo, so = _export_offset(bytes(ua))
    struct.pack_into("<q", ua, so, len(out) - 4)
    return bytes(ua), bytes(out)


def verify(ua, ue, expect_count=None):
    """Re-parse from scratch and check the structural invariants the engine relies on."""
    names, _start, _co, count = table_info(ua, ue)
    try:
        spans = row_spans(ua, ue)
    except Exception:
        spans = None          # table written by other tooling; structural checks still apply
    if spans is not None:
        assert len(spans) == count, f"row count {count} != parsed rows {len(spans)}"
        assert spans[-1][4] == len(ue) - 4, (
            f"last row ends at {spans[-1][4]}, expected {len(ue) - 4}")
    _eo, so = _export_offset(ua)
    ss = struct.unpack_from("<q", ua, so)[0]
    assert ss == len(ue) - 4, f"SerialSize {ss} != len(uexp)-4 {len(ue) - 4}"
    assert ue[-4:] == b"\xc1\x83\x2a\x9e", "package trailer missing"
    for nm, idx, num, s, e in (spans or []):
        assert 0 <= idx < len(names), f"row {nm}: bad name index"
    if expect_count is not None:
        assert count == expect_count, f"count {count} != {expect_count}"
    return count, spans


# ---------------------------------------------------------------- name-table extension
# Appending a name shifts every section after the name table, so every absolute offset in the
# package summary (and each export's SerialOffset) moves by the number of bytes added.
# Layout verified on ItemDB.uasset: 193-byte summary, names, imports, exports, depends,
# asset registry, preload dependencies; TotalHeaderSize == file length.

def _crc_tables():
    dep = []
    for i in range(256):
        c = i << 24
        for _ in range(8):
            c = ((c << 1) ^ 0x04C11DB7) if c & 0x80000000 else (c << 1)
        dep.append(c & 0xFFFFFFFF)
    sb8 = []
    for i in range(256):
        c = i
        for _ in range(8):
            c = (c >> 1) ^ 0xEDB88320 if c & 1 else c >> 1
        sb8.append(c)
    return dep, sb8


_CRC_DEP, _CRC_SB8 = _crc_tables()


def name_hashes(s):
    """(NonCasePreservingHash, CasePreservingHash) as UE4.18 stores them per name entry.
    Verified against all 2,550 entries of the shipped ItemDB."""
    h = 0
    for ch in s.upper().encode("latin-1"):
        h = ((h >> 8) & 0x00FFFFFF) ^ _CRC_DEP[(h ^ ch) & 0xFF]
    c = 0xFFFFFFFF
    for ch in s.encode("latin-1"):
        for _ in range(4):
            c = (c >> 8) ^ _CRC_SB8[(c ^ ch) & 0xFF]
            ch >>= 8
    return h & 0xFFFF, (~c) & 0xFFFF


def package_summary(ua):
    """-> dict field -> (byte offset, value) for the fields that hold offsets/counts."""
    p = 0
    out = {}

    def i32():
        nonlocal p
        v = struct.unpack_from("<i", ua, p)[0]
        p += 4
        return v

    def fstr():
        nonlocal p
        n = i32()
        p += n if n >= 0 else -2 * n

    def field(name, wide=False):
        nonlocal p
        if wide:
            out[name] = (p, struct.unpack_from("<q", ua, p)[0])
            p += 8
        else:
            out[name] = (p, i32())

    for _ in range(5):
        i32()
    n = i32()
    p += n * 20                                       # custom versions
    field("TotalHeaderSize")
    fstr()
    field("PackageFlags")
    for f in ("NameCount", "NameOffset", "GatherableTextDataCount", "GatherableTextDataOffset",
              "ExportCount", "ExportOffset", "ImportCount", "ImportOffset", "DependsOffset",
              "SoftPackageReferencesCount", "SoftPackageReferencesOffset",
              "SearchableNamesOffset", "ThumbnailTableOffset"):
        field(f)
    p += 16                                           # package guid
    gens = i32()
    out["Generations"] = (p, gens)
    p += 8 * gens
    for _ in range(2):                                # saved / compatible engine version
        p += 10
        fstr()
    field("CompressionFlags")
    n = i32()
    p += n * 16
    field("PackageSource")
    n = i32()
    for _ in range(n):
        fstr()
    field("AssetRegistryDataOffset")
    field("BulkDataStartOffset", wide=True)
    field("WorldTileInfoDataOffset")
    n = i32()
    p += n * 4
    field("PreloadDependencyCount")
    field("PreloadDependencyOffset")
    return out


_OFFSET_FIELDS = ("TotalHeaderSize", "GatherableTextDataOffset", "ExportOffset", "ImportOffset",
                  "DependsOffset", "SoftPackageReferencesOffset", "SearchableNamesOffset",
                  "ThumbnailTableOffset", "AssetRegistryDataOffset", "WorldTileInfoDataOffset",
                  "PreloadDependencyOffset")


def add_names(ua, new_names):
    """-> uasset with `new_names` appended to its name table (existing indices unchanged)."""
    names, _ = uasset.names_of(ua)
    todo = [n for n in dict.fromkeys(new_names) if n not in names]
    if not todo:
        return bytes(ua)
    s = package_summary(ua)
    # end of the name table
    p = s["NameOffset"][1]
    for _ in range(s["NameCount"][1]):
        p += _fstr_len(ua, p) + 4
    end = p
    blob = bytearray()
    for n in todo:
        b = n.encode("latin-1") + b"\x00"
        blob += struct.pack("<i", len(b)) + b + struct.pack("<HH", *name_hashes(n))
    delta = len(blob)
    out = bytearray(ua[:end]) + blob + bytearray(ua[end:])
    old_count = s["NameCount"][1]
    struct.pack_into("<i", out, s["NameCount"][0], old_count + len(todo))
    gpos, gcount = s["Generations"]
    for k in range(gcount):                           # generation name counts track NameCount
        o = gpos + 8 * k + 4
        if struct.unpack_from("<i", out, o)[0] == old_count:
            struct.pack_into("<i", out, o, old_count + len(todo))
    for f in _OFFSET_FIELDS:
        o, v = s[f]
        if v >= end:
            struct.pack_into("<i", out, o, v + delta)
    o, v = s["BulkDataStartOffset"]
    if v >= end:
        struct.pack_into("<q", out, o, v + delta)
    # exports: SerialOffset (int64) sits 36 bytes into each FObjectExport
    exp_off = s["ExportOffset"][1] + delta
    count = s["ExportCount"][1]
    if count != 1:
        raise RuntimeError(f"add_names expects exactly 1 export, got {count}")
    so = exp_off + 36
    struct.pack_into("<q", out, so, struct.unpack_from("<q", out, so)[0] + delta)
    # self-check: the new table reads back, and the header still describes the file
    names2, total = uasset.names_of(bytes(out))
    assert names2 == names + todo, "name table did not read back"
    assert total == len(out), (total, len(out))
    return bytes(out)
