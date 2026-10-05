"""Octopath Traveler - World Overhaul launcher (OctopathWorldOverhaul.exe).

The overhaul's numbers are baked into a pak built from YOUR save: how far the story is and
how strong the party is. The game can't recalculate them itself, so this runs before the game:

  1. pick the save you're about to play (or the newest, see overhaul.ini)
  2. if that save's progress / party level, the settings or the mod changed since the last
     install, rebuild, validate and install the pak (~15 s); a failed build keeps the
     previous pak and the game still starts
  3. start the game

Usage
  OctopathWorldOverhaul.exe              pick a save, update, start the game via Steam
  OctopathWorldOverhaul.exe --setup      Steam Play button / Big Picture + desktop shortcut
  OctopathWorldOverhaul.exe --uninstall  remove the pak and the Steam hook
  OctopathWorldOverhaul.exe --build      update only, don't start the game
  ... --wrap <command>                   used by Steam's Launch Options (%command%)
  ... --newest                           skip the picker, use the newest save
"""
import glob
import hashlib
import json
import os
import subprocess
import sys
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import paths          # noqa: E402
import version        # noqa: E402

STEAM_URL = "steam://rungameid/" + paths.APP_ID
SETUP_MARK = "setup_done.json"


def stamp_path():
    return os.path.join(paths.log_dir(), "installed_build.json")


def source_hash():
    if getattr(sys, "frozen", False):
        return version.VERSION
    h = hashlib.sha256()
    for f in sorted(glob.glob(os.path.join(HERE, "*.py"))):
        if os.path.basename(f) in ("launch_octopath.py", "steam_setup.py"):
            continue
        with open(f, "rb") as fh:
            h.update(os.path.basename(f).encode() + fh.read())
    return h.hexdigest()[:16]


# ------------------------------------------------------------------ save info / picker
def save_summary(path):
    import gvas
    import build_difficulty_mod as B
    import respec_core as rc
    if path == B.NEW_GAME:
        B.world_floor(0, 1)
        return dict(path=path, slot="New game", saved="", play="", chapters=0,
                    party="(no save yet - start a new game)", party_lv=1, floor=1,
                    danger="vanilla", progress=0)
    s = gvas.SaveFile.load(path)
    progress = s.get("MainProgressPoint").value
    slot = {x.name.split("_")[0]: x for x in s.get("slotData").value}
    ids = [getattr(x, "value", x) for x in slot["MainMemberCharacterID"].value]
    lv = {}
    for m in s.get("PlayerMember").value:
        f = {x.name.split("_")[0]: x.value for x in m}
        lv[f["CharacterID"]] = f["Level"]
    party = [f"{rc.CHAR_NAMES.get(c, '?')} {lv.get(c, 0)}" for c in ids if lv.get(c, 0) > 0]
    party_lv = B.party_level(path)
    floor, _why = B.world_floor(progress, party_lv)
    # the opening stage leaves the story's areas as shipped
    danger = "vanilla" if B.RAMP and B.STAGE and B.STAGE[0] <= B.RAMP[0][0] else str(floor)
    secs = getattr(slot.get("PlayTime"), "value", 0) or 0
    num = os.path.basename(path)[8:-4]
    return dict(path=path, slot=("Autosave" if num == "0" else f"Slot {num}"),
                saved=time.strftime("%Y-%m-%d %H:%M", time.localtime(os.path.getmtime(path))),
                play=f"{secs // 3600}h{secs // 60 % 60:02d}", chapters=progress // 8,
                party=", ".join(party), party_lv=party_lv, floor=floor, danger=danger,
                progress=progress)


