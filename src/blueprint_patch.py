"""Let elemental damage boosts on armour and accessories count (BattlePlayerBP).

The game totals a character's elemental boost in BattlePlayerBP.SearchMagicAbilityUpFromAll-
Weapon: start at 100%, then for every equipped WEAPON add (value - 100) for each boost of the
spell's element. GetOnHitDamageDiseaseRatio multiplies the hit by that total, after buffs and
support skills. Armour and accessories are never looked at - measured in-game: two x10 Fire
accessories on Cyrus did nothing.

The loop runs over EquipmentWeapon (the slots holding a weapon) and reads Equipment[slot].
Equipment always has all 11 slots in order (blank entries for empty ones), so the patch:
  * loops over Equipment instead of EquipmentWeapon, and
  * reads Equipment[loop index] instead of Equipment[EquipmentWeapon[loop index]].
Both are same-size swaps of an object reference, so no offset or jump moves. The leftover
reads of EquipmentWeapon[loop index] go past its end for armour/accessory slots, which the
engine answers with a log warning and a zero byte that nothing uses.

Shipped armour and accessories carry no elemental boost, so vanilla items behave exactly as
before; boosts still add up, now across every equipped piece.
"""
import struct

import kismet

ASSET = "Octopath_Traveler/Content/Battle/BP/BattlePlayerBP"
FUNCTION = "SearchMagicAbilityUpFromAllWeapon"


def _refs(pkg):
    fn = pkg.export_index(FUNCTION, cls="Function")
    return dict(
        fn=fn,
        equipment=pkg.export_index("Equipment", cls="ArrayProperty", outer="BattlePlayerBP_C"),
        weapons=pkg.export_index("EquipmentWeapon", cls="ArrayProperty",
                                 outer="BattlePlayerBP_C"),
        slot=pkg.export_index("CallFunc_Conv_ByteToInt_ReturnValue", outer=FUNCTION),
        index=pkg.export_index("Temp_int_Array_Index_Variable", outer=FUNCTION))


def _tok(token, index):
    return bytes([token]) + struct.pack("<i", index)


def patch(ua, ue):
    """-> patched .uexp bytes (the .uasset is unchanged). Raises if the code isn't the
    exact shipped function."""
    pkg = kismet.Package(ua, ue)
    r = _refs(pkg)
    before = [s for _m, s in kismet.disassemble(pkg, r["fn"])]
    off, size, _mem = pkg.script(r["fn"])
    code = bytearray(ue[off:off + size])

    # Array_Length(inst:EquipmentWeapon) - the only use followed directly by end-of-params
    length_call = _tok(0x01, r["weapons"]) + b"\x16"
    if code.count(length_call) != 1:
        raise RuntimeError(f"{FUNCTION}: expected one Array_Length(EquipmentWeapon)")
    i = code.index(length_call)
    code[i:i + 5] = _tok(0x01, r["equipment"])
    # Equipment[local slot] -> Equipment[local loop index]
    by_slot = b"\x6b" + _tok(0x01, r["equipment"]) + _tok(0x00, r["slot"])
    if code.count(by_slot) != 3:
        raise RuntimeError(f"{FUNCTION}: expected Equipment[slot] three times, "
                           f"found {code.count(by_slot)}")
    code = bytearray(code.replace(
        by_slot, b"\x6b" + _tok(0x01, r["equipment"]) + _tok(0x00, r["index"])))

    out = bytearray(ue)
    out[off:off + size] = code
    after = [s for _m, s in kismet.disassemble(kismet.Package(ua, bytes(out)), r["fn"])]
    expect_changed = sum(1 for s in before
                         if "Array_Length(inst:exp:EquipmentWeapon)" in s
                         or "Equipment[local:exp:CallFunc_Conv_ByteToInt_ReturnValue]" in s)
    changed = [(a, b) for a, b in zip(before, after) if a != b]
    if len(before) != len(after) or len(changed) != expect_changed or expect_changed != 4:
        raise RuntimeError(f"{FUNCTION}: patch changed {len(changed)} statements, "
                           f"expected 4")
    return bytes(out)


