"""Set up a decisive in-game test of the damage cap and the passive-effect question.

Builds the normal overhaul plus two throwaway test items, installs it, and seeds + equips
them on the party leader in a backed-up copy of the save:

  * "Cap Test Blade"  - 999 Atk and WEAPON_ABILITY_UP 1000 (a 10x damage multiplier, which
    is NOT subject to the 999 stat cap). If BATTLE_DAMAGE_CAP really is raised, a hit will
    read well above 9999; if the engine ignores the value we patched, it will read exactly
    9999. Either way the number on screen answers it.
  * "Regen Test Pendant" - ADD_MP_FIXED_REGENERATION 99, so SP visibly climbs after each
    action if accessory passives work at all.

Run `python damage_test.py --restore` afterwards to put the save and the normal pak back.
"""
import os
import shutil
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
import paths  # noqa: E402
import build_all  # noqa: E402
import buildlog
import gvas
import respec_core as rc
import build_difficulty_mod as B

SAVE = max(paths.find_saves(), key=os.path.getmtime) if paths.find_saves() else None
BACKUP = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backups",
                      "damage_test_backup.sav")
INPUT_INI = os.path.join(paths.documents_dir(), "My Games", "Octopath_Traveler", "Config",
                         "WindowsNoEditor", "Input.ini")
INPUT_BACKUP = INPUT_INI + ".orig"

TEST_ITEMS = [
    dict(tier=99, kind="weapon", slot="sword", template="ITM_WS_045",
         name="Cap Test Blade", stats={"ATK": 999, "CON": 999},
         ailment=("WEAPON_ABILITY_UP", 1000), price=1,
         desc="TEST ITEM: 10x damage multiplier, to see where damage stops."),
    dict(tier=99, kind="accessory", slot="accessory", template="ITM_AC_033",
         name="Regen Test Pendant", stats={"HP": 100},
         ailment=("ADD_MP_FIXED_REGENERATION", 99), price=1,
         desc="TEST ITEM: restores 99 SP after every action."),
]


def fast_encounters(files):
    """Make random encounters fire after a couple of steps instead of ~240.

    Walking far enough for a natural encounter takes a minute of synthetic input; with this
    the fight starts almost immediately, so the test needs only a few seconds of an unlocked
    screen. Test builds only - the normal build leaves encounter rates alone.
    """
    import struct
    import uasset
    import datatable as dt
    import pak as pakmod
    ua = files[B.VOLUME + ".uasset"]
    ue = bytearray(files[B.VOLUME + ".uexp"])
    rows = uasset.read_datatable(ua, bytes(ue))
    for field, value in (("EncountStepMin", 4), ("RandomStepA", 1), ("RandomStepB", 1)):
        offs = B.int_offsets(ua, bytes(ue), field, expect=len(rows))
        for o in offs:
            if struct.unpack_from("<i", ue, o)[0] > 0:
                struct.pack_into("<i", ue, o, value)
    uasset.read_datatable(ua, bytes(ue))        # must still parse
    files[B.VOLUME + ".uexp"] = bytes(ue)
    return files


def enable_console():
    """UE4 shipping builds usually strip the console, but the binding costs nothing to try."""
    if not os.path.exists(INPUT_BACKUP):
        shutil.copy2(INPUT_INI, INPUT_BACKUP)
    with open(INPUT_INI, "w", encoding="utf-8") as f:
        f.write("[/Script/Engine.InputSettings]\n"
                "ConsoleKeys=Tilde\n"
                "ConsoleKeys=F10\n")


def restore_console():
    if os.path.exists(INPUT_BACKUP):
        shutil.copy2(INPUT_BACKUP, INPUT_INI)
        os.remove(INPUT_BACKUP)


def setup():
    log = buildlog.get()
    original = build_all.design_catalogue

    def with_tests(nums):
        return original(nums) + TEST_ITEMS

    import pakwrite
    original_write = pakwrite.write_pak

    def write_with_fast_encounters(path, files, mount="../../../"):
        # mutate the caller's dict, not a copy - build_all verifies the written pak against
        # this same dict afterwards, and a copy makes that check fail
        fast_encounters(files)
        return original_write(path, files, mount)

    build_all.design_catalogue = with_tests
    pakwrite.write_pak = write_with_fast_encounters
    try:
        path, minted, floor = build_all.main(
            os.path.join(B.MODS_DIR, build_all.OUT_NAME))
    finally:
        build_all.design_catalogue = original
        pakwrite.write_pak = original_write

    ids = {m["name"]: m["id"] for m in minted if m["name"] in
           ("Cap Test Blade", "Regen Test Pendant")}
    log.info("test item ids: %s", ids)
    if len(ids) != 2:
        raise RuntimeError(f"test items missing from build: {ids}")

    shutil.copy2(SAVE, BACKUP)
    log.info("save backed up to %s", BACKUP)

    ed = rc.SaveEditor(SAVE)
    for iid in ids.values():
        ed._set_item_count(iid, 5)
    ed.write(os.path.join(os.path.dirname(os.path.abspath(__file__)), "backups"))

    # equip them on the party leader so no in-game menu work is needed
    s = gvas.SaveFile.load(SAVE)
    # slotData.MainMemberCharacterID is the real party order; PlayerParty.MainMemberID holds
    # member slots, not character ids (it reads 4 here while the leader on screen is H'aanit)
    slot = {p.name: p.value for p in s.get("slotData").value}
    leader_id = slot["MainMemberCharacterID"][0]
    log.info("party leader characterID=%s (party %s)", leader_id,
             slot["MainMemberCharacterID"])
    for m in s.get("PlayerMember").value:
        cid = next(p.value for p in m if p.name.startswith("CharacterID"))
        if cid != leader_id:
            continue
        eq = next(p.value for p in m if p.name.startswith("Equipment"))
        for prop in eq:
            field = prop.name.split("_")[0]
            if field == "Sword":
                log.info("  Sword %s -> %s", prop.value, ids["Cap Test Blade"])
                prop.value = ids["Cap Test Blade"]
            elif prop.name.startswith("Accessory_00"):
                log.info("  Accessory_00 %s -> %s", prop.value, ids["Regen Test Pendant"])
                prop.value = ids["Regen Test Pendant"]
    data = s.to_bytes()
    gvas.SaveFile(data)                     # must still parse
    with open(SAVE, "wb") as f:
        f.write(data)
    log.info("equipped on leader and written")

    enable_console()
    log.info("console keys written to Input.ini (Tilde / F10) - may be stripped in shipping")
    log.info("")
    log.info("READY: launch, load slot 7, walk to trigger an encounter, attack.")
    return ids


def restore():
    log = buildlog.get()
    if os.path.exists(BACKUP):
        shutil.copy2(BACKUP, SAVE)
        log.info("save restored from %s", BACKUP)
    restore_console()
    path, _minted, _floor = build_all.main(os.path.join(B.MODS_DIR, build_all.OUT_NAME))
    log.info("normal pak rebuilt at %s", path)


if __name__ == "__main__":
    if "--restore" in sys.argv:
        buildlog.run(restore, name="damage_test_restore")
    else:
        buildlog.run(setup, name="damage_test_setup")