def pick_save(saves, timeout):
    """Small window: which save are you about to play? Returns a path, NEW_GAME, or None
    (cancel). Unreadable saves are left out; the last row is always "New game"."""
    import tkinter as tk
    from tkinter import ttk
    import build_difficulty_mod as B
    infos = []
    for p in sorted(saves, key=os.path.getmtime, reverse=True):
        try:
            infos.append(save_summary(p))
        except Exception:                            # noqa: BLE001
            print(f"skipping unreadable save {p}:")
            print(traceback.format_exc())
    infos.append(save_summary(B.NEW_GAME))
    if len(infos) == 1:
        return B.NEW_GAME
    result = {"path": infos[0]["path"]}
    root = tk.Tk()
    root.title("Orsterra Unbound - which save will you play?")
    root.attributes("-topmost", True)
    frm = ttk.Frame(root, padding=12)
    frm.pack(fill="both", expand=True)
    ttk.Label(frm, text="The world is built for the save you pick. Load the SAME save in "
                        "the game (Continue loads the most recent one). Starting over, or a "
                        "second player on this PC? Pick New game.",
              wraplength=760).pack(anchor="w", pady=(0, 8))
    cols = ("slot", "saved", "play", "chapters", "party", "danger")
    tv = ttk.Treeview(frm, columns=cols, show="headings", height=min(12, len(infos)))
    for c, w, t in (("slot", 80, "Save"), ("saved", 120, "Last saved"), ("play", 70, "Played"),
                    ("chapters", 70, "Chapters"), ("party", 320, "Party"),
                    ("danger", 90, "World danger")):
        tv.heading(c, text=t)
        tv.column(c, width=w, anchor="w")
    for i, s in enumerate(infos):
        tv.insert("", "end", iid=str(i), values=(s["slot"], s["saved"], s["play"],
                                                   s["chapters"], s["party"], s["danger"]))
    tv.selection_set("0")
    tv.pack(fill="both", expand=True)
    msg = ttk.Label(frm, text="")
    msg.pack(anchor="w", pady=(6, 0))
    left = {"t": timeout, "live": True}

    def go(*_a):
        sel = tv.selection()
        result["path"] = infos[int(sel[0])]["path"] if sel else infos[0]["path"]
        root.destroy()

    def cancel():
        result["path"] = None
        root.destroy()

    def touched(*_a):
        left["live"] = False
        msg.config(text="")

    def tick():
        if not left["live"]:
            return
        if left["t"] <= 0:
            go()
            return
        msg.config(text=f"Continuing with the highlighted save in {left['t']} s ...")
        left["t"] -= 1
        root.after(1000, tick)
    tv.bind("<Button-1>", touched)
    tv.bind("<Key>", touched)
    tv.bind("<Double-1>", go)
    btns = ttk.Frame(frm)
    btns.pack(fill="x", pady=(8, 0))
    ttk.Button(btns, text="Build world and play", command=go).pack(side="right")
    ttk.Button(btns, text="Cancel", command=cancel).pack(side="right", padx=6)
    root.after(200, tick)
    root.protocol("WM_DELETE_WINDOW", cancel)
    root.mainloop()
    return result["path"]


# ------------------------------------------------------------------ setup
def setup_dialog():
    import tkinter as tk
    from tkinter import ttk, messagebox
    import steam_setup
    root = tk.Tk()
    root.title("Orsterra Unbound - setup")
    frm = ttk.Frame(root, padding=14)
    frm.pack()
    ttk.Label(frm, text="How do you want to start the game?", font=("", 11, "bold")).pack(
        anchor="w")
    v_steam = tk.BooleanVar(value=True)
    v_lnk = tk.BooleanVar(value=True)
    ttk.Checkbutton(frm, variable=v_steam, text="Steam's Play button and Big Picture run the "
                    "overhaul first (Steam restarts once)").pack(anchor="w", pady=2)
    ttk.Checkbutton(frm, variable=v_lnk, text="Desktop shortcut").pack(anchor="w", pady=2)
    out = {"ok": False}

    def ok():
        out["ok"] = True
        root.destroy()
    ttk.Button(frm, text="Set up", command=ok).pack(side="right", pady=(10, 0))
    ttk.Button(frm, text="Skip", command=root.destroy).pack(side="right", padx=6, pady=(10, 0))
    root.mainloop()
    done = []
    if out["ok"]:
        try:
            if v_lnk.get():
                done.append("shortcut: " + steam_setup.create_shortcut())
            if v_steam.get():
                n = steam_setup.configure_steam()
                done.append(f"Steam launch options set for {n} account(s)")
        except Exception as exc:                             # noqa: BLE001
            messagebox.showerror("Setup", str(exc))
        else:
            messagebox.showinfo("Setup", "\n".join(done) or "Nothing to do.")
    with open(os.path.join(paths.user_dir(), SETUP_MARK), "w") as f:
        json.dump({"version": version.VERSION, "done": done}, f)


