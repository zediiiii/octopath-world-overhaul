"""Octopath Traveler nut respec tool (tkinter UI)."""
import os
import subprocess
import tkinter as tk
from tkinter import ttk, messagebox

import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
import respec_core as rc

HERE = os.path.dirname(os.path.abspath(__file__))
BACKUP_DIR = os.path.join(HERE, "backups")


def game_running():
    try:
        out = subprocess.run(["tasklist"], capture_output=True, text=True,
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout
        return "octopath_traveler" in out.lower()
    except Exception:
        return False


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Octopath Traveler — Nut Respec")
        self.resizable(False, False)
        self.editor = None
        self.vars = {}      # (cid, key) -> IntVar
        self.pool_labels = {}

        top = ttk.Frame(self, padding=8)
        top.pack(fill="x")
        ttk.Label(top, text="Save:").pack(side="left")
        self.saves = rc.find_saves()
        self.slot_var = tk.StringVar()
        labels = [f"{os.path.basename(p):<16} {rc.slot_summary(p)}" for p in self.saves]
        self.combo = ttk.Combobox(top, textvariable=self.slot_var, values=labels,
                                  width=70, state="readonly", font=("Consolas", 9))
        self.combo.pack(side="left", padx=4)
        self.combo.bind("<<ComboboxSelected>>", lambda e: self.load())

        self.warn = ttk.Label(self, foreground="#b00", padding=(8, 0))
        self.warn.pack(fill="x")

        self.grid_frame = ttk.Frame(self, padding=8)
        self.grid_frame.pack()

        btns = ttk.Frame(self, padding=8)
        btns.pack(fill="x")
        ttk.Button(btns, text="Refund all (set everyone to 0)", command=self.refund_all).pack(side="left")
        ttk.Button(btns, text="Revert changes", command=self.load).pack(side="left", padx=6)
        ttk.Button(btns, text="Write save", command=self.write).pack(side="right")

        ttk.Label(self, padding=(8, 0, 8, 8), foreground="#555", justify="left", text=(
            "Each cell = permanent bonus from nuts. Points are pooled per stat across the whole party.\n"
            "'Unassigned' points are put back in your bag as nuts (largest sizes first) when you write.\n"
            "Nuts already in your bag count toward the pool, so you can assign them here directly too.\n"
            "A backup is made in the 'backups' folder before every write. Close the game (or be on the title screen) first."
        )).pack(fill="x")

        self.check_game()
        if self.saves:
            newest = max(range(len(self.saves)), key=lambda i: os.path.getmtime(self.saves[i]))
            self.combo.current(newest)
            self.load()

    def check_game(self):
        self.warn.config(text="⚠ Octopath Traveler is running — quit to title screen (or close it) "
                              "before writing, then load the save." if game_running() else "")
        self.after(5000, self.check_game)

    def current_path(self):
        i = self.combo.current()
        return self.saves[i] if i >= 0 else None

    def load(self):
        path = self.current_path()
        if not path:
            return
        try:
            self.editor = rc.SaveEditor(path)
        except Exception as e:
            messagebox.showerror("Load failed", str(e))
            return
        self.build_grid()

    def build_grid(self):
        for w in self.grid_frame.winfo_children():
            w.destroy()
        self.vars.clear()
        self.pool_labels.clear()
        ed = self.editor
        g = self.grid_frame
        ttk.Label(g, text="Character", font=("Segoe UI", 9, "bold")).grid(row=0, column=0, sticky="w", padx=4)
        for j, (label, key, nut, sizes) in enumerate(rc.STATS, start=1):
            ttk.Label(g, text=label, font=("Segoe UI", 9, "bold")).grid(row=0, column=j, padx=3)
            ttk.Label(g, text=f"step {sizes[0][1]}", foreground="#777").grid(row=1, column=j)
        r = 2
        for cid, name, lvl, _ in ed.chars:
            ttk.Label(g, text=f"{name}  (Lv {lvl})").grid(row=r, column=0, sticky="w", padx=4, pady=1)
            for j, (label, key, nut, sizes) in enumerate(rc.STATS, start=1):
                v = tk.IntVar(value=ed.doping(cid, key))
                v.trace_add("write", lambda *a: self.update_pool())
                self.vars[(cid, key)] = v
                sb = ttk.Spinbox(g, from_=0, to=99999, increment=sizes[0][1], textvariable=v, width=7,
                                 justify="right")
                sb.grid(row=r, column=j, padx=2, pady=1)
            r += 1
        ttk.Separator(g).grid(row=r, column=0, columnspan=len(rc.STATS) + 1, sticky="ew", pady=4)
        r += 1
        ttk.Label(g, text="Unassigned → nuts", font=("Segoe UI", 9, "bold")).grid(row=r, column=0, sticky="w", padx=4)
        ttk.Label(g, text="Total pool", foreground="#555").grid(row=r + 1, column=0, sticky="w", padx=4)
        ttk.Label(g, text="Nuts in bag now", foreground="#555").grid(row=r + 2, column=0, sticky="w", padx=4)
        for j, (label, key, nut, sizes) in enumerate(rc.STATS, start=1):
            lb = ttk.Label(g, font=("Segoe UI", 9, "bold"))
            lb.grid(row=r, column=j)
            self.pool_labels[key] = lb
            ttk.Label(g, text=str(ed.total_points(key)), foreground="#555").grid(row=r + 1, column=j)
            bag = "/".join(str(ed.item_count(i)) for i, _ in sizes)
            ttk.Label(g, text=bag, foreground="#555").grid(row=r + 2, column=j)
        ttk.Label(g, text="(bag shown as S/M/L counts)", foreground="#777").grid(
            row=r + 3, column=1, columnspan=4, sticky="w")
        self.update_pool()

    def alloc(self):
        out = {}
        for (cid, key), v in self.vars.items():
            try:
                val = int(v.get())
            except (tk.TclError, ValueError):
                val = None
            out.setdefault(cid, {})[key] = val
        return out

    def update_pool(self):
        if not self.editor:
            return
        a = self.alloc()
        for label, key, nut, sizes in rc.STATS:
            vals = [a[c[0]][key] for c in self.editor.chars]
            lb = self.pool_labels.get(key)
            if lb is None:
                continue
            if any(x is None or x < 0 for x in vals):
                lb.config(text="?", foreground="#b00")
                continue
            left = self.editor.total_points(key) - sum(vals)
            bad = left < 0 or left % sizes[0][1] != 0
            lb.config(text=str(left), foreground="#b00" if bad else ("#070" if left else "#000"))

    def refund_all(self):
        for v in self.vars.values():
            v.set(0)

    def write(self):
        if not self.editor:
            return
        a = self.alloc()
        if any(x is None or x < 0 for d in a.values() for x in d.values()):
            messagebox.showerror("Invalid", "All cells must be whole numbers ≥ 0.")
            return
        if game_running() and not messagebox.askyesno(
                "Game is running",
                "Octopath Traveler is running. Only continue if you're on the title screen "
                "(the game could otherwise overwrite this slot). Continue?"):
            return
        try:
            plan = self.editor.apply(a)
            bak = self.editor.write(BACKUP_DIR)
        except Exception as e:
            messagebox.showerror("Could not write", str(e))
            self.load()
            return
        lines = []
        for key, nuts in plan.items():
            stat = rc.STATS[rc.STAT_KEYS.index(key)]
            names = {stat[3][0][0]: "", stat[3][1][0]: " (M)", stat[3][2][0]: " (L)"}
            parts = [f"{n}× {stat[2]}{names[i]}" for i, n in nuts.items() if n]
            lines.append(f"{stat[0]}: " + (", ".join(parts) if parts else "none"))
        messagebox.showinfo("Saved", "Save written.\nBackup: " + bak +
                            ("\n\nNuts now in bag for changed stats:\n" + "\n".join(lines) if lines else ""))
        self.combo.config(values=[f"{os.path.basename(p):<16} {rc.slot_summary(p)}" for p in self.saves])
        self.load()


if __name__ == "__main__":
    App().mainloop()
