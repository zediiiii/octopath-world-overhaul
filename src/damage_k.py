"""Damage numbers of 100,000 or more show as thousands with a "k" ("345k", "1000k").

The battle number widget (BattleDamageNumber.SetVisibilityType) has five digit images,
units to ten-thousands, so with the damage cap at 999,999 a big hit lost its leading digit.
Its font is a texture atlas, 10 digit columns x 5 colour rows, read through the material
parameters Tex_U (column), Tex_V (row) and the grid size Split_V (columns) / Split_U (rows):
the names are swapped in the material - checked on the BP/SP atlas (3 rows, 2 columns,
Split_U 3 / Split_V 2) and the death-count font (1 row, 10 columns, Split_U 1 / Split_V 10).

  * Texture: both atlases (x1 512x512 and x2 1024x1024, DXT5, one mip) are widened to twice
    their width. The digit blocks are copied unchanged; column 10 holds a "k" in each colour
    (data/damage_k.bin, drawn by dev/make_damage_k.py); columns 11-19 stay empty.
  * Material instances: Split_V 10 -> 20, so every digit keeps its exact cell.
  * Widget: before the digit loop, if Number >= 100,000 it becomes Number / 1000 * 10, so
    the digits move up one slot; when the units image is set and the number was big, its
    Tex_U becomes 10 (the k). New code is appended after the function's END and reached by
    two redirected statements (kismet.jump_padding), so no existing offset moves.
"""
import os
import struct
import zlib

import kismet
import paths

WIDGET = "Octopath_Traveler/Content/UI/Battle/BP/BattleDamageNumber"
FUNCTION = "SetVisibilityType"
TEXTURES = ("Octopath_Traveler/Content/UI/Battle/Texture/UiTX_Battle_DamageFont_atlas",
            "Octopath_Traveler/Content/UI/Battle/Texture_x2/UiTX_Battle_DamageFont_atlas")
MATERIALS = ("Octopath_Traveler/Content/UI/Battle/Material/Mi_Battle_DamageFont",
             "Octopath_Traveler/Content/UI/Battle/Material_x2/Mi_Battle_DamageFont")
GLYPH = os.path.join(paths.data_dir(), "damage_k.bin")
BIG = 100000
K_COLUMN = 10.0
# the atlas's own fully transparent block (alpha 0, colour 0x2e2c2b-ish)
EMPTY_BLOCK = bytes.fromhex("0000000000000000" "66318529aaaaaaaa")


def glyph_strips():
    """-> (x1 strip, x2 strip): DXT5 blocks of the new column, 16 / 32 blocks wide."""
    with open(GLYPH, "rb") as f:
        d = zlib.decompress(f.read())
    n1, n2 = struct.unpack_from("<II", d)
    return d[8:8 + n1], d[8 + n1:8 + n1 + n2]


# ---- texture -------------------------------------------------------------------------------
def _layout(ue):
    """Offsets of the cooked Texture2D's platform data fields (UE 4.18, one DXT5 mip)."""
    p = ue.index(b"\x08\x00\x00\x00PF_DXT5\x00") + 4
    w, h, slices = struct.unpack_from("<iii", ue, p - 16)
    first, mips, cooked, flags, count, disk = struct.unpack_from("<iiiIii", ue, p + 8)
    data = p + 40
    if not (w == h and slices == 1 and first == 0 and mips == 1 and cooked == 1
            and count == disk == w * w and struct.unpack_from("<ii", ue, data + w * w) == (w, w)
            and len(ue) == data + w * w + 8 + 8 + 4):
        raise RuntimeError("damage font atlas: not the expected single-mip DXT5 layout")
    return dict(p=p, w=w, data=data, flags=flags)


def texture_mips(ue):
    L = _layout(ue)
    return [ue[L["data"]:L["data"] + L["w"] ** 2]]


