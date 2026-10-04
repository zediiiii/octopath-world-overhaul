"""Build + validate every preset against saves from different stages of the game.

    python dev/test_matrix.py <save> [<save> ...]

Nothing is installed: each build goes to a staging pak and is validated there. Exits
non-zero if any combination fails. Use dev/make_fresh_save.py for a start-of-game save.
"""
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
import paths              # noqa: E402
import config             # noqa: E402
import buildlog           # noqa: E402
import build_all          # noqa: E402
import build_difficulty_mod as B    # noqa: E402
import validate           # noqa: E402


def main(saves):
    log = buildlog.setup("test_matrix")
    results = []
    for save in saves:
        for preset in config.PRESETS:
            cfg = config.load()
            cfg.update(config.PRESETS[preset])
            cfg["preset"] = preset
            config.apply(cfg)
            B.SELECTED_SAVE = save
            out = os.path.join(paths.user_dir(), "matrix_test.pak")
            t = time.time()
            try:
                path, minted, floor = build_all.main(out)
                errors = validate.main(path)
            except Exception as exc:                 # noqa: BLE001
                log.exception("build crashed")
                floor, errors = "?", f"CRASH {exc}"
            results.append((os.path.basename(save), preset, floor, errors, time.time() - t))
            log.info("==> %s %s floor=%s errors=%s", os.path.basename(save), preset, floor, errors)
    if os.path.exists(out):
        os.remove(out)
    print("\nsave | preset | floor | errors | seconds")
    for r in results:
        print(" | ".join(str(x) if not isinstance(x, float) else f"{x:.0f}" for x in r))
    return 0 if all(r[3] == 0 for r in results) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
