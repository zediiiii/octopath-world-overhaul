"""What's left to do in a save: chapters, side stories (with where they start), optional bosses
and unexplored places - the same counts relentless's completion uses.

    python dev/whats_left.py [save]        (default: the newest save)
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
import build_difficulty_mod as B   # noqa: E402
import gvas                        # noqa: E402
import pak                         # noqa: E402
import paths                       # noqa: E402
import side_stories as S           # noqa: E402
import uasset                      # noqa: E402

g = B.g


def main(save):
    s = gvas.SaveFile.load(save)
    done = B.completion(save)
    print(f"{os.path.basename(save)}: {done['share'] * 100:.1f}% complete -> relentless world "
          f"{B.COMPLETION_TOP * done['share']:.0f} from completion")
    for k in ("chapters", "side_stories", "optional_bosses", "areas"):
        print(f"  {k.replace('_', ' ')}: {done[k]}/{done['totals'][k]}")

    # side stories not finished, with where they start
    slots, _total = S.slots()
    grps = s.get("SubMissionData").value
    state = {}
    for a, grp in enumerate(grps):
        st = {q.name.split("_")[0]: q.value for q in grp}["MissionState"]
        for pos, story in slots.get(a, ()):
            if pos < len(st):
                state[story] = max(state.get(story, 0), st[pos])
    g_ = S._Guide()
    left = {}
    for st in S.stories():
        if st["real"] and state.get(st["group"], 0) != 2 and st["group"] not in left:
            first = S.walkthrough(st, g_)[:1]
            left[st["group"]] = (st["title"], state.get(st["group"], 0),
                                 first[0][7:] if first else "?")
    print(f"\nSide stories not finished ({len(left)}):")
    for title, stt, where in sorted(left.values(), key=lambda x: (-x[1], x[0])):
        print(f"  {'IN PROGRESS' if stt == 1 else 'not started'}: {title} - {where}")

    # optional bosses not fought
    p = pak.Pak(paths.base_pak())
    rows = uasset.read_datatable(p.read(B.ENEMY + ".uasset"), p.read(B.ENEMY + ".uexp"))
    text = uasset.read_datatable(p.read("Octopath_Traveler/Content/GameText/Database/GameTextEN.uasset"),
                                 p.read("Octopath_Traveler/Content/GameText/Database/GameTextEN.uexp"))
    id_row = {g(v, "EnemyID"): k for k, v in rows.items()}
    _per, groups = B._completion_data()
    info = s.get("EnemyInfoData").value
    fought = lambda i: 0 <= i < len(info) and any(q.value for q in info[i])
    print("\nOptional bosses not fought:")
    for grp, ids in sorted(groups.items()):
        if not any(fought(i) for i in ids):
            names = {(text.get(g(rows[id_row[i]], "DisplayNameID")) or {}).get("Text") for i in ids}
            print(f"  {grp}: {', '.join(n for n in names if n)}")

    # places never visited
    wm = uasset.read_datatable(p.read(B.WORLD_MAP + ".uasset"), p.read(B.WORLD_MAP + ".uexp"))
    vm = s.get("VisitedMap").value
    seen = lambda i: i // 32 < len(vm) and (vm[i // 32] >> (i % 32)) & 1
    print("\nPlaces never visited:")
    for v in list(wm.values())[B.WORLD_MAP_DEMO_ROWS:]:
        ids = {int(x) for x in list(g(v, "RefLevelName")) + [g(v, "MoveLevelName")]
               if x and x != "None"}
        if ids and not any(seen(i) for i in ids):
            name = (text.get(g(v, "MapName")) or {}).get("Text")
            region = (text.get(g(v, "RegionName")) or {}).get("Text")
            print(f"  {name} ({region})")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else max(paths.find_saves(), key=os.path.getmtime))
