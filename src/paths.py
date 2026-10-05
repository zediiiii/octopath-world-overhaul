"""Where everything lives, detected on whatever PC this runs on.

Nothing here is specific to one machine: the game is found through Steam's registry entry
and library folders, saves through Windows' real Documents folder (which OneDrive may have
moved), and every path can be overridden in overhaul.ini.
"""
import ctypes
import glob
import os
import re
import sys

APP_ID = "921570"
GAME_FOLDER = "OCTOPATH TRAVELER"
BASE_PAK_REL = "Octopath_Traveler/Content/Paks/Octopath_Traveler-WindowsNoEditor.pak"
MODS_REL = "Octopath_Traveler/Content/Paks/~mods"

# overrides set from overhaul.ini by config.apply()
OVERRIDES = {"game_dir": "", "save_dir": ""}


def app_dir():
    """Folder of the exe (frozen) or the repo root (running from source)."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def data_dir():
    """Shipped data (item_registry.json). Next to the exe, or src/data from source."""
    if getattr(sys, "frozen", False):
        return os.path.join(app_dir(), "data")
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")


def _writable(d):
    try:
        os.makedirs(d, exist_ok=True)
        probe = os.path.join(d, ".write_test")
        with open(probe, "w") as f:
            f.write("x")
        os.remove(probe)
        return True
    except OSError:
        return False


def user_dir():
    """Writable folder for logs and the build stamp: next to the app if possible."""
    d = app_dir()
    if _writable(os.path.join(d, "logs")):
        return d
    alt = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
                       "OctopathWorldOverhaul")
    os.makedirs(alt, exist_ok=True)
    return alt


def log_dir():
    d = os.path.join(user_dir(), "logs")
    os.makedirs(d, exist_ok=True)
    return d


# ------------------------------------------------------------------ Steam / game
def steam_dir():
    try:
        import winreg
        for hive, key, val in ((winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam", "SteamPath"),
                               (winreg.HKEY_LOCAL_MACHINE,
                                r"SOFTWARE\WOW6432Node\Valve\Steam", "InstallPath"),
                               (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Valve\Steam",
                                "InstallPath")):
            try:
                with winreg.OpenKey(hive, key) as k:
                    v = winreg.QueryValueEx(k, val)[0]
                    if v and os.path.isdir(v):
                        return os.path.normpath(v)
            except OSError:
                continue
    except ImportError:
        pass
    for guess in (r"C:\Program Files (x86)\Steam", r"C:\Program Files\Steam"):
        if os.path.isdir(guess):
            return guess
    return None


def steam_libraries():
    sd = steam_dir()
    libs = [sd] if sd else []
    if sd:
        vdf = os.path.join(sd, "steamapps", "libraryfolders.vdf")
        if os.path.exists(vdf):
            with open(vdf, encoding="utf-8", errors="replace") as f:
                for m in re.finditer(r'"path"\s+"([^"]+)"', f.read()):
                    p = m.group(1).replace("\\\\", "\\")
                    if os.path.isdir(p) and p not in libs:
                        libs.append(p)
    return libs


def game_dir():
    if OVERRIDES.get("game_dir"):
        d = OVERRIDES["game_dir"]
        if not os.path.exists(os.path.join(d, BASE_PAK_REL)):
            raise RuntimeError(f"game_dir in overhaul.ini is {d}, but the game isn't there: "
                               "point it at the folder that contains Octopath_Traveler.exe, "
                               "or leave it empty to find the game through Steam.")
        return d
    for lib in steam_libraries():
        d = os.path.join(lib, "steamapps", "common", GAME_FOLDER)
        if os.path.exists(os.path.join(d, BASE_PAK_REL)):
            return d
    raise RuntimeError("Could not find OCTOPATH TRAVELER in any Steam library. Set game_dir "
                       "in overhaul.ini to the folder that contains Octopath_Traveler.exe.")


def base_pak():
    return os.path.join(game_dir(), BASE_PAK_REL)


def mods_dir():
    d = os.path.join(game_dir(), MODS_REL)
    os.makedirs(d, exist_ok=True)
    return d


def game_exe():
    return os.path.join(game_dir(), "Octopath_Traveler.exe")


# ------------------------------------------------------------------ saves
def documents_dir():
    try:
        buf = ctypes.create_unicode_buffer(260)
        if ctypes.windll.shell32.SHGetFolderPathW(None, 5, None, 0, buf) == 0:   # CSIDL_PERSONAL
            return buf.value
    except Exception:                                   # noqa: BLE001
        pass
    return os.path.join(os.path.expanduser("~"), "Documents")


def save_roots():
    """Every SaveGames folder (one per Steam account that has played)."""
    if OVERRIDES.get("save_dir"):
        return [OVERRIDES["save_dir"]]
    base = os.path.join(documents_dir(), "My Games", "Octopath_Traveler")
    return sorted(glob.glob(os.path.join(base, "*", "SaveGames")))


def find_saves():
    out = []
    for root in save_roots():
        out += [p for p in glob.glob(os.path.join(root, "SaveData*.sav"))]
    return out


def steam_userdata_configs():
    """localconfig.vdf of every Steam account on this PC."""
    sd = steam_dir()
    if not sd:
        return []
    return glob.glob(os.path.join(sd, "userdata", "*", "config", "localconfig.vdf"))