# ---- battle money follows the equipment JP bonus (BattleManagerBP) -----------------------
# CalcGetReward multiplies battle money by (support ratio + MoneyRatioByEquipment - 1), but
# nothing in the game ever sets MoneyRatioByEquipment (always 1.0); equipment only reaches
# the EXP and JP ratios. Reading JPRatioByEquipment there instead makes JP-up gear raise
# money by the same percentage: one same-size reference swap, 1 byte.
MANAGER = "Octopath_Traveler/Content/Battle/BP/BattleManagerBP"
REWARD_FUNCTION = "CalcGetReward"


def patch_manager(ua, ue):
    pkg = kismet.Package(ua, ue)
    fn = pkg.export_index(REWARD_FUNCTION, cls="Function")
    money = pkg.export_index("MoneyRatioByEquipment", outer="BattleManagerBP_C")
    jp = pkg.export_index("JPRatioByEquipment", outer="BattleManagerBP_C")
    off, size, _mem = pkg.script(fn)
    code = bytearray(ue[off:off + size])
    tok = _tok(0x01, money)
    if code.count(tok) != 1:
        raise RuntimeError(f"{REWARD_FUNCTION}: expected one MoneyRatioByEquipment read")
    before = [x for _m, x in kismet.disassemble(pkg, fn)]
    code = bytearray(code.replace(tok, _tok(0x01, jp)))
    out = bytearray(ue)
    out[off:off + size] = code
    after = [x for _m, x in kismet.disassemble(kismet.Package(ua, bytes(out)), fn)]
    changed = [(a, b) for a, b in zip(before, after) if a != b]
    if len(before) != len(after) or len(changed) != 1 or "JPRatioByEquipment" not in changed[0][1]:
        raise RuntimeError(f"{REWARD_FUNCTION}: patch changed {len(changed)} statements")
    return _jp_not_cumulative(ua, bytes(out))


def _jp_not_cumulative(ua, ue):
    """SetJPRatioByEquipment: JP = Ratio + JP - 1 (every JP item adds up) becomes
    JP = FMax(Ratio, JP) + 0 - only the strongest JP (and so money) item counts (user
    2026-10-04: "that effect can't be cumulative"). Swaps the math function and the -1.0."""
    pkg = kismet.Package(ua, ue)
    fn = pkg.export_index("SetJPRatioByEquipment", cls="Function")
    add = next(i for i, x in enumerate(pkg.imports) if x["name"] == "Add_FloatFloat")
    fmax = next(i for i, x in enumerate(pkg.imports) if x["name"] == "FMax")
    off, size, _mem = pkg.script(fn)
    code = bytearray(ue[off:off + size])
    call_add = b"h" + struct.pack("<i", -(add + 1))
    minus_one = b"" + struct.pack("<f", -1.0)
    if code.count(call_add) != 2 or code.count(minus_one) != 1:
        raise RuntimeError("SetJPRatioByEquipment: not the shipped code")
    i = code.index(call_add)
    code[i:i + 5] = b"h" + struct.pack("<i", -(fmax + 1))
    j = code.index(minus_one)
    code[j:j + 5] = b"" + struct.pack("<f", 0.0)
    out = bytearray(ue)
    out[off:off + size] = code
    st = [x for _m, x in kismet.disassemble(kismet.Package(ua, bytes(out)), fn)]
    if not (st[0].startswith("LET local:exp:CallFunc_Add_FloatFloat_ReturnValue = FMax(")
            and "0.0)" in st[1]):
        raise RuntimeError(f"SetJPRatioByEquipment patch unexpected: {st[:2]}")
    return bytes(out)


PATCHES = ((ASSET, patch), (MANAGER, patch_manager))


def patched_files(base_pak):
    out = {}
    for asset, fn in PATCHES:
        ua = base_pak.read(asset + ".uasset")
        ue = base_pak.read(asset + ".uexp")
        out[asset + ".uasset"], out[asset + ".uexp"] = ua, fn(ua, ue)
    return out