def patch_texture(ua, ue, strip):
    """-> (ua, ue) with the atlas twice as wide: old blocks, then the strip, then empty."""
    import datatable as dt
    pkg = kismet.Package(ua, ue)
    L = _layout(ue)
    p, w, data = L["p"], L["w"], L["data"]
    row = w // 4 * 16                       # bytes per row of blocks
    sw = len(strip) // (w // 4)             # strip bytes per row of blocks
    if sw * (w // 4) != len(strip) or sw > row:
        raise RuntimeError("damage k strip does not fit the atlas")
    old = ue[data:data + w * w]
    new = bytearray()
    for r in range(w // 4):
        new += old[r * row:(r + 1) * row] + strip[r * sw:(r + 1) * sw] \
            + EMPTY_BLOCK * ((row - sw) // 16)
    grow = len(new) - len(old)
    out = bytearray(ue[:data]) + new + struct.pack("<ii", 2 * w, w) + ue[data + w * w + 8:]
    struct.pack_into("<i", out, p - 16, 2 * w)                 # SizeX
    struct.pack_into("<ii", out, p + 24, 2 * w * w, 2 * w * w)  # element count, size on disk
    # SkipOffset (absolute file offset of the platform data's end marker)
    skip = struct.unpack_from("<i", ue, p - 20)[0]
    if skip != pkg.header + len(ue) - 12:
        raise RuntimeError("damage font atlas: unexpected SkipOffset")
    struct.pack_into("<i", out, p - 20, skip + grow)
    # ImportedSize property (IntPoint) - kept consistent with the new size
    ni = pkg.names.index("ImportedSize")
    t = ue.index(struct.pack("<ii", ni, 0))
    if struct.unpack_from("<ii", ue, t + 49) != (w, w):
        raise RuntimeError("damage font atlas: ImportedSize not where expected")
    struct.pack_into("<i", out, t + 49, 2 * w)
    # export size and the bulk data start in the summary
    s = dt.package_summary(ua)
    out_ua = bytearray(ua)
    if len(pkg.exports) != 1:
        raise RuntimeError("damage font atlas: expected one export")
    so = s["ExportOffset"][1] + 28
    if struct.unpack_from("<q", ua, so)[0] != len(ue) - 4:
        raise RuntimeError("damage font atlas: export size not as expected")
    struct.pack_into("<q", out_ua, so, len(out) - 4)
    bo, bv = s["BulkDataStartOffset"]
    struct.pack_into("<q", out_ua, bo, bv + grow)
    return bytes(out_ua), bytes(out)


# ---- material instance -----------------------------------------------------------------
def patch_material(ua, ue):
    """-> ue with the ScalarParameterValue Split_V (columns) 10.0 -> 20.0."""
    names = kismet.Package(ua, ue).names
    n = lambda s: struct.pack("<ii", names.index(s), 0)
    k = ue.index(n("Split_V"))
    want = n("ParameterValue") + n("FloatProperty") + struct.pack("<ii", 4, 0) + b"\0"
    if ue.count(n("Split_V")) != 1 or ue[k + 8:k + 33] != want \
            or struct.unpack_from("<f", ue, k + 33)[0] != 10.0:
        raise RuntimeError("Mi_Battle_DamageFont: Split_V not as expected")
    return ue[:k + 33] + struct.pack("<f", 20.0) + ue[k + 37:]


# ---- widget ------------------------------------------------------------------------------
def _i32(v):
    return struct.pack("<i", v)


def patch_widget(ua, ue):
    pkg = kismet.Package(ua, ue)
    fn = pkg.export_index(FUNCTION, cls="Function")
    loc = {x: pkg.export_index(x, outer=FUNCTION) for x in (
        "Number", "TmpDigit", "CallFunc_EqualEqual_IntInt_ReturnValue",
        "CallFunc_Conv_IntToFloat_ReturnValue", "CallFunc_EqualEqual_ByteByte_ReturnValue")}
    imp = {x["name"]: -(i + 1) for i, x in enumerate(pkg.imports)}
    st = {m: (p, b, s) for m, p, b, s in kismet.spans(pkg, fn)}
    expect = {
        659: "LET local:exp:TmpDigit = 1",
        682: "SETARRAY local:exp:K2Node_MakeArray_Array = [inst:exp:1, inst:exp:10, "
             "inst:exp:100, inst:exp:1000, inst:exp:10000]",
        2667: "local:exp:CallFunc_GetDynamicMaterial_ReturnValue.SetScalarParameterValue("
              "name:Tex_U, local:exp:CallFunc_Conv_IntToFloat_ReturnValue)",
        2721: "LET local:exp:CallFunc_EqualEqual_IntInt_ReturnValue = "
              "EqualEqual_IntInt(local:exp:TmpDigit, 1)",
        3216: "END"}
    for m, s in expect.items():
        if st.get(m, (0, 0, None))[2] != s:
            raise RuntimeError(f"BattleDamageNumber: unexpected code at {m}: {st.get(m)}")
    if max(st) != 3216:
        raise RuntimeError("BattleDamageNumber: code after END (already patched?)")
    off, size, mem = pkg.script(fn)
    code = bytearray(pkg.ue[off:off + size])
    # the "small number" flag reuses a bool the function only uses before the digit loop
    # (weakness / break label checks), so it is free from here on
    flag = b"\x00" + _i32(loc["CallFunc_EqualEqual_ByteByte_ReturnValue"])
    num = b"\x00" + _i32(loc["Number"])
    let_int = lambda dst, call: b"\x0f" + _i32(loc[dst]) + b"\x00" + _i32(loc[dst]) + call

    # A, entered instead of "TmpDigit = 1" (659), once per number:
    #   TmpDigit = 1; small = Number < 100000
    #   if not small: Number = Number / 1000; Number = Number * 10
    #   -> 682 (the digit loop)
    a, a_end = kismet.assemble(pkg, mem, [
        st[659][1],
        b"\x14" + flag + b"\x68" + _i32(imp["Less_IntInt"]) + num + b"\x1d" + _i32(BIG) + b"\x16",
        ("jumpifnot", "big", flag),
        ("jump", 682),
        ("label", "big"),
        let_int("Number", b"\x68" + _i32(imp["Divide_IntInt"]) + num + b"\x1d" + _i32(1000) + b"\x16"),
        let_int("Number", b"\x68" + _i32(imp["Multiply_IntInt"]) + num + b"\x1d" + _i32(10) + b"\x16"),
        ("jump", 682)])
    # B, entered instead of the Tex_U statement (2667), for every digit image:
    #   if big and TmpDigit == 1: digit = 10 (the k column)
    #   SetScalarParameterValue(Tex_U, digit); -> 2721
    conv = loc["CallFunc_Conv_IntToFloat_ReturnValue"]
    eq = b"\x00" + _i32(loc["CallFunc_EqualEqual_IntInt_ReturnValue"])
    b, _end = kismet.assemble(pkg, a_end, [
        ("jumpifnot", "big", flag),
        ("jump", "set"),
        ("label", "big"),
        st[2721][1],                                    # eq = TmpDigit == 1
        ("jumpifnot", "set", eq),
        b"\x0f" + _i32(conv) + b"\x00" + _i32(conv) + b"\x1e" + struct.pack("<f", K_COLUMN),
        ("label", "set"),
        st[2667][1],
        ("jump", 2721)])
    for m, tgt in ((659, mem), (2667, a_end)):
        p, old, _s = st[m]
        code[p:p + len(old)] = kismet.jump_padding(
            pkg, tgt, len(old), kismet.mem_size(pkg, old), loc["TmpDigit"])
    code += a + b
    out_ua, out_ue = kismet.replace_script(ua, ue, fn, bytes(code))
    check_widget(out_ua, out_ue)
    return out_ua, out_ue


def check_widget(ua, ue):
    """Raise unless the patched SetVisibilityType reads back as planned."""
    pkg = kismet.Package(ua, ue)
    fn = pkg.export_index(FUNCTION, cls="Function")
    bad = kismet.bad_jumps(pkg, fn)
    if bad:
        raise RuntimeError(f"BattleDamageNumber: jumps into the middle of a statement: {bad}")
    st = kismet.disassemble(pkg, fn, past_end=True)
    texts = [s for _m, s in st]
    tail = texts[texts.index("END") + 1:]
    F = "local:exp:CallFunc_EqualEqual_ByteByte_ReturnValue"
    want = ["LET local:exp:TmpDigit = 1",
            f"LET {F} = Less_IntInt(local:exp:Number, 100000)",
            "JUMPIFNOT ", "JUMP 682",
            "LET local:exp:Number = Divide_IntInt(local:exp:Number, 1000)",
            "LET local:exp:Number = Multiply_IntInt(local:exp:Number, 10)",
            "JUMP 682",
            "JUMPIFNOT ", "JUMP ",
            "LET local:exp:CallFunc_EqualEqual_IntInt_ReturnValue = EqualEqual_IntInt(local:exp:TmpDigit, 1)",
            "JUMPIFNOT ",
            "LET local:exp:CallFunc_Conv_IntToFloat_ReturnValue = 10.0",
            "local:exp:CallFunc_GetDynamicMaterial_ReturnValue.SetScalarParameterValue(name:Tex_U, "
            "local:exp:CallFunc_Conv_IntToFloat_ReturnValue)",
            "JUMP 2721"]
    if len(tail) != len(want) or not all(t.startswith(w) for t, w in zip(tail, want)):
        raise RuntimeError(f"BattleDamageNumber: appended code reads back wrong: {tail}")
    m659 = next(s for m, s in st if m == 659)
    m2667 = next(s for m, s in st if m == 2667)
    starts = [m for m, _s in st]
    a0 = starts[texts.index("END") + 1]
    b0 = starts[texts.index("END") + 8]
    if m659 != f"JUMP {a0}" or m2667 != f"JUMP {b0}":
        raise RuntimeError("BattleDamageNumber: redirects not in place")
    # the flag must be free inside the loop: written only before 682 by the shipped code
    writes = [m for m, s in st if s.startswith(f"LET {F} =") and 682 <= m < 3217]
    if writes:
        raise RuntimeError(f"BattleDamageNumber: {F} is written inside the loop at {writes}")
    # branch targets: "big" paths land where planned
    jn = [(m, s) for m, s in st[texts.index("END") + 1:] if s.startswith("JUMPIFNOT")]
    tgt = [int(s.split()[1]) for _m, s in jn]
    exp = [starts[texts.index("END") + 5], starts[texts.index("END") + 10],
           starts[texts.index("END") + 13]]
    if tgt != exp:
        raise RuntimeError(f"BattleDamageNumber: branch targets {tgt}, expected {exp}")
    jb = st[texts.index("END") + 9][1]
    if jb != f"JUMP {starts[texts.index('END') + 13]}":
        raise RuntimeError(f"BattleDamageNumber: small-number path jumps wrong: {jb}")


def patched_files(base_pak):
    """-> {pak path: bytes} for the widget, both atlases and both material instances."""
    out = {}
    ua, ue = base_pak.read(WIDGET + ".uasset"), base_pak.read(WIDGET + ".uexp")
    out[WIDGET + ".uasset"], out[WIDGET + ".uexp"] = patch_widget(ua, ue)
    for path, strip in zip(TEXTURES, glyph_strips()):
        ua, ue = base_pak.read(path + ".uasset"), base_pak.read(path + ".uexp")
        out[path + ".uasset"], out[path + ".uexp"] = patch_texture(ua, ue, strip)
    for path in MATERIALS:
        ua, ue = base_pak.read(path + ".uasset"), base_pak.read(path + ".uexp")
        out[path + ".uasset"], out[path + ".uexp"] = ua, patch_material(ua, ue)
    return out


def check(base_pak, mod_pak):
    """-> list of problems with the damage-k files in mod_pak (empty = fine)."""
    try:
        want = patched_files(base_pak)
    except Exception as exc:                       # noqa: BLE001
        return [f"damage k patch cannot be rebuilt: {exc}"]
    problems = [f"{p.rsplit('/', 1)[-1]} is not exactly the planned patch"
                for p, data in want.items() if mod_pak.read(p) != data]
    if not problems:
        try:
            check_widget(mod_pak.read(WIDGET + ".uasset"), mod_pak.read(WIDGET + ".uexp"))
        except Exception as exc:                   # noqa: BLE001
            problems.append(str(exc))
    return problems


ASSETS = (WIDGET,) + TEXTURES + MATERIALS
