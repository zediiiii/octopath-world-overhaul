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


def patched_files(base_pak):
    ua = base_pak.read(ASSET + ".uasset")
    ue = base_pak.read(ASSET + ".uexp")
    return {ASSET + ".uasset": ua, ASSET + ".uexp": patch(ua, ue)}


def check(base_pak, mod_pak):
    """-> list of problems with the patched blueprint in mod_pak (empty = fine)."""
    ua = base_pak.read(ASSET + ".uasset")
    ue = base_pak.read(ASSET + ".uexp")
    if mod_pak.read(ASSET + ".uasset") != ua:
        return ["BattlePlayerBP.uasset differs from the shipped one"]
    mod = mod_pak.read(ASSET + ".uexp")
    if mod != patch(ua, ue):
        return ["BattlePlayerBP.uexp is not exactly the expected patch"]
    pkg = kismet.Package(ua, mod)
    code = "\n".join(s for _m, s in kismet.disassemble(pkg, _refs(pkg)["fn"]))
    if "EquipmentWeapon)" in code.split("Array_Length", 1)[1].split("\n", 1)[0]:
        return ["the loop still runs over weapons only"]
    if code.count("Equipment[local:exp:Temp_int_Array_Index_Variable]") != 3:
        return ["elemental boosts are not read from every equipped slot"]
    return []
