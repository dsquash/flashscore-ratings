#!/usr/bin/env python3
"""
launcher.py — Flashscore Ratings UI
=====================================
Double-click launcher.py  or:  python launcher.py
"""

import tkinter as tk
from tkinter import ttk, scrolledtext
import subprocess
import threading
import re
import sys
import json
from pathlib import Path

BASE_DIR  = Path(__file__).parent
LAST_URL  = BASE_DIR / "flashscore_output" / "last_url.txt"
RUN_PY    = BASE_DIR / "run.py"
OVERRIDES = BASE_DIR / "sofifa_overrides.json"

# ── Platform-aware fonts ──────────────────────────────────────────
# UI_FONT / MONO_FONT are Windows-only — fall back to the right
# native family per OS so the UI doesn't look broken on Mac/Linux.
if sys.platform == "darwin":
    UI_FONT   = "Helvetica Neue"   # matches macOS system UI
    MONO_FONT = "Menlo"            # default macOS monospace
elif sys.platform.startswith("win"):
    UI_FONT   = "Segoe UI"
    MONO_FONT = "Consolas"
else:
    UI_FONT   = "DejaVu Sans"
    MONO_FONT = "DejaVu Sans Mono"

# ── Colors ────────────────────────────────────────────────────────
BG        = "#1a1d24"
BG2       = "#23273a"
ACCENT    = "#4f8ef7"
BTN_GREEN = "#27ae60"
BTN_BLUE  = "#2980b9"
BTN_GRAY  = "#3d4255"
FG        = "#e8eaf0"
FG_DIM    = "#7a8099"
RED       = "#e74c3c"
YELLOW    = "#f1c40f"

# ── macOS Aqua fix ────────────────────────────────────────────────
# On macOS, tk.Button ignores bg/fg (native Aqua renderer). Patch the
# widget classes so every Button/Radiobutton auto-sets highlightbackground
# to the window BG — this removes the default gray halo and lets the
# dark theme blend in. Colors on the button face itself still fall back
# to native (Mac limitation), but the UI looks far less broken.
if sys.platform == "darwin":
    _OrigButton = tk.Button
    _OrigRadiobutton = tk.Radiobutton

    class _MacButton(_OrigButton):
        def __init__(self, master=None, **kw):
            kw.setdefault("highlightbackground", BG)
            super().__init__(master, **kw)

    class _MacRadiobutton(_OrigRadiobutton):
        def __init__(self, master=None, **kw):
            kw.setdefault("highlightbackground", BG)
            super().__init__(master, **kw)

    tk.Button = _MacButton
    tk.Radiobutton = _MacRadiobutton


def read_last_url():
    try:
        return LAST_URL.read_text(encoding="utf-8").strip()
    except Exception:
        return ""


def read_match_type():
    try:
        content = RUN_PY.read_text(encoding="utf-8")
        m = re.search(r'^MATCH_TYPE\s*=\s*["\']([^"\']+)["\']', content, re.MULTILINE)
        return m.group(1) if m else "club"
    except Exception:
        return "club"