def check(base_pak, mod_pak):
    """-> list of problems with the patched blueprints in mod_pak (empty = fine)."""
    problems = []
    for asset, fn in PATCHES:
        ua = base_pak.read(asset + ".uasset")
        ue = base_pak.read(asset + ".uexp")
        name = asset.rsplit("/", 1)[-1]
        if mod_pak.read(asset + ".uasset") != ua:
            problems.append(f"{name}.uasset differs from the shipped one")
        elif mod_pak.read(asset + ".uexp") != fn(ua, ue):
            problems.append(f"{name}.uexp is not exactly the expected patch")
    if problems:
        return problems
    pkg = kismet.Package(base_pak.read(ASSET + ".uasset"), mod_pak.read(ASSET + ".uexp"))
    code = "\n".join(x for _m, x in kismet.disassemble(pkg, _refs(pkg)["fn"]))
    if code.count("Equipment[local:exp:Temp_int_Array_Index_Variable]") != 3:
        problems.append("elemental boosts are not read from every equipped slot")
    return problems


# ---- optional: dash button toggles instead of hold (ActionController_Impl) ---------------
# OnActionDash(Press) runs, via the event graph, "if player input: SetPlayerDash(Press)",
# so dash only lasts while the button is held. The event's entry jump is pointed at a new
# block appended after the graph's last instruction (nothing existing moves):
#     OnIsPlayerInput(ok); if not ok: the original "SetPlayerDash(false)" path
#     if not Press: return                      (release does nothing)
#     tmp = GetPlayerDash(self); tmp = !tmp; SetPlayerDash(self, tmp); return
# tmp reuses an event-graph bool (CallFunc_Not_PreBool_ReturnValue) whose other use is a
# self-contained two-statement sequence. Every byte sequence copies the graph's own encoding.
ACTION = "Octopath_Traveler/Content/Character/BP/ActionController_Impl"


def _u32(v):
    return struct.pack("<I", v)


