"""Build the release folder and zip: dist\\OrsterraUnbound\\ and dist\\OrsterraUnbound-<version>.zip

No PyInstaller: a one-file PyInstaller exe is a loader plus a packed archive, the same shape
as Python malware, so some antivirus tools flag it. The release is instead

  OctopathWorldOverhaul.exe   a few-KB launcher compiled from launcher\\*.cs with Windows'
                              own C# compiler; runs runtime\\pythonw.exe app\\launch_octopath.py
  runtime\\                    the official python.org runtime (signed by the PSF), trimmed:
                              the interpreter, the DLLs the mod uses, a zipped standard library
                              and Tcl/Tk for the windows
  app\\                        the mod's source, as plain .py files
  data\\  README.md  LICENSE  CHANGELOG.md

Run with the same Python version the runtime should be (the one on PATH):
  python dev/package_release.py
"""
import glob
import importlib._bootstrap_external
import os
import shutil
import subprocess
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
import version  # noqa: E402

PY = sys.base_prefix
TAG = f"python{sys.version_info.major}{sys.version_info.minor}"
CSC = os.path.join(os.environ.get("WINDIR", r"C:\Windows"),
                   r"Microsoft.NET\Framework64\v4.0.30319\csc.exe")

# interpreter files (signed by the Python Software Foundation)
CORE = ["pythonw.exe", "python.exe", f"{TAG}.dll", "python3.dll", "vcruntime140.dll",
        "vcruntime140_1.dll", "LICENSE.txt"]
# extension modules the mod doesn't need (tests, networking, crypto, databases)
SKIP_DLLS = ("_test", "_ctypes_test", "_ssl", "_hashlib", "libssl", "libcrypto", "sqlite3", "_sqlite3",
             "_remote_debugging", "_socket", "select", "_overlapped", "_asyncio",
             "_multiprocessing", "_wmi")
# standard-library packages the mod doesn't need
SKIP_LIB = {"site-packages", "test", "idlelib", "ensurepip", "turtledemo", "lib2to3",
            "pydoc_data", "venv", "__phello__", "sqlite3", "asyncio", "email", "http",
            "xmlrpc", "unittest", "multiprocessing", "concurrent", "wsgiref", "xml",
            "urllib", "html", "curses", "dbm", "ctypes/test", "tkinter/test", "_pyrepl",
            "zoneinfo", "tomllib", "turtle.py", "pydoc.py", "doctest.py", "mailbox.py",
            "imaplib.py", "smtplib.py", "ftplib.py", "poplib.py", "ssl.py", "socketserver.py",
            "__pycache__"}
# Tcl/Tk parts the windows don't need
KEEP_TCL = ("tcl8", "tcl8.6", "tk8.6")
SKIP_TCL = {"demos", "tzdata", "msgs", "images", "http1.0", "opt0.4"}


def copy_runtime(dst):
    os.makedirs(dst)
    for f in CORE:
        shutil.copy2(os.path.join(PY, f), dst)
    for f in glob.glob(os.path.join(PY, "DLLs", "*")):
        name = os.path.basename(f)
        if name.lower().endswith((".pyd", ".dll")) and not name.startswith(SKIP_DLLS):
            shutil.copy2(f, dst)
    for d in KEEP_TCL:
        shutil.copytree(os.path.join(PY, "tcl", d), os.path.join(dst, "tcl", d),
                        ignore=lambda _d, names: [n for n in names if n in SKIP_TCL])
    lib = os.path.join(PY, "Lib")
    with zipfile.ZipFile(os.path.join(dst, f"{TAG}.zip"), "w", zipfile.ZIP_DEFLATED) as z:
        for dirpath, dirs, files in os.walk(lib):
            rel = os.path.relpath(dirpath, lib).replace(os.sep, "/")
            dirs[:] = sorted(d for d in dirs if d not in SKIP_LIB
                             and (rel == "." and d or f"{rel}/{d}") not in SKIP_LIB)
            for f in sorted(files):
                if not f.endswith(".py") or rel == "." and f in SKIP_LIB:
                    continue
                arc = f if rel == "." else f"{rel}/{f}"
                with open(os.path.join(dirpath, f), "rb") as fh:
                    src = fh.read()
                # sourceless .pyc: zipimport loads it without a .py to check against
                code = compile(src, arc, "exec", dont_inherit=True)
                z.writestr(arc + "c", importlib._bootstrap_external._code_to_timestamp_pyc(
                    code, 0, len(src)))
    # the ._pth file pins sys.path to these entries (no user site-packages, no PYTHONPATH)
    with open(os.path.join(dst, f"{TAG}._pth"), "w") as f:
        f.write(f"{TAG}.zip\n.\n..\\app\n")


def compile_launcher(dst):
    src = os.path.join(ROOT, "launcher", "OctopathWorldOverhaul.cs")
    out = os.path.join(dst, "OctopathWorldOverhaul.exe")
    subprocess.run([CSC, "/nologo", "/target:winexe", "/optimize+", "/platform:anycpu",
                    "/reference:System.Windows.Forms.dll", f"/out:{out}", src], check=True)


def main():
    dist = os.path.join(ROOT, "dist")
    out = os.path.join(dist, "OrsterraUnbound")
    if os.path.exists(out):
        shutil.rmtree(out)
    os.makedirs(out)
    compile_launcher(out)
    copy_runtime(os.path.join(out, "runtime"))
    app = os.path.join(out, "app")
    os.makedirs(app)
    for f in glob.glob(os.path.join(ROOT, "src", "*.py")):
        shutil.copy2(f, app)
    os.makedirs(os.path.join(out, "data"))
    shutil.copy2(os.path.join(ROOT, "src", "data", "item_registry.json"),
                 os.path.join(out, "data"))
    for f in ("README.md", "LICENSE", "CHANGELOG.md"):
        shutil.copy2(os.path.join(ROOT, f), out)

    zpath = os.path.join(dist, f"OrsterraUnbound-{version.VERSION}.zip")
    if os.path.exists(zpath):
        os.remove(zpath)
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for dirpath, _dirs, files in os.walk(out):
            for f in files:
                full = os.path.join(dirpath, f)
                z.write(full, os.path.relpath(full, out))
    print(f"built {zpath} ({os.path.getsize(zpath) / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