def write_match_type(match_type: str):
    try:
        content = RUN_PY.read_text(encoding="utf-8")
        updated = re.sub(
            r'^MATCH_TYPE\s*=\s*["\'][^"\']*["\']',
            f'MATCH_TYPE = "{match_type}"',
            content, flags=re.MULTILINE
        )
        RUN_PY.write_text(updated, encoding="utf-8")
    except Exception:
        pass


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Flashscore Ratings")
        self.configure(bg=BG)
        self.resizable(True, True)
        # Mac widgets render a touch larger — give the window more room
        if sys.platform == "darwin":
            self.minsize(720, 560)
            self.geometry("760x620")
        else:
            self.minsize(580, 500)

        self._proc            = None
        self._running         = False
        self._missing_players = []
        self._update_banner   = None   # reference to update banner frame

        self._build_ui()
        self._load_state()
        # Check for updates silently in background
        threading.Thread(target=self._bg_update_check, daemon=True).start()

    # ── UI Construction ───────────────────────────────────────────

    def _build_ui(self):
        # ── Header ────────────────────────────────────────────────
        hdr = tk.Frame(self, bg=BG, pady=12)
        hdr.pack(fill="x", padx=20)
        tk.Label(hdr, text="⚽  Flashscore Ratings", font=(UI_FONT, 16, "bold"),
                 bg=BG, fg=FG).pack(side="left")

        self.btn_check_update = tk.Button(
            hdr, text="⬆  Check for Updates",
            font=(UI_FONT, 8), bg=BTN_GRAY, fg=FG_DIM,
            relief="flat", cursor="hand2",
            activebackground="#4d5268", activeforeground=FG,
            command=self._check_update_manual, padx=8, pady=3
        )
        self.btn_check_update.pack(side="right")

        # ── URL ───────────────────────────────────────────────────
        url_frame = tk.Frame(self, bg=BG2, pady=14, padx=16)
        url_frame.pack(fill="x", padx=16, pady=(0, 8))

        tk.Label(url_frame, text="Flashscore URL", font=(UI_FONT, 9),
                 bg=BG2, fg=FG_DIM).pack(anchor="w")

        entry_row = tk.Frame(url_frame, bg=BG2)
        entry_row.pack(fill="x", pady=(4, 0))

        self.url_var = tk.StringVar()
        self.url_entry = tk.Entry(
            entry_row, textvariable=self.url_var,
            font=(UI_FONT, 10), bg="#2d3147", fg=FG,
            insertbackground=FG, relief="flat",
            highlightthickness=1, highlightbackground="#3d4255",
            highlightcolor=ACCENT
        )
        self.url_entry.pack(side="left", fill="x", expand=True, ipady=6)

        btn_paste = tk.Button(
            entry_row, text="📋 Paste", font=(UI_FONT, 9),
            bg=BTN_GRAY, fg=FG, relief="flat", cursor="hand2",
            activebackground="#4d5268", activeforeground=FG,
            command=self._paste_url, padx=10
        )
        btn_paste.pack(side="left", padx=(6, 0))

        btn_clear = tk.Button(
            entry_row, text="✕", font=(UI_FONT, 9),
            bg=BTN_GRAY, fg=FG_DIM, relief="flat", cursor="hand2",
            activebackground="#4d5268", activeforeground=FG,
            command=lambda: self.url_var.set(""), padx=8
        )
        btn_clear.pack(side="left", padx=(4, 0))

        # ── Match type ────────────────────────────────────────────
        type_frame = tk.Frame(self, bg=BG, pady=4)
        type_frame.pack(fill="x", padx=20)

        tk.Label(type_frame, text="Match type:", font=(UI_FONT, 10),
                 bg=BG, fg=FG_DIM).pack(side="left", padx=(0, 12))

        self.match_type = tk.StringVar(value="club")

        rb_style = dict(bg=BG, fg=FG, selectcolor=BG2, activebackground=BG,
                        activeforeground=FG, font=(UI_FONT, 10),
                        relief="flat", cursor="hand2")
        tk.Radiobutton(type_frame, text="Club",
                       variable=self.match_type, value="club",
                       command=self._on_type_change, **rb_style).pack(side="left")
        tk.Radiobutton(type_frame, text="National team",
                       variable=self.match_type, value="national",
                       command=self._on_type_change, **rb_style).pack(side="left", padx=(12, 0))

        # ── Action buttons ────────────────────────────────────────
        btn_frame = tk.Frame(self, bg=BG, pady=8)
        btn_frame.pack(fill="x", padx=16)

        self.btn_run = tk.Button(
            btn_frame, text="▶  Full Run",
            font=(UI_FONT, 11, "bold"),
            bg=BTN_GREEN, fg="white", relief="flat", cursor="hand2",
            activebackground="#2ecc71", activeforeground="white",
            command=self._run_full, padx=20, pady=8
        )
        self.btn_run.pack(side="left", padx=(0, 8))

        self.btn_refresh = tk.Button(
            btn_frame, text="↻  Refresh Stats",
            font=(UI_FONT, 11),
            bg=BTN_BLUE, fg="white", relief="flat", cursor="hand2",
            activebackground="#3498db", activeforeground="white",
            command=self._run_refresh, padx=20, pady=8
        )
        self.btn_refresh.pack(side="left", padx=(0, 8))

        self.btn_redownload = tk.Button(
            btn_frame, text="⬇  Re-download overrides",
            font=(UI_FONT, 10),
            bg="#2a3050", fg="#a0b0ff", relief="flat", cursor="hand2",
            activebackground="#3a4060", activeforeground="#c0d0ff",
            command=self._run_redownload, padx=14, pady=8
        )
        self.btn_redownload.pack(side="left")

        self.btn_stop = tk.Button(
            btn_frame, text="■  Stop",
            font=(UI_FONT, 10),
            bg=BTN_GRAY, fg=FG_DIM, relief="flat", cursor="hand2",
            activebackground="#4d5268", activeforeground=FG,
            command=self._stop, padx=14, pady=8,
            state="disabled"
        )
        self.btn_stop.pack(side="right")

        self.btn_reset = tk.Button(
            btn_frame, text="🗑  Reset",
            font=(UI_FONT, 10),
            bg="#5a2020", fg="#ff8080", relief="flat", cursor="hand2",
            activebackground="#7a2828", activeforeground="#ffaaaa",
            command=self._confirm_reset, padx=14, pady=8
        )
        self.btn_reset.pack(side="right", padx=(0, 8))

        tk.Button(
            btn_frame, text="✏  Overrides",
            font=(UI_FONT, 10),
            bg="#2a3a2a", fg="#7ecb7e", relief="flat", cursor="hand2",
            activebackground="#3a4a3a", activeforeground="#a0e0a0",
            command=self._open_overrides, padx=14, pady=8
        ).pack(side="right", padx=(0, 6))

        # ── Status bar ────────────────────────────────────────────
        self.status_var = tk.StringVar(value="Ready.")
        status_bar = tk.Label(
            self, textvariable=self.status_var,
            font=(UI_FONT, 9), bg=BG2, fg=FG_DIM,
            anchor="w", padx=12, pady=4
        )
        status_bar.pack(fill="x", padx=16, pady=(4, 0))

        # ── Log output ────────────────────────────────────────────
        log_frame = tk.Frame(self, bg=BG, pady=4)
        log_frame.pack(fill="both", expand=True, padx=16, pady=(4, 12))

        log_header = tk.Frame(log_frame, bg=BG)
        log_header.pack(fill="x")
        tk.Label(log_header, text="Output", font=(UI_FONT, 9),
                 bg=BG, fg=FG_DIM).pack(side="left")
        tk.Button(log_header, text="Clear log", font=(UI_FONT, 8),
                  bg=BTN_GRAY, fg=FG_DIM, relief="flat", cursor="hand2",
                  activebackground="#4d5268", activeforeground=FG,
                  command=self._clear_log, padx=8, pady=1
                  ).pack(side="right")

        self.log = scrolledtext.ScrolledText(
            log_frame, font=(MONO_FONT, 9),
            bg="#12141c", fg="#c8d0e0",
            insertbackground=FG, relief="flat",
            wrap="word", state="disabled"
        )
        self.log.pack(fill="both", expand=True, pady=(4, 0))

        # ── Footer ────────────────────────────────────────────────
        tk.Label(
            self, text="Marian Grosu  ·  Flashscore Ratings",
            font=(UI_FONT, 8), bg=BG, fg=FG_DIM,
            anchor="center"
        ).pack(fill="x", pady=(4, 6))

        # Log color tags
        self.log.tag_config("ok",     foreground="#27ae60")
        self.log.tag_config("warn",   foreground=YELLOW)
        self.log.tag_config("err",    foreground=RED)
        self.log.tag_config("header", foreground=ACCENT)
        self.log.tag_config("dim",    foreground=FG_DIM)

        # ── Missing players banner ────────────────────────────────
        self.missing_frame = tk.Frame(self, bg="#2a1f10", pady=6)
        self.missing_label = tk.Label(
            self.missing_frame,
            text="", font=(UI_FONT, 9, "bold"),
            bg="#2a1f10", fg=YELLOW, anchor="w"
        )
        self.missing_label.pack(side="left", padx=(12, 8))
        tk.Button(
            self.missing_frame, text="→ Fill in overrides",
            font=(UI_FONT, 9, "bold"),
            bg="#c47c00", fg="white", relief="flat", cursor="hand2",
            activebackground="#e09000", activeforeground="white",
            command=self._open_overrides_for_missing, padx=10, pady=3
        ).pack(side="left")

    # ── State ─────────────────────────────────────────────────────

    def _load_state(self):
        url = read_last_url()
        if url:
            self.url_var.set(url)
        mt = read_match_type()
        self.match_type.set(mt)

    def _on_type_change(self):
        write_match_type(self.match_type.get())

    def _paste_url(self):
        try:
            text = self.clipboard_get()
            self.url_var.set(text.strip())
        except Exception:
            pass

    def _clear_log(self):
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")

    def _log(self, text: str):
        self.log.configure(state="normal")

        line = text.rstrip("\n")
        if any(x in line for x in ["✓", "OK", "Done", "Finished", "READY", "Updated"]):
            tag = "ok"
        elif any(x in line for x in ["⚠", "NOT FOUND", "ERROR", "Missing", "FAILED"]):
            tag = "warn" if "NOT FOUND" in line or "Missing" in line else "err"
        elif line.startswith("===") or line.startswith("[1/") or line.startswith("[2/") or line.startswith("[3/"):
            tag = "header"
        elif line.startswith("  ") and not line.strip().startswith("→"):
            tag = "dim"
        else:
            tag = None

        if tag:
            self.log.insert("end", text, tag)
        else:
            self.log.insert("end", text)

        self.log.see("end")
        self.log.configure(state="disabled")

    def _set_running(self, running: bool):
        self._running = running
        state_btns = "disabled" if running else "normal"
        state_stop = "normal"   if running else "disabled"
        self.btn_run.configure(state=state_btns)
        self.btn_refresh.configure(state=state_btns)
        self.btn_redownload.configure(state=state_btns)
        self.btn_reset.configure(state=state_btns)
        self.btn_stop.configure(state=state_stop)
        if not running:
            self.status_var.set("Ready.")

    # ── Reset ─────────────────────────────────────────────────────

    def _confirm_reset(self):
        import tkinter.messagebox as mb
        output_dir = BASE_DIR / "flashscore_output"
        if not output_dir.exists():
            self._log("ℹ Nothing to reset — flashscore_output does not exist.\n")
            return

        images_dir = output_dir / "images"
        n_images   = len(list(images_dir.glob("*.png"))) if images_dir.exists() else 0
        has_json   = (output_dir / "data.json").exists()

        msg = (
            f"The following will be deleted:\n"
            f"  • {n_images} images from flashscore_output/images/\n"
            f"  • data.json ({'exists' if has_json else 'not found'})\n"
            f"  • last_url.txt\n"
            f"  • debug files (debug.png, debug_testids.txt)\n\n"
            f"Continue?"
        )
        ok = mb.askyesno("Reset — are you sure?", msg, icon="warning")
        if ok:
            self._do_reset()

    def _do_reset(self):
        import shutil
        output_dir = BASE_DIR / "flashscore_output"
        deleted = []
        errors  = []

        images_dir = output_dir / "images"
        if images_dir.exists():
            try:
                shutil.rmtree(str(images_dir))
                images_dir.mkdir()
                deleted.append("images/ (all player photos)")
            except Exception as e:
                errors.append(f"images/: {e}")

        for fname in ["data.json", "last_url.txt", "placeholders.json",
                      "debug.png", "debug_testids.txt", "last_refresh_summary.txt"]:
            fpath = output_dir / fname
            if fpath.exists():
                try:
                    fpath.unlink()
                    deleted.append(fname)
                except Exception as e:
                    errors.append(f"{fname}: {e}")

        self._log("\n🗑  RESET\n")
        if deleted:
            for d in deleted:
                self._log(f"  ✓ Deleted: {d}\n")
        if errors:
            for e in errors:
                self._log(f"  ⚠ Error: {e}\n")
        self._log("  Done — you can now run Full Run for a new match.\n\n")
        self.status_var.set("Reset complete.")

    # ── Script runner ─────────────────────────────────────────────

    def _run_script(self, script: str, extra_args: list = None):
        url = self.url_var.get().strip()
        if not url and script == "run.py":
            self.status_var.set("⚠ Please enter the Flashscore URL!")
            self._log("⚠ Please enter the Flashscore URL!\n")
            return

        write_match_type(self.match_type.get())

        cmd = ["python", str(BASE_DIR / script)]
        if url and script == "run.py":
            cmd.append(url)
        if extra_args:
            cmd.extend(extra_args)

        label = "Full Run" if script == "run.py" else "Refresh Stats"
        self._log(f"\n{'─'*50}\n▶ {label}  [{self.match_type.get()}]\n{'─'*50}\n")
        self.status_var.set(f"Running: {label}...")
        self._set_running(True)

        is_refresh = (script == "refresh_stats.py")

        def worker():
            collected_missing = []
            try:
                import os
                env = os.environ.copy()
                env["PYTHONIOENCODING"] = "utf-8"
                self._proc = subprocess.Popen(
                    cmd, cwd=str(BASE_DIR),
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, encoding="utf-8", errors="replace",
                    bufsize=1, env=env
                )
                for line in self._proc.stdout:
                    self.after(0, self._log, line)
                    stripped = line.strip()
                    if stripped.startswith("Missing:"):
                        names_part = stripped[len("Missing:"):].strip()
                        collected_missing = [n.strip() for n in names_part.split(",") if n.strip()]

                self._proc.wait()
                rc  = self._proc.returncode
                msg = "✓ Finished." if rc == 0 else f"⚠ Exited with code {rc}."
                self.after(0, self._log, f"\n{msg}\n")
                self.after(0, self.status_var.set, msg)
                self.after(0, self._update_missing_banner, collected_missing)
                if is_refresh and rc == 0:
                    self.after(200, self._show_refresh_summary)
            except Exception as e:
                self.after(0, self._log, f"\nERROR: {e}\n")
                self.after(0, self.status_var.set, f"ERROR: {e}")
            finally:
                self._proc = None
                self.after(0, self._set_running, False)

        threading.Thread(target=worker, daemon=True).start()

    def _run_full(self):
        self._run_script("run.py")

    def _run_redownload(self):
        self._run_script("run.py", extra_args=["--images-only"])

    def _run_refresh(self):
        self._run_script("refresh_stats.py")

    # ── Refresh Stats summary popup ───────────────────────────────

    def _show_refresh_summary(self):
        summary_path = BASE_DIR / "flashscore_output" / "last_refresh_summary.txt"
        try:
            text = summary_path.read_text(encoding="utf-8").strip()
        except Exception:
            text = "Summary not available."

        win = tk.Toplevel(self)
        win.title("Refresh Stats — Summary")
        win.configure(bg=BG)
        win.resizable(False, False)
        win.grab_set()

        tk.Label(win, text="Refresh Stats", font=(UI_FONT, 13, "bold"),
                 bg=BG, fg=FG).pack(pady=(18, 4), padx=24)
        tk.Frame(win, bg="#2a3050", height=1).pack(fill="x", padx=20, pady=(0, 10))

        lines = text.splitlines()
        if lines:
            tk.Label(win, text=lines[0], font=(UI_FONT, 11, "bold"),
                     bg=BG, fg="#a0b0ff").pack(padx=24, pady=(0, 6))

        body = "\n".join(lines[2:]) if len(lines) > 2 else ""
        if body:
            color = "#f0c040" if not body.strip().startswith("No changes") else "#60d080"
            tk.Label(win, text=body, font=(UI_FONT, 10),
                     bg=BG, fg=color, justify="left", anchor="w").pack(
                padx=28, pady=(0, 12), fill="x")
        else:
            tk.Label(win, text="No changes detected.", font=(UI_FONT, 10),
                     bg=BG, fg="#60d080").pack(padx=24, pady=(0, 12))

        tk.Button(win, text="OK", font=(UI_FONT, 10, "bold"),
                  bg=BTN_BLUE, fg="white", relief="flat", cursor="hand2",
                  padx=28, pady=6, command=win.destroy).pack(pady=(0, 16))

        win.update_idletasks()
        x = self.winfo_x() + (self.winfo_width()  - win.winfo_width())  // 2
        y = self.winfo_y() + (self.winfo_height() - win.winfo_height()) // 2
        win.geometry(f"+{x}+{y}")

    # ── Missing players banner ────────────────────────────────────

    def _update_missing_banner(self, missing: list):
        self._missing_players = missing
        if missing:
            n = len(missing)
            self.missing_label.config(
                text=f"⚠  {n} player{'s' if n > 1 else ''} not found:  "
                     + ",  ".join(missing)
            )
            self.missing_frame.pack(fill="x", padx=16, pady=(0, 4),
                                    before=self.log.master)
        else:
            self.missing_frame.pack_forget()

    def _open_overrides_for_missing(self):
        self._open_overrides(prefill=self._missing_players)

    # ── Overrides window ──────────────────────────────────────────

    def _load_overrides(self) -> dict:
        if not OVERRIDES.exists():
            return {}
        try:
            with open(OVERRIDES, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _save_overrides(self, data: dict):
        with open(OVERRIDES, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _open_overrides(self, prefill: list = None):
        win = tk.Toplevel(self)
        win.title("SoFIFA Overrides")
        win.configure(bg=BG)
        win.geometry("660x520")
        win.resizable(True, True)
        win.grab_set()

        tk.Label(
            win,
            text="Manual mappings: Flashscore name  →  SoFIFA player page URL",
            font=(UI_FONT, 9), bg=BG, fg=FG_DIM
        ).pack(anchor="w", padx=14, pady=(10, 2))
        tk.Label(
            win,
            text="Example: 'Inacio'  →  https://sofifa.com/player/262622/samuele-inacio-pia/",
            font=(MONO_FONT, 8), bg=BG, fg="#555c7a"
        ).pack(anchor="w", padx=14, pady=(0, 4))

        prefill        = [p for p in (prefill or []) if p]
        pending_entries = []

        if prefill:
            overrides_now = self._load_overrides()
            to_fill = [p for p in prefill if p not in overrides_now]

            if to_fill:
                pf_outer = tk.Frame(win, bg=BG2, pady=8, padx=12)
                pf_outer.pack(fill="x", padx=14, pady=(0, 6))

                tk.Label(pf_outer,
                         text=f"⚠  {len(to_fill)} player(s) not found — paste their SoFIFA URL:",
                         font=(UI_FONT, 9, "bold"), bg=BG2, fg=YELLOW
                         ).pack(anchor="w", pady=(0, 6))

                for player_name in to_fill:
                    row = tk.Frame(pf_outer, bg=BG2)
                    row.pack(fill="x", pady=2)

                    name_var = tk.StringVar(value=player_name)
                    url_var  = tk.StringVar()

                    tk.Label(row, textvariable=name_var,
                             font=(UI_FONT, 10, "bold"), bg=BG2, fg=FG,
                             width=18, anchor="w").pack(side="left", padx=(0, 8))

                    url_entry = tk.Entry(row, textvariable=url_var,
                                         font=(UI_FONT, 9),
                                         bg="#2d3147", fg=FG, insertbackground=FG,
                                         relief="flat", highlightthickness=1,
                                         highlightbackground="#3d4255")
                    url_entry.pack(side="left", fill="x", expand=True, ipady=4)

                    def make_paste(e=url_entry):
                        try:
                            e.delete(0, "end")
                            e.insert(0, win.clipboard_get().strip())
                        except Exception:
                            pass

                    tk.Button(row, text="📋", font=(UI_FONT, 9),
                              bg=BTN_GRAY, fg=FG, relief="flat", cursor="hand2",
                              activebackground="#4d5268",
                              command=make_paste, padx=6, pady=3
                              ).pack(side="left", padx=(4, 0))

                    pending_entries.append((name_var, url_var))

                def save_pending():
                    overrides = self._load_overrides()
                    saved = []
                    for nv, uv in pending_entries:
                        n = nv.get().strip()
                        u = uv.get().strip()
                        if n and u:
                            overrides[n] = u
                            saved.append(n)
                    if saved:
                        self._save_overrides(overrides)
                        refresh_tree()
                        self._log(f"  Overrides saved: {', '.join(saved)}\n")
                        remaining = [p for p in self._missing_players if p not in saved]
                        self._update_missing_banner(remaining)

                tk.Button(pf_outer, text="💾  Save all",
                          font=(UI_FONT, 10, "bold"),
                          bg=BTN_GREEN, fg="white", relief="flat", cursor="hand2",
                          activebackground="#2ecc71",
                          command=save_pending, padx=14, pady=5
                          ).pack(anchor="e", pady=(8, 0))

        # ── Existing overrides list ───────────────────────────────
        list_frame = tk.Frame(win, bg=BG2)
        list_frame.pack(fill="both", expand=True, padx=14, pady=(0, 6))

        columns = ("fs_name", "sofifa_url")
        tree = ttk.Treeview(list_frame, columns=columns, show="headings", height=8)
        tree.heading("fs_name",    text="Flashscore Name")
        tree.heading("sofifa_url", text="SoFIFA URL")
        tree.column("fs_name",    width=140, anchor="w")
        tree.column("sofifa_url", width=420, anchor="w")

        style = ttk.Style()
        style.theme_use("default")
        style.configure("Treeview",
                         background=BG2, foreground=FG,
                         fieldbackground=BG2, rowheight=22,
                         font=(MONO_FONT, 9))
        style.configure("Treeview.Heading",
                         background="#2d3147", foreground=FG_DIM,
                         font=(UI_FONT, 9))
        style.map("Treeview", background=[("selected", "#3a4066")])

        sb = tk.Scrollbar(list_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=sb.set)
        tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        overrides = self._load_overrides()

        def refresh_tree():
            overrides_fresh = self._load_overrides()
            overrides.clear()
            overrides.update(overrides_fresh)
            tree.delete(*tree.get_children())
            for k, v in overrides.items():
                tree.insert("", "end", values=(k, v))

        refresh_tree()

        # ── Add form ──────────────────────────────────────────────
        add_frame = tk.Frame(win, bg=BG, pady=6)
        add_frame.pack(fill="x", padx=14)

        tk.Label(add_frame, text="Flashscore name:", font=(UI_FONT, 9),
                 bg=BG, fg=FG_DIM).grid(row=0, column=0, sticky="w", padx=(0, 6))
        entry_name = tk.Entry(add_frame, font=(UI_FONT, 10),
                              bg="#2d3147", fg=FG, insertbackground=FG,
                              relief="flat", highlightthickness=1,
                              highlightbackground="#3d4255", width=18)
        entry_name.grid(row=0, column=1, sticky="ew", padx=(0, 10))

        tk.Label(add_frame, text="SoFIFA URL:", font=(UI_FONT, 9),
                 bg=BG, fg=FG_DIM).grid(row=0, column=2, sticky="w", padx=(0, 6))
        entry_url = tk.Entry(add_frame, font=(UI_FONT, 10),
                             bg="#2d3147", fg=FG, insertbackground=FG,
                             relief="flat", highlightthickness=1,
                             highlightbackground="#3d4255", width=34)
        entry_url.grid(row=0, column=3, sticky="ew", padx=(0, 10))
        add_frame.columnconfigure(3, weight=1)

        def do_add():
            n = entry_name.get().strip()
            u = entry_url.get().strip()
            if not n or not u:
                return
            overrides[n] = u
            self._save_overrides(overrides)
            refresh_tree()
            entry_name.delete(0, "end")
            entry_url.delete(0, "end")
            self._log(f"  Override added: '{n}' → {u}\n")

        def do_paste_url():
            try:
                entry_url.delete(0, "end")
                entry_url.insert(0, win.clipboard_get().strip())
            except Exception:
                pass

        tk.Button(add_frame, text="+ Add", font=(UI_FONT, 9, "bold"),
                  bg=BTN_GREEN, fg="white", relief="flat", cursor="hand2",
                  activebackground="#2ecc71", command=do_add,
                  padx=10, pady=4).grid(row=0, column=4, padx=(0, 4))

        tk.Button(add_frame, text="📋", font=(UI_FONT, 9),
                  bg=BTN_GRAY, fg=FG, relief="flat", cursor="hand2",
                  activebackground="#4d5268", command=do_paste_url,
                  padx=6, pady=4).grid(row=0, column=5)

        def do_delete():
            sel = tree.selection()
            if not sel:
                return
            for item in sel:
                fs_name = tree.item(item, "values")[0]
                overrides.pop(fs_name, None)
            self._save_overrides(overrides)
            refresh_tree()

        btn_row = tk.Frame(win, bg=BG, pady=4)
        btn_row.pack(fill="x", padx=14, pady=(0, 10))
        tk.Button(btn_row, text="🗑 Delete selected",
                  font=(UI_FONT, 9), bg="#5a2020", fg="#ff8080",
                  relief="flat", cursor="hand2",
                  activebackground="#7a2828", activeforeground="#ffaaaa",
                  command=do_delete, padx=10, pady=4).pack(side="left")
        tk.Button(btn_row, text="Close",
                  font=(UI_FONT, 9), bg=BTN_GRAY, fg=FG,
                  relief="flat", cursor="hand2",
                  activebackground="#4d5268",
                  command=win.destroy, padx=10, pady=4).pack(side="right")

    # ── Stop ──────────────────────────────────────────────────────

    def _stop(self):
        if self._proc:
            try:
                self._proc.terminate()
                self._log("\n■ Stopped by user.\n")
                self.status_var.set("Stopped.")
            except Exception:
                pass

    # ── Auto-update ───────────────────────────────────────────────

    def _bg_update_check(self):
        """Background thread: silently check for updates on startup."""
        try:
            import updater
            available, local, remote = updater.check_for_update(timeout=8)
            if available:
                self.after(0, self._show_update_banner, local, remote)
        except Exception:
            pass  # No internet or updater not configured — fail silently

    def _show_update_banner(self, local: str, remote: str):
        """Show a non-intrusive update banner below the header."""
        if self._update_banner:
            self._update_banner.destroy()

        banner = tk.Frame(self, bg="#1e3a1e", pady=6)
        self._update_banner = banner

        tk.Label(
            banner,
            text=f"⬆  Update available: v{local}  →  v{remote}",
            font=(UI_FONT, 9, "bold"), bg="#1e3a1e", fg="#7ecb7e"
        ).pack(side="left", padx=(14, 12))

        tk.Button(
            banner, text="Update now",
            font=(UI_FONT, 9, "bold"),
            bg=BTN_GREEN, fg="white", relief="flat", cursor="hand2",
            activebackground="#2ecc71",
            command=lambda: self._do_update(remote),
            padx=10, pady=3
        ).pack(side="left")

        tk.Button(
            banner, text="✕", font=(UI_FONT, 8),
            bg="#1e3a1e", fg="#7ecb7e", relief="flat", cursor="hand2",
            command=banner.destroy, padx=6
        ).pack(side="right", padx=8)

        # Insert banner below header (before url_frame)
        banner.pack(fill="x", padx=16, pady=(0, 4))

    def _check_update_manual(self):
        """Called when user clicks 'Check for Updates'."""
        self.btn_check_update.configure(state="disabled", text="Checking...")
        self.update_idletasks()

        def worker():
            try:
                import updater
                available, local, remote = updater.check_for_update(timeout=12)
            except Exception as e:
                self.after(0, lambda: self._update_check_result(False, "?", "?", str(e)))
                return
            self.after(0, lambda: self._update_check_result(available, local, remote))

        threading.Thread(target=worker, daemon=True).start()

    def _update_check_result(self, available: bool, local: str, remote: str, error: str = ""):
        self.btn_check_update.configure(state="normal", text="⬆  Check for Updates")
        if error:
            self.status_var.set(f"Update check failed: {error}")
            return
        if available:
            self._show_update_banner(local, remote)
        else:
            if remote == "?":
                self.status_var.set("Could not reach GitHub — check internet connection.")
            else:
                self.status_var.set(f"Already up to date (v{local}).")

    def _do_update(self, remote: str):
        """Apply update: download files from GitHub, then prompt restart."""
        import tkinter.messagebox as mb

        if self._running:
            mb.showwarning("Update", "Please stop the current run before updating.")
            return

        ok = mb.askyesno(
            "Update",
            f"Download and install v{remote}?\n\n"
            "The app files will be replaced. Your match data and overrides will not be touched.\n\n"
            "The app will need to be restarted after the update.",
            icon="question"
        )
        if not ok:
            return

        # Show progress window
        prog_win = tk.Toplevel(self)
        prog_win.title("Updating...")
        prog_win.configure(bg=BG)
        prog_win.resizable(False, False)
        prog_win.grab_set()

        tk.Label(prog_win, text=f"Installing v{remote}...", font=(UI_FONT, 11, "bold"),
                 bg=BG, fg=FG).pack(pady=(18, 6), padx=24)

        progress_var = tk.StringVar(value="Starting...")
        tk.Label(prog_win, textvariable=progress_var, font=(MONO_FONT, 9),
                 bg=BG, fg=FG_DIM, justify="left").pack(padx=24, pady=(0, 14))

        prog_win.update_idletasks()
        x = self.winfo_x() + (self.winfo_width()  - 320) // 2
        y = self.winfo_y() + (self.winfo_height() - 160) // 2
        prog_win.geometry(f"320x160+{x}+{y}")

        def worker():
            try:
                import updater

                def on_progress(current, total, name, ok):
                    status = "✓" if ok else "✗"
                    self.after(0, progress_var.set,
                               f"[{current}/{total}] {status}  {name}")

                updated, failed, ae_results = updater.apply_update(on_progress)
                self.after(0, prog_win.destroy)

                # Build result message
                lines = [f"✓ Updated {len(updated)} file(s)."]

                if ae_results:
                    ae_ok  = [r for r in ae_results if r[1]]
                    ae_bad = [r for r in ae_results if not r[1]]
                    if ae_ok:
                        lines.append(f"\n✓ AE extension installed in {len(ae_ok)} location(s).")
                    if ae_bad:
                        lines.append(f"\n⚠ AE extension failed in {len(ae_bad)} location(s):\n"
                                     + "\n".join(f"  {r[0]}: {r[2]}" for r in ae_bad))
                else:
                    lines.append("\nℹ AE extension: no After Effects installation found.\n"
                                 "  Copy 'Lineup Panel.jsx' manually to:\n"
                                 "  Adobe AE → Support Files → Scripts → ScriptUI Panels")

                if failed:
                    lines.append(f"\n⚠ {len(failed)} file(s) failed:\n" + "\n".join(failed))

                lines.append("\n\nPlease restart the app.")
                msg = "\n".join(lines)

                if failed or (ae_results and any(not r[1] for r in ae_results)):
                    self.after(0, lambda: mb.showwarning(f"Update v{remote}", msg))
                else:
                    self.after(0, lambda: mb.showinfo(f"Update v{remote} complete", msg))

                if self._update_banner:
                    self.after(0, self._update_banner.destroy)
                    self._update_banner = None
            except Exception as e:
                self.after(0, prog_win.destroy)
                self.after(0, lambda: mb.showerror("Update failed", str(e)))

        threading.Thread(target=worker, daemon=True).start()


if __name__ == "__main__":
    app = App()
    app.mainloop()
