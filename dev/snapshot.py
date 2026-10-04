"""Snapshot / restore the whole Octopath SaveGames folder byte-for-byte.

    python dev/snapshot.py take      -> copies every file to <user dir>/save_snapshot/
    python dev/snapshot.py restore   -> puts every file back, deletes files that were not
                                        there, verifies byte-identical

Use around every in-game test: the game autosaves into SaveData0 (and writes
SystemData.sav) while it runs.
"""
import filecmp
import os
import shutil
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
import paths  # noqa: E402

SG = paths.save_roots()[0]
SNAP = os.path.join(paths.user_dir(), "save_snapshot")


def take():
    if os.path.exists(SNAP):
        shutil.rmtree(SNAP)
    shutil.copytree(SG, SNAP)
    print("snapshot:", len(os.listdir(SNAP)), "files ->", SNAP)


def restore():
    snap = set(os.listdir(SNAP))
    for f in os.listdir(SG):
        if f not in snap:
            os.remove(os.path.join(SG, f))
            print("removed new file", f)
    for f in snap:
        shutil.copy2(os.path.join(SNAP, f), os.path.join(SG, f))
    bad = [f for f in snap if not filecmp.cmp(os.path.join(SNAP, f), os.path.join(SG, f),
                                              shallow=False)]
    if bad or set(os.listdir(SG)) != snap:
        sys.exit(f"RESTORE MISMATCH: {bad}")
    print("restored", len(snap), "files byte-identical")


if __name__ == "__main__":
    {"take": take, "restore": restore}[sys.argv[1]]()