def patch_dash_toggle(ua, ue):
    import datatable as dt
    pkg = kismet.Package(ua, ue)
    fn = pkg.export_index("ExecuteUbergraph_ActionController_Impl", cls="Function")
    imp = {x["name"]: -(i + 1) for i, x in enumerate(pkg.imports)}
    loc = {n: pkg.export_index(n, outer="ExecuteUbergraph_ActionController_Impl")
           for n in ("K2Node_Event_Press", "CallFunc_OnIsPlayerInput_IsPlayerInput2",
                     "CallFunc_Not_PreBool_ReturnValue")}
    off, size, mem = pkg.script(fn)
    code = ue[off:off + size]
    st = {m: s for m, s in kismet.disassemble(pkg, fn)}
    # the shipped shape this patch is written against
    expect = {3808: "JUMP 2465", 3813: "RETURN nothing",
              2502: "obj:imp:Default__KSGameStatics.SetPlayerDash(self, local:exp:K2Node_Event_Press)"}
    for m, s in expect.items():
        if st.get(m) != s:
            raise RuntimeError(f"ActionController_Impl: unexpected code at {m}: {st.get(m)}")
    if not st.get(2488, "").startswith("JUMPIFNOT 2549 ("):
        raise RuntimeError("ActionController_Impl: player-input check not where expected")
    i32 = lambda v: struct.pack("<i", v)
    ctx = b"\x19\x20" + i32(imp["Default__KSGameStatics"])
    tmp = b"\x00" + i32(loc["CallFunc_Not_PreBool_ReturnValue"])
    block = (
        b"\x1b" + code[code.index(b"\x1b"):][1:9]            # OnIsPlayerInput (FName copied)
        if False else b"")
    # copy the two shipped statements at 2465 / 2488 verbatim
    d = kismet.Disassembler(pkg, code)
    spans = {}
    while d.p < size:
        m, p0 = d.mem, d.p
        s = d.expr()
        spans[m] = code[p0:d.p]
        if s == "END":
            break
    block = (spans[2465]                                                   # OnIsPlayerInput
             + spans[2488]                                                 # -> 2549 if not
             + b"\x07" + _u32(3813) + b"\x00" + i32(loc["K2Node_Event_Press"])   # release: return
             + b"\x14" + tmp + ctx + _u32(11) + i32(loc["CallFunc_Not_PreBool_ReturnValue"])
             + b"\x1c" + i32(imp["GetPlayerDash"]) + b"\x17\x16"           # tmp = GetPlayerDash
             + b"\x14" + tmp + b"\x68" + i32(imp["Not_PreBool"]) + tmp + b"\x16"  # tmp = !tmp
             + ctx + _u32(20) + i32(0) + b"\x1c" + i32(imp["SetPlayerDash"])
             + b"\x17" + tmp + b"\x16"                                     # SetPlayerDash(tmp)
             + b"\x06" + _u32(3813))                                       # return
    entry = spans[3808]
    if entry != b"\x06" + _u32(2465):
        raise RuntimeError("ActionController_Impl: entry jump bytes differ")
    new_code = bytearray(code)
    j = None
    # the 5-byte entry jump sits at the disk offset of mem 3808
    dd = kismet.Disassembler(pkg, code)
    while dd.p < size:
        m, p0 = dd.mem, dd.p
        dd.expr()
        if m == 3808:
            j = p0
            break
    new_code[j:j + 5] = b"\x06" + _u32(mem)          # jump to the appended block
    new_code += block
    # in-memory size of the block (8-byte object refs, 12-byte names)
    blk_mem = kismet.Disassembler(pkg, bytes(block))
    while blk_mem.p < len(block):
        blk_mem.expr()
    grow = len(block)
    out_ue = bytearray(ue[:off - 8]) + struct.pack("<ii", mem + blk_mem.mem, size + grow) \
        + new_code + ue[off + size:]
    # export table: this export grows, later ones move
    e = pkg.exports[fn - 1]
    s = dt.package_summary(ua)
    out_ua = bytearray(ua)
    eo = s["ExportOffset"][1]
    for i, x in enumerate(pkg.exports):
        base = eo + i * 104
        if struct.unpack_from("<qq", out_ua, base + 28) != (x["size"], x["off"] + pkg.header):
            raise RuntimeError("export table layout not as expected")
        if i + 1 == fn:
            struct.pack_into("<q", out_ua, base + 28, x["size"] + grow)
        elif x["off"] > e["off"]:
            struct.pack_into("<q", out_ua, base + 36, x["off"] + pkg.header + grow)
    bo, bv = s["BulkDataStartOffset"]
    struct.pack_into("<q", out_ua, bo, bv + grow)
    out_ua, out_ue = bytes(out_ua), bytes(out_ue)
    # proof: the patched package parses, every other export is byte-identical, and the
    # event graph reads back as planned
    new = kismet.Package(out_ua, out_ue)
    for i, (a, b) in enumerate(zip(pkg.exports, new.exports)):
        if i + 1 != fn and pkg.ue[a["off"]:a["off"] + a["size"]] != new.ue[b["off"]:b["off"] + b["size"]]:
            raise RuntimeError(f"dash toggle: export {a['name']} changed")
    st2 = [s for _m, s in kismet.disassemble(new, fn, past_end=True)]
    tail = st2[st2.index("END") + 1:]
    want = ["OnIsPlayerInput(", "JUMPIFNOT 2549", "JUMPIFNOT 3813 (local:exp:K2Node_Event_Press)",
            "LET local:exp:CallFunc_Not_PreBool_ReturnValue = obj:imp:Default__KSGameStatics.GetPlayerDash(self)",
            "LET local:exp:CallFunc_Not_PreBool_ReturnValue = Not_PreBool(local:exp:CallFunc_Not_PreBool_ReturnValue)",
            "obj:imp:Default__KSGameStatics.SetPlayerDash(self, local:exp:CallFunc_Not_PreBool_ReturnValue)",
            "JUMP 3813"]
    if len(tail) != len(want) or not all(t.startswith(w) for t, w in zip(tail, want)):
        raise RuntimeError(f"dash toggle block reads back wrong: {tail}")
    return out_ua, out_ue


def dash_toggle_files(base_pak):
    ua, ue = patch_dash_toggle(base_pak.read(ACTION + ".uasset"), base_pak.read(ACTION + ".uexp"))
    return {ACTION + ".uasset": ua, ACTION + ".uexp": ue}