def uninstall():
    import steam_setup
    import build_all
    pak_path = os.path.join(paths.mods_dir(), build_all.OUT_NAME)
    if os.path.exists(pak_path):
        os.remove(pak_path)
        print("removed", pak_path)
    if steam_setup.launch_options_set():
        steam_setup.configure_steam(remove=True)
    for f in (stamp_path(), os.path.join(paths.user_dir(), SETUP_MARK)):
        if os.path.exists(f):
            os.remove(f)
    print("Uninstalled. Delete the desktop shortcut and this folder if you like; your saves "
          "were never modified.")


# ------------------------------------------------------------------ main
def update(save_path, log=print):
    """Rebuild + install if anything changed. Returns True if the installed pak is current."""
    import config
    import build_difficulty_mod as B
    import build_all
    import buildlog
    cfg = config.apply(config.load())
    B.SELECTED_SAVE = save_path
    info = save_summary(save_path)
    want = {"save": os.path.normcase(save_path), "progress": info["progress"],
            "party_level": info["party_lv"], "config": config.fingerprint(cfg),
            "source": source_hash()}
    installed = os.path.join(paths.mods_dir(), build_all.OUT_NAME)
    have = {}
    if os.path.exists(stamp_path()):
        try:
            with open(stamp_path(), encoding="utf-8") as f:
                have = json.load(f)
        except ValueError:
            have = {}
    log(f"save: {info['slot']} ({info['chapters']} chapters, party level {info['party_lv']}) "
        f"-> world danger {info['danger']}, preset {cfg['preset']}")
    if have == want and os.path.exists(installed):
        log("installed overhaul is already up to date.")
        return True
    log("building the world for this save ...")
    t = time.time()

    def work():
        buildlog.run(build_all.build_and_check, installed, name="launcher_build")
    err = with_progress(work, f"Building the world for {info['slot']} "
                              f"(danger {info['danger']}, preset {cfg['preset']}) ...")
    if err is None:
        with open(stamp_path(), "w", encoding="utf-8") as f:
            json.dump(want, f)
        log(f"installed in {time.time() - t:.0f}s.")
        return True
    log(err)
    log("*** Build FAILED - the previous overhaul stays installed and the game will "
        "start with it. Details are in the logs folder. ***")
    hint = ""
    if "PermissionError" in err:
        hint = ("\n\nWindows refused to write a file: close the game if it is running, and "
                "check that your antivirus isn't blocking OctopathWorldOverhaul.exe.")
    notify("Orsterra Unbound", "The world could not be rebuilt for this save, so the game will "
           "start with the previous build." + hint + "\n\nDetails: " + paths.log_dir())
    return False


