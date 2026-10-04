"""Write a synthetic start-of-game save (0 chapters, active party at a given level) to test
early-game builds. Builds only READ saves, so this never touches the real save folder.

    python dev/make_fresh_save.py <source save> <output .sav> [level]
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
import gvas   # noqa: E402


def main(src, dst, level=5):
    s = gvas.SaveFile.load(src)
    s.get("MainProgressPoint").value = 0
    for m in s.get("PlayerMember").value:
        for p in m:
            if p.name.startswith("Level") and p.value > 0:
                p.value = level
    data = s.to_bytes()
    gvas.SaveFile(data)
    with open(dst, "wb") as f:
        f.write(data)
    print("wrote", dst)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 5)
