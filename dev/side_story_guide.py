"""Write docs/SIDE_STORIES.md: the walkthrough of every side story, as the journal shows it.

    python dev/side_story_guide.py
"""
import collections
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
import side_stories as S   # noqa: E402

REGION_ORDER = ["Frostlands", "Flatlands", "Coastlands", "Highlands", "Sunlands",
                "Riverlands", "Cliftlands", "Woodlands"]


def main():
    g = S._Guide()
    by_region = collections.defaultdict(list)
    seen = set()
    for s in S.stories():
        if not s["real"] or s["detail"] in seen:
            continue
        seen.add(s["detail"])
        recs = [r for r in S.stories() if r["detail"] == s["detail"] and r["real"]]
        lines = S.walkthrough(s, g)
        if len(recs) > 1:
            places = [S.walkthrough(r, g)[0].split(f" {S.DASH} ", 1)[-1] for r in recs]
            lines = [f"Start: {lines[0][7:].split(f' {S.DASH} ')[0]}, met in one of: "
                     + "; ".join(places)] + lines[1:]
        region = next((r for r in REGION_ORDER if r in lines[0]), "Elsewhere")
        by_region[region].append((s["title"], lines))
    out = ["# Side stories - walkthroughs",
           "",
           "Generated from the game's data by `dev/side_story_guide.py`; the same text is in "
           "each side story's journal entry in game. Places are *town, region*.",
           ""]
    for region in REGION_ORDER + ["Elsewhere"]:
        if not by_region.get(region):
            continue
        out += [f"## {region}", ""]
        for title, lines in sorted(by_region[region]):
            out.append(f"### {title}")
            out.append("")
            out += [f"- {ln.strip()}" if not ln.startswith("    ") else f"  {ln.strip()}"
                    for ln in lines]
            out.append("")
    path = os.path.join(ROOT, "docs", "SIDE_STORIES.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(out))
    print(f"wrote {path} ({len(seen)} side stories)")


if __name__ == "__main__":
    main()
