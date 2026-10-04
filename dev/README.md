# Developer tools

**Before any in-game test: `python dev/snapshot.py take`, and `python dev/snapshot.py restore`
after.** The game autosaves into SaveData0 (and writes SystemData.sav) during test runs;
backing up only the slot you edit is not enough.

| Script | What it does |
|---|---|
| `test_matrix.py <saves…>` | build + validate every preset against each save (nothing installed) |
| `make_fresh_save.py <src> <out> [level]` | synthetic start-of-game save for early-game builds (write it outside the save folder) |
| `balance_report.py` | regenerate `docs/BALANCE.md` |
| `snapshot.py take/restore` | byte-exact snapshot of the whole SaveGames folder |
| `bootcheck.ps1` | launch via Steam, confirm the game stays up, close it |
| `run_damage_test.ps1` | load the newest save, walk into a fight, screenshot every action (leaves the game running - close it) |
| `damage_test.py` | build a test pak with throwaway items + fast encounters and equip them (`--restore` to undo) |
| `screenshot.ps1`, `input.ps1` | capture the screen / send keys to the game window |

Keep test scripts that change the pak **outside** `src/`: the launcher rebuilds when a source
file changes and would overwrite the test pak at launch. Afterwards delete
`logs/installed_build.json` and run the launcher with `--build` to reinstall the real pak.