def with_progress(fn, text):
    """Run fn in a thread behind a small 'please wait' window. -> None or an error string."""
    import threading
    box = {"err": None}

    def run():
        try:
            fn()
        except BaseException:                            # noqa: BLE001 (incl. SystemExit)
            box["err"] = traceback.format_exc()
    th = threading.Thread(target=run, daemon=True)
    th.start()
    try:
        import tkinter as tk
        from tkinter import ttk
        root = tk.Tk()
        root.title("Orsterra Unbound")
        root.attributes("-topmost", True)
        frm = ttk.Frame(root, padding=16)
        frm.pack()
        ttk.Label(frm, text=text, wraplength=420).pack(anchor="w")
        bar = ttk.Progressbar(frm, mode="indeterminate", length=420)
        bar.pack(pady=(10, 0))
        bar.start(12)

        def poll():
            if th.is_alive():
                root.after(200, poll)
            else:
                root.destroy()
        root.protocol("WM_DELETE_WINDOW", lambda: None)
        root.after(200, poll)
        root.mainloop()
    except Exception:                                    # noqa: BLE001 (no display)
        pass
    th.join()
    return box["err"]


def notify(title, text):
    try:
        from tkinter import messagebox
        import tkinter as tk
        r = tk.Tk()
        r.withdraw()
        # a withdrawn root's dialog can open behind the game or Steam; keep it in front
        r.attributes("-topmost", True)
        messagebox.showwarning(title, text, parent=r)
        r.destroy()
    except Exception:                                    # noqa: BLE001
        print(text)


def main(argv):
    wrap = argv[argv.index("--wrap") + 1:] if "--wrap" in argv else None
    if wrap is not None or sys.stdout is None:
        logf = open(os.path.join(paths.log_dir(), "launcher.log"), "a", encoding="utf-8")
        sys.stdout = sys.stderr = logf
        print(f"\n==== {time.ctime()}  {version.VERSION}  args={argv}")
    print(f"Octopath Traveler - World Overhaul {version.VERSION}\n")
    if "--setup" in argv:
        setup_dialog()
        return 0
    if "--uninstall" in argv:
        uninstall()
        return 0
    try:
        go = prepare(argv, wrap)
    except Exception:                                    # noqa: BLE001
        # Whatever went wrong, Steam's Play button must still start the game - with the
        # previously installed overhaul, if any.
        print(traceback.format_exc())
        notify("Orsterra Unbound", "The overhaul could not be updated, so the game will start "
               "with the previous build (or without the overhaul).\n\n"
               + explain(sys.exc_info()[1]) + "\n\nDetails: " + paths.log_dir())
        go = "--build" not in argv
    if not go:
        return 1 if go is None else 0
    if wrap is not None:
        print("starting the game (Steam command) ...")
        sys.stdout.flush()
        return subprocess.call(wrap)
    print("starting the game ...")
    os.startfile(STEAM_URL)
    time.sleep(2)
    return 0


def explain(exc):
    """A one-line hint for the errors other people's PCs actually produce."""
    if isinstance(exc, PermissionError):
        return ("Windows refused to write a file (" + str(exc) + "). If the game is running, "
                "close it first; otherwise check that your antivirus isn't blocking "
                "OctopathWorldOverhaul.exe.")
    return str(exc) or exc.__class__.__name__


def prepare(argv, wrap):
    """Pick the save and build. -> True to start the game, False to stop, None = cancelled."""
    import config
    import steam_setup
    import build_difficulty_mod as B
    # applied now, not just loaded: the save picker shows each save's world danger
    cfg = config.apply(config.load())
    if wrap is None and steam_setup.game_running():
        print("The game is already running.")
        return False
    paths.base_pak()                                     # fails early if the game isn't found
    first_run = not os.path.exists(os.path.join(paths.user_dir(), SETUP_MARK))
    if first_run and wrap is None and "--build" not in argv and "--newest" not in argv:
        setup_dialog()
    saves = paths.find_saves()
    if not saves:
        print("No saves yet - building for a new game (the opening chapters play as vanilla).")
        save = B.NEW_GAME
    elif cfg["save_choice"] == "newest" or "--newest" in argv:
        save = max(saves, key=os.path.getmtime)
    else:
        save = pick_save(saves, cfg["ask_timeout"])
        if save is None:
            print("Cancelled.")
            return None
    update(save)
    return "--build" not in argv


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]) or 0)
