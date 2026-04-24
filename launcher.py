#!/usr/bin/env python3
"""
launcher.py — Flashscore Ratings UI
=====================================
Double-click launcher.py  or:  python3 launcher.py

Platform-aware UI:
  - macOS: native Aqua (ttk) widgets, clean light theme
  - Windows / Linux: custom dark theme with tk widgets
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

IS_MAC = (sys.platform == "darwin")
IS_WIN = sys.platform.startswith("win")

# ── Fonts ─────────────────────────────────────────────────────────
if IS_MAC:
    UI_FONT   = "SF Pro Text"       # macOS 10.11+ system UI
    UI_ALT    = "Helvetica Neue"    # fallback
    MONO_FONT = "SF Mono"
    MONO_ALT  = "Menlo"
elif IS_WIN:
    UI_FONT = UI_ALT = "Segoe UI"
    MONO_FONT = MONO_ALT = "Consolas"
else:
    UI_FONT = UI_ALT = "DejaVu Sans"
    MONO_FONT = MONO_ALT = "DejaVu Sans Mono"


def _font(family, size, weight="normal"):
    """Build a font tuple that tolerates a missing family."""
    return (family, size, weight) if weight != "normal" else (family, size)


# ── Color palette ─────────────────────────────────────────────────
if IS_MAC:
    # Apple-inspired light palette
    BG         = "#f5f5f7"   # window background
    CARD       = "#ffffff"   # card / elevated surfaces
    BORDER     = "#d2d2d7"
    ACCENT     = "#0a84ff"
    ACCENT_HI  = "#0071e3"
    SUCCESS    = "#30d158"
    SUCCESS_HI = "#28b14c"
    WARNING    = "#ff9f0a"
    DANGER     = "#ff453a"
    FG         = "#1d1d1f"
    FG_DIM     = "#6e6e73"
    FG_MUTED   = "#8e8e93"
    LOG_BG     = "#1d1d1f"
    LOG_FG     = "#f5f5f7"
else:
    BG         = "#1a1d24"
    CARD       = "#23273a"
    BORDER     = "#3d4255"
    ACCENT     = "#4f8ef7"
    ACCENT_HI  = "#2980b9"
    SUCCESS    = "#27ae60"
    SUCCESS_HI = "#2ecc71"
    WARNING    = "#f1c40f"
    DANGER     = "#e74c3c"
    FG         = "#e8eaf0"
    FG_DIM     = "#7a8099"
    FG_MUTED   = "#555c7a"
    LOG_BG     = "#12141c"
    LOG_FG     = "#c8d0e0"


# ── IO helpers ────────────────────────────────────────────────────

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


# ── Styling ───────────────────────────────────────────────────────

def _setup_ttk_styles(root: tk.Tk):
    """Configure ttk styles. On Mac we use the native 'aqua' theme and
    layer on custom styles for accented buttons. On Windows we fall
    back to 'clam' so we can color ttk widgets consistently with the
    dark theme."""
    style = ttk.Style(root)

    if IS_MAC:
        try:
            style.theme_use("aqua")
        except tk.TclError:
            style.theme_use("default")

        # Typography-only tweaks — aqua handles colors natively for
        # buttons/entries, so we don't fight the OS.
        style.configure("TLabel",      font=_font(UI_FONT, 12), background=BG,  foreground=FG)
        style.configure("Dim.TLabel",  font=_font(UI_FONT, 11), background=BG,  foreground=FG_DIM)
        style.configure("Card.TLabel", font=_font(UI_FONT, 11), background=CARD, foreground=FG_DIM)
        style.configure("Header.TLabel", font=_font(UI_FONT, 18, "bold"),
                        background=BG, foreground=FG)
        style.configure("Footer.TLabel", font=_font(UI_FONT, 10),
                        background=BG, foreground=FG_MUTED)
        style.configure("Status.TLabel", font=_font(UI_FONT, 11),
                        background=CARD, foreground=FG_DIM)

        style.configure("TFrame",       background=BG)
        style.configure("Card.TFrame",  background=CARD)
        style.configure("TLabelframe",  background=BG)
        style.configure("TLabelframe.Label", background=BG, foreground=FG_DIM)

        style.configure("TEntry", padding=6)
        style.configure("TRadiobutton", background=BG, foreground=FG,
                        font=_font(UI_FONT, 12))
        style.configure("TButton", font=_font(UI_FONT, 12), padding=(14, 6))
        style.configure("Primary.TButton",   font=_font(UI_FONT, 12, "bold"), padding=(18, 6))
        style.configure("Secondary.TButton", font=_font(UI_FONT, 12), padding=(16, 6))
        style.configure("Small.TButton",     font=_font(UI_FONT, 11), padding=(10, 4))
        style.configure("Tiny.TButton",      font=_font(UI_FONT, 10), padding=(8, 2))
        style.configure("Danger.TButton",    font=_font(UI_FONT, 11), padding=(14, 5))

        # Treeview
        style.configure("Treeview",
                        background=CARD, foreground=FG,
                        fieldbackground=CARD, rowheight=24,
                        font=_font(MONO_FONT, 11))
        style.configure("Treeview.Heading",
                        background=BG, foreground=FG_DIM,
                        font=_font(UI_FONT, 11, "bold"))
        style.map("Treeview", background=[("selected", "#d0e4ff")],
                             foreground=[("selected", FG)])

    else:
        style.theme_use("default")
        style.configure("Treeview",
                        background=CARD, foreground=FG,
                        fieldbackground=CARD, rowheight=22,
                        font=_font(MONO_FONT, 9))
        style.configure("Treeview.Heading",
                        background="#2d3147", foreground=FG_DIM,
                        font=_font(UI_FONT, 9))
        style.map("Treeview", background=[("selected", "#3a4066")])


# ── Widget factories ──────────────────────────────────────────────
# These abstract the Mac / non-Mac difference. On Mac they return
# native ttk widgets (aqua renderer). On Windows they return tk
# widgets so we keep full control over colors for the dark theme.

def make_frame(parent, card=False, **kw):
    if IS_MAC:
        return ttk.Frame(parent, style="Card.TFrame" if card else "TFrame", **kw)
    bg = CARD if card else BG
    return tk.Frame(parent, bg=bg, **kw)


def make_label(parent, text="", variant="default", **kw):
    """variant: default | dim | header | footer | status | card-dim"""
    if IS_MAC:
        style_map = {
            "default":  "TLabel",
            "dim":      "Dim.TLabel",
            "header":   "Header.TLabel",
            "footer":   "Footer.TLabel",
            "status":   "Status.TLabel",
            "card-dim": "Card.TLabel",
        }
        lbl = ttk.Label(parent, text=text, style=style_map.get(variant, "TLabel"), **kw)
        return lbl

    fonts = {
        "default":  _font(UI_FONT, 10),
        "dim":      _font(UI_FONT, 9),
        "header":   _font(UI_FONT, 16, "bold"),
        "footer":   _font(UI_FONT, 8),
        "status":   _font(UI_FONT, 9),
        "card-dim": _font(UI_FONT, 9),
    }
    colors = {
        "default":  (BG,   FG),
        "dim":      (BG,   FG_DIM),
        "header":   (BG,   FG),
        "footer":   (BG,   FG_DIM),
        "status":   (CARD, FG_DIM),
        "card-dim": (CARD, FG_DIM),
    }
    bg, fg = colors.get(variant, (BG, FG))
    return tk.Label(parent, text=text, font=fonts.get(variant, _font(UI_FONT, 10)),
                    bg=bg, fg=fg, **kw)


def make_entry(parent, textvariable=None, **kw):
    if IS_MAC:
        e = ttk.Entry(parent, textvariable=textvariable,
                      font=_font(UI_FONT, 13), **kw)
        return e
    return tk.Entry(parent, textvariable=textvariable,
                    font=_font(UI_FONT, 10), bg="#2d3147", fg=FG,
                    insertbackground=FG, relief="flat",
                    highlightthickness=1, highlightbackground=BORDER,
                    highlightcolor=ACCENT, **kw)


def make_button(parent, text="", command=None, kind="default", **kw):
    """kind: default | primary | secondary | small | tiny | danger"""
    if IS_MAC:
        style_map = {
            "default":   "TButton",
            "primary":   "Primary.TButton",
            "secondary": "Secondary.TButton",
            "small":     "Small.TButton",
            "tiny":      "Tiny.TButton",
            "danger":    "Danger.TButton",
        }
        return ttk.Button(parent, text=text, command=command,
                          style=style_map.get(kind, "TButton"), **kw)

    # Windows / Linux — colored tk.Button
    presets = {
        "default":   dict(bg=BORDER,  fg=FG,     hover="#4d5268",  font_size=10, bold=False),
        "primary":   dict(bg=SUCCESS, fg="white", hover=SUCCESS_HI, font_size=11, bold=True),
        "secondary": dict(bg=ACCENT,  fg="white", hover=ACCENT_HI, font_size=11, bold=False),
        "small":     dict(bg=BORDER,  fg=FG,     hover="#4d5268",  font_size=9,  bold=False),
        "tiny":      dict(bg=BORDER,  fg=FG_DIM, hover="#4d5268",  font_size=8,  bold=False),
        "danger":    dict(bg="#5a2020", fg="#ff8080", hover="#7a2828", font_size=10, bold=False),
    }
    p = presets.get(kind, presets["default"])
    fam = UI_FONT
    font = (fam, p["font_size"], "bold") if p["bold"] else (fam, p["font_size"])
    return tk.Button(parent, text=text, command=command,
                     font=font, bg=p["bg"], fg=p["fg"],
                     relief="flat", cursor="hand2",
                     activebackground=p["hover"], activeforeground=p["fg"],
                     padx=14, pady=6, **kw)


def make_radio(parent, text, variable, value, command=None):
    if IS_MAC:
        return ttk.Radiobutton(parent, text=text, variable=variable,
                               value=value, command=command,
                               style="TRadiobutton")
    return tk.Radiobutton(parent, text=text, variable=variable, value=value,
                          command=command, bg=BG, fg=FG, selectcolor=CARD,
                          activebackground=BG, activeforeground=FG,
                          font=_font(UI_FONT, 10), relief="flat",
                          cursor="hand2")


# ── App ───────────────────────────────────────────────────────────

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Flashscore Ratings")
        self.configure(bg=BG)
        self.resizable(True, True)

        if IS_MAC:
            self.minsize(780, 600)
            self.geometry("860x680")
        else:
            self.minsize(580, 500)

        _setup_ttk_styles(self)

        self._proc            = None
        self._running         = False
        self._missing_players = []
        self._update_banner   = None

        self._build_ui()
        self._load_state()
        threading.Thread(target=self._bg_update_check, daemon=True).start()

    # ── UI Construction ───────────────────────────────────────────

    def _build_ui(self):
        # ── Header ────────────────────────────────────────────────
        hdr = make_frame(self)
        hdr.pack(fill="x", padx=24, pady=(18, 8))

        make_label(hdr, "⚽  Flashscore Ratings", variant="header").pack(side="left")

        self.btn_check_update = make_button(
            hdr, text="Check for Updates", command=self._check_update_manual,
            kind="tiny"
        )
        self.btn_check_update.pack(side="right")

        # ── URL card ──────────────────────────────────────────────
        url_card = make_frame(self, card=True)
        url_card.pack(fill="x", padx=24, pady=(6, 10))

        pad = make_frame(url_card, card=True)
        pad.pack(fill="x", padx=16, pady=14)

        make_label(pad, "Flashscore URL", variant="card-dim").pack(anchor="w")

        entry_row = make_frame(pad, card=True)
        entry_row.pack(fill="x", pady=(6, 0))

        self.url_var = tk.StringVar()
        self.url_entry = make_entry(entry_row, textvariable=self.url_var)
        if IS_MAC:
            self.url_entry.pack(side="left", fill="x", expand=True, ipady=4)
        else:
            self.url_entry.pack(side="left", fill="x", expand=True, ipady=6)

        make_button(entry_row, text="Paste", command=self._paste_url,
                    kind="small").pack(side="left", padx=(8, 0))
        make_button(entry_row, text="Clear", command=lambda: self.url_var.set(""),
                    kind="small").pack(side="left", padx=(6, 0))

        # ── Match type ────────────────────────────────────────────
        type_row = make_frame(self)
        type_row.pack(fill="x", padx=24, pady=(0, 4))

        make_label(type_row, "Match type:", variant="dim").pack(side="left", padx=(0, 14))
        self.match_type = tk.StringVar(value="club")
        make_radio(type_row, "Club", self.match_type, "club",
                   self._on_type_change).pack(side="left")
        make_radio(type_row, "National team", self.match_type, "national",
                   self._on_type_change).pack(side="left", padx=(16, 0))

        # ── Action buttons ────────────────────────────────────────
        btn_row = make_frame(self)
        btn_row.pack(fill="x", padx=24, pady=(10, 6))

        self.btn_run = make_button(btn_row, text="▶  Full Run",
                                   command=self._run_full, kind="primary")
        self.btn_run.pack(side="left", padx=(0, 8))

        self.btn_refresh = make_button(btn_row, text="↻  Refresh Stats",
                                       command=self._run_refresh, kind="secondary")
        self.btn_refresh.pack(side="left", padx=(0, 8))

        self.btn_redownload = make_button(btn_row, text="⬇  Re-download images",
                                          command=self._run_redownload, kind="default")
        self.btn_redownload.pack(side="left")

        self.btn_stop = make_button(btn_row, text="■  Stop",
                                    command=self._stop, kind="default")
        self.btn_stop.pack(side="right")
        self._set_widget_state(self.btn_stop, "disabled")

        self.btn_reset = make_button(btn_row, text="🗑  Reset",
                                     command=self._confirm_reset, kind="danger")
        self.btn_reset.pack(side="right", padx=(0, 8))

        make_button(btn_row, text="📷  Photos",
                    command=self._open_player_photos, kind="default"
                    ).pack(side="right", padx=(0, 6))

        make_button(btn_row, text="✏  Overrides",
                    command=self._open_overrides, kind="default"
                    ).pack(side="right", padx=(0, 6))

        # ── Status bar ────────────────────────────────────────────
        self.status_var = tk.StringVar(value="Ready.")
        status_wrap = make_frame(self, card=True)
        status_wrap.pack(fill="x", padx=24, pady=(6, 0))
        status_lbl = make_label(status_wrap, "", variant="status")
        status_lbl.configure(textvariable=self.status_var, anchor="w")
        status_lbl.pack(fill="x", padx=12, pady=6)

        # ── Log output ────────────────────────────────────────────
        log_wrap = make_frame(self)
        log_wrap.pack(fill="both", expand=True, padx=24, pady=(8, 8))

        log_header = make_frame(log_wrap)
        log_header.pack(fill="x")
        make_label(log_header, "Output", variant="dim").pack(side="left")
        make_button(log_header, text="Clear log", command=self._clear_log,
                    kind="tiny").pack(side="right")

        self.log = scrolledtext.ScrolledText(
            log_wrap, font=_font(MONO_FONT, 11 if IS_MAC else 9),
            bg=LOG_BG, fg=LOG_FG,
            insertbackground=LOG_FG, relief="flat",
            wrap="word", state="disabled",
            borderwidth=0, highlightthickness=0
        )
        self.log.pack(fill="both", expand=True, pady=(6, 0))

        # ── Footer ────────────────────────────────────────────────
        make_label(self, "Marian Grosu  ·  Flashscore Ratings",
                   variant="footer", anchor="center"
                   ).pack(fill="x", pady=(6, 10))

        # ── Log color tags ────────────────────────────────────────
        self.log.tag_config("ok",     foreground="#7ad97e")
        self.log.tag_config("warn",   foreground="#ffd666")
        self.log.tag_config("err",    foreground="#ff8080")
        self.log.tag_config("header", foreground="#6fb4ff")
        self.log.tag_config("dim",    foreground="#9aa2b6")

        # ── Missing players banner ────────────────────────────────
        self.missing_frame = make_frame(self, card=True)
        self.missing_label = make_label(
            self.missing_frame, "", variant="card-dim", anchor="w"
        )
        self.missing_label.configure(foreground=WARNING)
        self.missing_label.pack(side="left", padx=(12, 8), pady=8)
        make_button(self.missing_frame, text="→  Fill in overrides",
                    command=self._open_overrides_for_missing,
                    kind="small").pack(side="left", pady=8)

    # ── State ─────────────────────────────────────────────────────

    def _load_state(self):
        url = read_last_url()
        if url:
            self.url_var.set(url)
        self.match_type.set(read_match_type())

    def _on_type_change(self):
        write_match_type(self.match_type.get())

    def _paste_url(self):
        try:
            self.url_var.set(self.clipboard_get().strip())
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
        elif line.startswith("===") or re.match(r"^\[\d+/", line):
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

    @staticmethod
    def _set_widget_state(w, state):
        try:
            if isinstance(w, ttk.Widget):
                w.state(["disabled"] if state == "disabled" else ["!disabled"])
            else:
                w.configure(state=state)
        except Exception:
            pass

    def _set_running(self, running: bool):
        self._running = running
        state_btns = "disabled" if running else "normal"
        state_stop = "normal"   if running else "disabled"
        for w in (self.btn_run, self.btn_refresh, self.btn_redownload, self.btn_reset):
            self._set_widget_state(w, state_btns)
        self._set_widget_state(self.btn_stop, state_stop)
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
        if mb.askyesno("Reset — are you sure?", msg, icon="warning"):
            self._do_reset()

    def _do_reset(self):
        import shutil
        output_dir = BASE_DIR / "flashscore_output"
        deleted, errors = [], []

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
        for d in deleted: self._log(f"  ✓ Deleted: {d}\n")
        for e in errors:  self._log(f"  ⚠ Error: {e}\n")
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

        # Use the same Python interpreter that's running the launcher.
        # On Mac "python" often doesn't exist — only "python3".
        cmd = [sys.executable, str(BASE_DIR / script)]
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

    def _run_full(self):       self._run_script("run.py")
    def _run_redownload(self): self._run_script("run.py", extra_args=["--images-only"])
    def _run_refresh(self):    self._run_script("refresh_stats.py")

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

        make_label(win, "Refresh Stats", variant="header").pack(pady=(18, 4), padx=24)

        sep = make_frame(win)
        sep.configure(height=1)
        if IS_MAC:
            sep.configure(style="Card.TFrame")
        else:
            sep.configure(bg=BORDER)
        sep.pack(fill="x", padx=20, pady=(0, 10))

        lines = text.splitlines()
        if lines:
            hdr_lbl = make_label(win, lines[0])
            try: hdr_lbl.configure(foreground=ACCENT)
            except Exception: pass
            hdr_lbl.pack(padx=24, pady=(0, 6))

        body = "\n".join(lines[2:]) if len(lines) > 2 else ""
        if body:
            is_nochange = body.strip().startswith("No changes")
            color = SUCCESS if is_nochange else WARNING
            body_lbl = make_label(win, body, justify="left", anchor="w")
            try: body_lbl.configure(foreground=color)
            except Exception: pass
            body_lbl.pack(padx=28, pady=(0, 12), fill="x")
        else:
            nolbl = make_label(win, "No changes detected.")
            try: nolbl.configure(foreground=SUCCESS)
            except Exception: pass
            nolbl.pack(padx=24, pady=(0, 12))

        make_button(win, text="OK", command=win.destroy,
                    kind="primary").pack(pady=(0, 16))

        win.update_idletasks()
        x = self.winfo_x() + (self.winfo_width()  - win.winfo_width())  // 2
        y = self.winfo_y() + (self.winfo_height() - win.winfo_height()) // 2
        win.geometry(f"+{x}+{y}")

    # ── Missing players banner ────────────────────────────────────

    def _update_missing_banner(self, missing: list):
        self._missing_players = missing
        if missing:
            n = len(missing)
            self.missing_label.configure(
                text=f"⚠  {n} player{'s' if n > 1 else ''} not found:  "
                     + ",  ".join(missing)
            )
            self.missing_frame.pack(fill="x", padx=24, pady=(0, 6),
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
        win.geometry("720x560")
        win.resizable(True, True)
        win.grab_set()

        make_label(win, "Manual mappings: Flashscore name  →  SoFIFA player page URL",
                   variant="dim").pack(anchor="w", padx=16, pady=(14, 2))
        make_label(win,
                   "Example: 'Inacio'  →  https://sofifa.com/player/262622/samuele-inacio-pia/",
                   variant="footer").pack(anchor="w", padx=16, pady=(0, 6))

        prefill        = [p for p in (prefill or []) if p]
        pending_entries = []

        if prefill:
            overrides_now = self._load_overrides()
            to_fill = [p for p in prefill if p not in overrides_now]

            if to_fill:
                pf_outer = make_frame(win, card=True)
                pf_outer.pack(fill="x", padx=16, pady=(0, 8))

                pf_pad = make_frame(pf_outer, card=True)
                pf_pad.pack(fill="x", padx=12, pady=10)

                warn_lbl = make_label(pf_pad,
                    f"⚠  {len(to_fill)} player(s) not found — paste their SoFIFA URL:",
                    variant="card-dim")
                try: warn_lbl.configure(foreground=WARNING)
                except Exception: pass
                warn_lbl.pack(anchor="w", pady=(0, 8))

                for player_name in to_fill:
                    row = make_frame(pf_pad, card=True)
                    row.pack(fill="x", pady=3)

                    name_var = tk.StringVar(value=player_name)
                    url_var  = tk.StringVar()

                    nlbl = make_label(row, "", variant="card-dim", anchor="w", width=20)
                    nlbl.configure(textvariable=name_var)
                    try: nlbl.configure(foreground=FG)
                    except Exception: pass
                    nlbl.pack(side="left", padx=(0, 8))

                    url_entry = make_entry(row, textvariable=url_var)
                    url_entry.pack(side="left", fill="x", expand=True,
                                   ipady=(2 if IS_MAC else 4))

                    def make_paste(e=url_entry):
                        try:
                            e.delete(0, "end")
                            e.insert(0, win.clipboard_get().strip())
                        except Exception:
                            pass

                    make_button(row, text="Paste", command=make_paste,
                                kind="small").pack(side="left", padx=(6, 0))

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

                make_button(pf_pad, text="💾  Save all",
                            command=save_pending, kind="primary"
                            ).pack(anchor="e", pady=(10, 0))

        # ── Existing overrides list ───────────────────────────────
        list_frame = make_frame(win, card=True)
        list_frame.pack(fill="both", expand=True, padx=16, pady=(0, 8))

        tree = ttk.Treeview(list_frame, columns=("fs_name", "sofifa_url"),
                            show="headings", height=10)
        tree.heading("fs_name",    text="Flashscore Name")
        tree.heading("sofifa_url", text="SoFIFA URL")
        tree.column("fs_name",    width=160, anchor="w")
        tree.column("sofifa_url", width=460, anchor="w")

        sb = ttk.Scrollbar(list_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=sb.set)
        tree.pack(side="left", fill="both", expand=True, padx=(6, 0), pady=6)
        sb.pack(side="right", fill="y", pady=6)

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
        add_frame = make_frame(win)
        add_frame.pack(fill="x", padx=16, pady=6)

        make_label(add_frame, "Flashscore name:", variant="dim"
                   ).grid(row=0, column=0, sticky="w", padx=(0, 6))
        entry_name_var = tk.StringVar()
        entry_name = make_entry(add_frame, textvariable=entry_name_var, width=18)
        entry_name.grid(row=0, column=1, sticky="ew", padx=(0, 10))

        make_label(add_frame, "SoFIFA URL:", variant="dim"
                   ).grid(row=0, column=2, sticky="w", padx=(0, 6))
        entry_url_var = tk.StringVar()
        entry_url = make_entry(add_frame, textvariable=entry_url_var, width=34)
        entry_url.grid(row=0, column=3, sticky="ew", padx=(0, 10))
        add_frame.columnconfigure(3, weight=1)

        def do_add():
            n = entry_name_var.get().strip()
            u = entry_url_var.get().strip()
            if not n or not u:
                return
            overrides[n] = u
            self._save_overrides(overrides)
            refresh_tree()
            entry_name_var.set("")
            entry_url_var.set("")
            self._log(f"  Override added: '{n}' → {u}\n")

        def do_paste_url():
            try:
                entry_url_var.set(win.clipboard_get().strip())
            except Exception:
                pass

        make_button(add_frame, text="+ Add", command=do_add, kind="primary"
                    ).grid(row=0, column=4, padx=(0, 4))
        make_button(add_frame, text="Paste", command=do_paste_url, kind="small"
                    ).grid(row=0, column=5)

        def do_delete():
            sel = tree.selection()
            if not sel: return
            for item in sel:
                fs_name = tree.item(item, "values")[0]
                overrides.pop(fs_name, None)
            self._save_overrides(overrides)
            refresh_tree()

        btn_row = make_frame(win)
        btn_row.pack(fill="x", padx=16, pady=(4, 12))
        make_button(btn_row, text="🗑 Delete selected", command=do_delete,
                    kind="danger").pack(side="left")
        make_button(btn_row, text="Close", command=win.destroy,
                    kind="default").pack(side="right")

    # ── Player Photos window ──────────────────────────────────────

    def _open_player_photos(self):
        """Fereastra cu URL-urile SoFIFA detectate per jucator + override rapid."""
        data_path = BASE_DIR / "flashscore_output" / "data.json"
        if not data_path.exists():
            import tkinter.messagebox as mb
            mb.showinfo("Player Photos", "No match data found.\nRun Full Run first.")
            return

        try:
            with open(data_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            import tkinter.messagebox as mb
            mb.showerror("Player Photos", f"Could not read data.json:\n{e}")
            return

        win = tk.Toplevel(self)
        win.title("Player SoFIFA URLs")
        win.configure(bg=BG)
        win.geometry("860x600")
        win.resizable(True, True)
        win.grab_set()

        match_info = data.get("match", {})
        title_text = (f"{match_info.get('home_team','')}  {match_info.get('home_score','')} - "
                      f"{match_info.get('away_score','')}  {match_info.get('away_team','')}")
        make_label(win, title_text, variant="dim").pack(anchor="w", padx=16, pady=(12, 2))
        make_label(win,
                   "Select a player → paste new SoFIFA URL → Save Override.  Then click Redownload Photos.",
                   variant="footer").pack(anchor="w", padx=16, pady=(0, 6))

        # ── Treeview ───────────────────────────────────────────────
        cols = ("group", "name", "kit", "sofifa_url", "override")
        tree = ttk.Treeview(win, columns=cols, show="headings", height=14)
        tree.heading("group",      text="Group")
        tree.heading("name",       text="Player")
        tree.heading("kit",        text="Kit")
        tree.heading("sofifa_url", text="SoFIFA URL (detected)")
        tree.heading("override",   text="Override?")
        tree.column("group",      width=90,  anchor="w", stretch=False)
        tree.column("name",       width=150, anchor="w", stretch=False)
        tree.column("kit",        width=38,  anchor="center", stretch=False)
        tree.column("sofifa_url", width=430, anchor="w")
        tree.column("override",   width=80,  anchor="center", stretch=False)

        sb = ttk.Scrollbar(win, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=sb.set)

        tree_frame = make_frame(win, card=True)
        tree_frame.pack(fill="both", expand=True, padx=16, pady=(0, 4))
        tree.pack(in_=tree_frame, side="left", fill="both", expand=True, padx=(4, 0), pady=4)
        sb.pack(in_=tree_frame, side="right", fill="y", pady=4)

        overrides_now = self._load_overrides()

        def populate_tree():
            tree.delete(*tree.get_children())
            overrides_fresh = self._load_overrides()
            overrides_now.clear()
            overrides_now.update(overrides_fresh)

            groups = [
                ("Home starter", data.get("home", {}).get("players",     [])),
                ("Home sub",     data.get("home", {}).get("substitutes", [])),
                ("Away starter", data.get("away", {}).get("players",     [])),
                ("Away sub",     data.get("away", {}).get("substitutes", [])),
            ]
            for group_label, players in groups:
                for p in players:
                    pname = p.get("name", "")
                    kit   = p.get("number", "")
                    surl  = p.get("sofifa_url", "")
                    # Verifica daca e override setat (dupa nume)
                    has_ov = any(pname and (
                        pname.lower() == fs.lower() or
                        pname.lower().rstrip('.').rstrip() in fs.lower()
                    ) for fs in overrides_fresh)
                    ov_label = "✓ YES" if has_ov else ""
                    tree.insert("", "end",
                                values=(group_label, pname, kit, surl or "—", ov_label))

        populate_tree()

        # ── Override editor ────────────────────────────────────────
        edit_outer = make_frame(win, card=True)
        edit_outer.pack(fill="x", padx=16, pady=(0, 4))
        edit_frame = make_frame(edit_outer, card=True)
        edit_frame.pack(fill="x", padx=12, pady=10)

        # Rând 1: player selecționat
        row1 = make_frame(edit_frame, card=True)
        row1.pack(fill="x", pady=(0, 6))
        make_label(row1, "Selected:", variant="card-dim").pack(side="left", padx=(0, 8))
        sel_name_var = tk.StringVar(value="← Select a player from the list above")
        sel_lbl = make_label(row1, "", variant="card-dim", anchor="w")
        sel_lbl.configure(textvariable=sel_name_var)
        try: sel_lbl.configure(foreground=ACCENT)
        except Exception: pass
        sel_lbl.pack(side="left", fill="x", expand=True)

        # Rând 2: URL + butoane
        row2 = make_frame(edit_frame, card=True)
        row2.pack(fill="x")
        make_label(row2, "New SoFIFA URL:", variant="card-dim").pack(side="left", padx=(0, 8))
        new_url_var = tk.StringVar()
        url_entry = make_entry(row2, textvariable=new_url_var)
        url_entry.pack(side="left", fill="x", expand=True, ipady=(2 if IS_MAC else 4))

        def on_select(event=None):
            sel = tree.selection()
            if not sel:
                return
            vals = tree.item(sel[0], "values")
            sel_name_var.set(vals[1] if vals else "")
            current_url = vals[3] if vals and vals[3] != "—" else ""
            new_url_var.set(current_url)

        tree.bind("<<TreeviewSelect>>", on_select)

        def do_paste():
            try:
                new_url_var.set(win.clipboard_get().strip())
            except Exception:
                pass

        def do_save_override():
            name = sel_name_var.get().strip()
            url  = new_url_var.get().strip()
            if not name or name.startswith("←"):
                return
            if not url or not url.startswith("http"):
                return
            ov = self._load_overrides()
            ov[name] = url
            self._save_overrides(ov)
            populate_tree()
            self._log(f"  Override saved: '{name}' → {url}\n")

        def do_delete_override():
            name = sel_name_var.get().strip()
            if not name or name.startswith("←"):
                return
            ov = self._load_overrides()
            if name in ov:
                del ov[name]
                self._save_overrides(ov)
                populate_tree()
                self._log(f"  Override removed: '{name}'\n")

        make_button(row2, text="Paste", command=do_paste, kind="small"
                    ).pack(side="left", padx=(8, 4))
        make_button(row2, text="Save Override", command=do_save_override, kind="primary"
                    ).pack(side="left", padx=(0, 4))
        make_button(row2, text="Remove", command=do_delete_override, kind="danger"
                    ).pack(side="left")

        # ── Bottom buttons ─────────────────────────────────────────
        btn_row2 = make_frame(win)
        btn_row2.pack(fill="x", padx=16, pady=(0, 12))

        def do_redownload():
            win.destroy()
            self._run_redownload()

        make_button(btn_row2, text="⬇  Redownload Photos (uses overrides)",
                    command=do_redownload, kind="secondary").pack(side="left")
        make_button(btn_row2, text="Close", command=win.destroy,
                    kind="default").pack(side="right")

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
        try:
            import updater
            available, local, remote = updater.check_for_update(timeout=8)
            if available:
                self.after(0, self._show_update_banner, local, remote)
        except Exception:
            pass

    def _show_update_banner(self, local: str, remote: str):
        if self._update_banner:
            self._update_banner.destroy()

        banner = make_frame(self, card=True)
        self._update_banner = banner

        lbl = make_label(
            banner, f"⬆  Update available: v{local}  →  v{remote}",
            variant="card-dim"
        )
        try: lbl.configure(foreground=SUCCESS)
        except Exception: pass
        lbl.pack(side="left", padx=(14, 12), pady=6)

        make_button(banner, text="Update now",
                    command=lambda: self._do_update(remote),
                    kind="primary").pack(side="left", pady=6)

        make_button(banner, text="✕", command=banner.destroy,
                    kind="tiny").pack(side="right", padx=8, pady=6)

        banner.pack(fill="x", padx=24, pady=(0, 6))

    def _check_update_manual(self):
        self._set_widget_state(self.btn_check_update, "disabled")
        try: self.btn_check_update.configure(text="Checking...")
        except Exception: pass
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
        self._set_widget_state(self.btn_check_update, "normal")
        try: self.btn_check_update.configure(text="Check for Updates")
        except Exception: pass

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

        prog_win = tk.Toplevel(self)
        prog_win.title("Updating...")
        prog_win.configure(bg=BG)
        prog_win.resizable(False, False)
        prog_win.grab_set()

        make_label(prog_win, f"Installing v{remote}...", variant="header"
                   ).pack(pady=(18, 6), padx=24)

        progress_var = tk.StringVar(value="Starting...")
        pl = make_label(prog_win, "", variant="dim", justify="left")
        pl.configure(textvariable=progress_var)
        pl.pack(padx=24, pady=(0, 14))

        prog_win.update_idletasks()
        x = self.winfo_x() + (self.winfo_width()  - 340) // 2
        y = self.winfo_y() + (self.winfo_height() - 170) // 2
        prog_win.geometry(f"340x170+{x}+{y}")

        def worker():
            try:
                import updater

                def on_progress(current, total, name, ok):
                    status = "✓" if ok else "✗"
                    self.after(0, progress_var.set,
                               f"[{current}/{total}] {status}  {name}")

                updated, failed, ae_results = updater.apply_update(on_progress)
                self.after(0, prog_win.destroy)

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
