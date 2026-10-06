"""Hook Steam's Play button (Library and Big Picture) and a desktop shortcut to the launcher.

Steam's per-game Launch Options are set to  "<launcher>" --wrap %command%  for Octopath
Traveler (app 921570) in every Steam account on this PC that has the game. Steam rewrites
localconfig.vdf when it exits, so Steam is shut down first and started again afterwards.
Every file is backed up before it is changed; remove() undoes it.
"""
import os
import re
import shutil
import subprocess
import sys
import time

import paths

APP = paths.APP_ID


def launcher_command():
    """How Steam should start us: pythonw.exe (the release's bundled one, or the
    installed one from source) running launch_octopath.py."""
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}" --wrap %command%'
    pyw = sys.executable
    if os.path.basename(pyw).lower() == "python.exe":
        cand = os.path.join(os.path.dirname(pyw), "pythonw.exe")
        pyw = cand if os.path.exists(cand) else pyw
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "launch_octopath.py")
    return f'"{pyw}" "{script}" --wrap %command%'


def _vdf_escape(s):
    return s.replace("\\", "\\\\").replace('"', '\\"')


def _app_block(text):
    """(start, end, indent) of the per-app block that holds LastPlayed / Playtime."""
    for m in re.finditer(r'\n(\t+)"%s"\s*\n\1\{' % APP, text):
        indent = m.group(1)
        end = text.index("\n" + indent + "}", m.end())
        body = text[m.end():end]
        if '"LastPlayed"' in body or '"Playtime"' in body:
            return m.end(), end, indent
    return None


def steam_running():
    # CREATE_NO_WINDOW: no console flash from the windowless launcher
    out = subprocess.run(["tasklist"], capture_output=True, text=True,
                         creationflags=0x08000000).stdout.lower()
    return "steam.exe" in out


def game_running():
    # CREATE_NO_WINDOW: no console flash from the windowless launcher
    out = subprocess.run(["tasklist"], capture_output=True, text=True,
                         creationflags=0x08000000).stdout.lower()
    return "octopath_traveler" in out


def stop_steam(timeout=120):
    exe = os.path.join(paths.steam_dir() or "", "steam.exe")
    if not steam_running():
        return True
    subprocess.Popen([exe, "-shutdown"])
    t = time.time()
    while steam_running() and time.time() - t < timeout:
        time.sleep(2)
    time.sleep(2)
    return not steam_running()


def start_steam():
    exe = os.path.join(paths.steam_dir() or "", "steam.exe")
    if os.path.exists(exe):
        subprocess.Popen([exe])


def _edit(remove, log=print):
    """Edit every account's localconfig.vdf. Steam must not be running."""
    done = 0
    for cfg in paths.steam_userdata_configs():
        with open(cfg, encoding="utf-8") as f:
            text = f.read()
        blk = _app_block(text)
        if not blk:
            continue                     # this account has never launched the game
        start, end, indent = blk
        body = re.sub(r'\n\t+"LaunchOptions"\t\t"(?:[^"\\]|\\.)*"', "", text[start:end])
        if not remove:
            body = f'\n{indent}\t"LaunchOptions"\t\t"{_vdf_escape(launcher_command())}"' + body
        new = text[:start] + body + text[end:]
        if new != text:
            backup = os.path.join(paths.user_dir(), "backups",
                                  f"localconfig.{os.path.basename(os.path.dirname(os.path.dirname(cfg)))}"
                                  f".{int(time.time())}.vdf")
            os.makedirs(os.path.dirname(backup), exist_ok=True)
            shutil.copyfile(cfg, backup)
            with open(cfg, "w", encoding="utf-8", newline="") as f:
                f.write(new)
            log(f"{'removed from' if remove else 'set in'} {cfg} (backup {backup})")
        done += 1
    return done


def configure_steam(remove=False, log=print):
    """Shut Steam down, set (or remove) the launch options, start Steam again."""
    if game_running():
        raise RuntimeError("Close the game first.")
    was_running = steam_running()
    if was_running and not stop_steam():
        raise RuntimeError("Steam did not close; try again with Steam closed.")
    try:
        n = _edit(remove, log)
    finally:
        if was_running:
            start_steam()
    if not n:
        log("No Steam account on this PC has launched Octopath Traveler yet - launch it "
            "once from Steam, then run setup again.")
    return n


def launch_options_set():
    for cfg in paths.steam_userdata_configs():
        with open(cfg, encoding="utf-8") as f:
            text = f.read()
        blk = _app_block(text)
        if blk and "launch_octopath" in text[blk[0]:blk[1]].lower() or \
                (blk and "octopathworldoverhaul" in text[blk[0]:blk[1]].lower()):
            return True
    return False


def hook_outdated():
    """True if Steam runs an Orsterra launcher, but not this one (e.g. the exe of an older
    version, or the release folder moved)."""
    want = _vdf_escape(launcher_command()).lower()
    for cfg in paths.steam_userdata_configs():
        with open(cfg, encoding="utf-8") as f:
            text = f.read()
        blk = _app_block(text)
        if not blk:
            continue
        body = text[blk[0]:blk[1]].lower()
        if ("launch_octopath" in body or "octopathworldoverhaul" in body) and want not in body:
            return True
    return False


def create_shortcut(name="Octopath Traveler (Orsterra Unbound)"):
    """Desktop shortcut that runs the launcher, with the game's icon."""
    import ctypes
    buf = ctypes.create_unicode_buffer(260)
    ctypes.windll.shell32.SHGetFolderPathW(None, 0x10, None, 0, buf)     # CSIDL_DESKTOPDIRECTORY
    lnk = os.path.join(buf.value, name + ".lnk")
    if getattr(sys, "frozen", False):
        target, args = sys.executable, ""
    else:
        target = sys.executable
        args = f'"{os.path.join(os.path.dirname(os.path.abspath(__file__)), "launch_octopath.py")}"'
    try:
        icon = paths.game_exe() + ",0"
    except RuntimeError:
        icon = target + ",0"
    ps = (f"$s=(New-Object -ComObject WScript.Shell).CreateShortcut('{lnk}');"
          f"$s.TargetPath='{target}';$s.Arguments='{args}';"
          f"$s.WorkingDirectory='{os.path.dirname(target)}';$s.IconLocation='{icon}';"
          f"$s.Description='Octopath Traveler with the World Overhaul (rebuilds for your save, "
          f"then starts the game)';$s.Save()")
    subprocess.run(["powershell", "-NoProfile", "-Command", ps], check=True,
                   capture_output=True)
    return lnk
