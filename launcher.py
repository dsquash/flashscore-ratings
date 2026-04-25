#!/usr/bin/env python3
"""
launcher.py — Flashscore Ratings UI
=====================================
Foloseste ttkbootstrap daca e instalat (pip install ttkbootstrap).
Fallback la ttk standard daca lipseste.
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

# ── ttkbootstrap (optional) ───────────────────────────────────────
try:
    import ttkbootstrap as _tboot
    from ttkbootstrap.constants import PRIMARY, SECONDARY, SUCCESS, DANGER, WARNING, INFO, LIGHT
    _BOOT = True
    _THEME = "litera"       # tema clara, profesionala
    _BASE_CLS = _tboot.Window
except ImportError:
    _BOOT = False
    _BASE_CLS = tk.Tk


# ── Constante vizuale ─────────────────────────────────────────────
PAD   = 20      # padding exterior uniform
PAD_S = 10      # padding interior mic
PAD_X = (PAD, PAD)
LOG_BG = "#1a1d24" if not _BOOT else "#1a1d24"
LOG_FG = "#c8d0e0"

MONO = "SF Mono" if IS_MAC else ("Consolas" if IS_WIN else "DejaVu Sans Mono")
UI   = "SF Pro Text" if IS_MAC else ("Segoe UI" if IS_WIN else "DejaVu Sans")


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


def _load_overrides() -> dict:
    if not OVERRIDES.exists():
        return {}
    try:
        with open(OVERRIDES, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_overrides(data: dict):
    with open(OVERRIDES, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ── App ───────────────────────────────────────────────────────────

class App(_BASE_CLS):
    def __init__(self):
        if _BOOT:
            super().__init__(themename=_THEME)
        else:
            super().__init__()
            self._setup_plain_ttk_style()

        self.title("Flashscore Ratings")
        self.resizable(True, True)
        self.minsize(600, 520)
        self.geometry("820x660")

        self._proc            = None
        self._running         = False
        self._missing_players = []
        self._update_banner   = None

        self._build_ui()
        self._load_state()
        threading.Thread(target=self._bg_update_check, daemon=True).start()

    def _setup_plain_ttk_style(self):
        """Stil ttk minimal cand ttkbootstrap nu e disponibil."""
        style = ttk.Style(self)
        try:
            style.theme_use("aqua" if IS_MAC else "clam")
        except tk.TclError:
            pass
        style.configure("TFrame",   background="#f5f5f7" if IS_MAC else "#1a1d24")
        style.configure("TLabel",   font=(UI, 12),  background="#f5f5f7" if IS_MAC else "#1a1d24",
                        foreground="#1d1d1f" if IS_MAC else "#e8eaf0")
        style.configure("TButton",  font=(UI, 12),  padding=(14, 6))
        style.configure("TEntry",   font=(UI, 12),  padding=6)
        style.configure("TRadiobutton", font=(UI, 12),
                        background="#f5f5f7" if IS_MAC else "#1a1d24",
                        foreground="#1d1d1f" if IS_MAC else "#e8eaf0")

    # ─────────────────────────────────────────────────────────────
    # UI build
    # ─────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = self

        # ── Header ────────────────────────────────────────────────
        hdr = ttk.Frame(root, padding=(PAD, PAD, PAD, 0))
        hdr.pack(fill="x")

        title_lbl = ttk.Label(hdr, text="⚽  Flashscore Ratings",
                              font=(UI, 20, "bold"))
        title_lbl.pack(side="left")

        self.btn_check_update = ttk.Button(
            hdr, text="Check for Updates",
            command=self._check_update_manual,
            **self._btn_kw("secondary-outline" if _BOOT else ""))
        self.btn_check_update.pack(side="right", padx=(8, 0))

        ttk.Separator(root).pack(fill="x", padx=PAD, pady=(PAD_S, 0))

        # ── URL card ──────────────────────────────────────────────
        url_frame = ttk.Frame(root, padding=(PAD, PAD_S, PAD, 0))
        url_frame.pack(fill="x")

        ttk.Label(url_frame, text="Flashscore URL",
                  font=(UI, 11), foreground="#6e6e73" if IS_MAC else "#7a8099"
                  ).pack(anchor="w", pady=(0, 4))

        entry_row = ttk.Frame(url_frame)
        entry_row.pack(fill="x")

        self.url_var = tk.StringVar()
        self.url_entry = ttk.Entry(entry_row, textvariable=self.url_var,
                                   font=(UI, 13))
        self.url_entry.pack(side="left", fill="x", expand=True, ipady=4)

        # ── Match type ────────────────────────────────────────────
        type_row = ttk.Frame(root, padding=(PAD, PAD_S, PAD, 0))
        type_row.pack(fill="x")

        ttk.Label(type_row, text="Match type:", font=(UI, 11),
                  foreground="#6e6e73" if IS_MAC else "#7a8099"
                  ).pack(side="left", padx=(0, 16))
        self.match_type = tk.StringVar(value="club")
        ttk.Radiobutton(type_row, text="Club", variable=self.match_type,
                        value="club", command=self._on_type_change
                        ).pack(side="left")
        ttk.Radiobutton(type_row, text="National team", variable=self.match_type,
                        value="national", command=self._on_type_change
                        ).pack(side="left", padx=(16, 0))

        ttk.Separator(root).pack(fill="x", padx=PAD, pady=PAD_S)

        # ── Primary actions ───────────────────────────────────────
        primary_row = ttk.Frame(root, padding=(PAD, 0, PAD, 0))
        primary_row.pack(fill="x")

        self.btn_run = ttk.Button(primary_row, text="▶  Full Run",
                                  command=self._run_full,
                                  **self._btn_kw("success"))
        self.btn_run.pack(side="left", ipadx=8, ipady=4)

        self.btn_refresh = ttk.Button(primary_row, text="↻  Refresh Stats",
                                      command=self._run_refresh,
                                      **self._btn_kw("primary"))
        self.btn_refresh.pack(side="left", padx=(10, 0), ipadx=4, ipady=4)

        # ── Secondary actions ─────────────────────────────────────
        sec_row = ttk.Frame(root, padding=(PAD, PAD_S, PAD, 0))
        sec_row.pack(fill="x")

        self.btn_redownload = ttk.Button(sec_row, text="⬇  Re-download",
                                         command=self._run_redownload,
                                         **self._btn_kw("secondary-outline" if _BOOT else "secondary"))
        self.btn_redownload.pack(side="left")

        ttk.Button(sec_row, text="📷  Photos",
                   command=self._open_player_photos,
                   **self._btn_kw("secondary-outline" if _BOOT else "secondary")
                   ).pack(side="left", padx=(8, 0))

        ttk.Button(sec_row, text="✏  Overrides",
                   command=self._open_overrides,
                   **self._btn_kw("secondary-outline" if _BOOT else "secondary")
                   ).pack(side="left", padx=(8, 0))

        # ── Status bar ────────────────────────────────────────────
        self.status_var = tk.StringVar(value="Ready.")
        status_frame = ttk.Frame(root, padding=(PAD, PAD_S, PAD, 0))
        status_frame.pack(fill="x")
        ttk.Label(status_frame, textvariable=self.status_var,
                  font=(UI, 11), foreground="#6e6e73" if IS_MAC else "#7a8099",
                  anchor="w").pack(fill="x")

        ttk.Separator(root).pack(fill="x", padx=PAD, pady=(PAD_S, 0))

        # ── Log ───────────────────────────────────────────────────
        log_outer = ttk.Frame(root, padding=(PAD, PAD_S, PAD, 0))
        log_outer.pack(fill="both", expand=True)

        log_hdr = ttk.Frame(log_outer)
        log_hdr.pack(fill="x", pady=(0, 4))
        ttk.Label(log_hdr, text="Output", font=(UI, 11),
                  foreground="#6e6e73" if IS_MAC else "#7a8099"
                  ).pack(side="left")
        ttk.Button(log_hdr, text="Clear", command=self._clear_log,
                   **self._btn_kw("light")).pack(side="right")

        self.log = scrolledtext.ScrolledText(
            log_outer, font=(MONO, 11 if IS_MAC else 9),
            bg=LOG_BG, fg=LOG_FG,
            insertbackground=LOG_FG, relief="flat",
            wrap="word", state="disabled",
            borderwidth=0, highlightthickness=0
        )
        self.log.pack(fill="both", expand=True)
        self.log.tag_config("ok",     foreground="#7ad97e")
        self.log.tag_config("warn",   foreground="#ffd666")
        self.log.tag_config("err",    foreground="#ff8080")
        self.log.tag_config("header", foreground="#6fb4ff")
        self.log.tag_config("dim",    foreground="#9aa2b6")

        # ── Footer ────────────────────────────────────────────────
        ttk.Separator(root).pack(fill="x", padx=PAD, pady=(PAD_S, 0))
        ttk.Label(root, text="Marian Grosu  ·  Flashscore Ratings",
                  font=(UI, 10), foreground="#8e8e93" if IS_MAC else "#555c7a",
                  anchor="center").pack(fill="x", pady=(6, PAD_S))

        # ── Missing players banner (initially hidden) ──────────────
        self.missing_frame = ttk.Frame(root, padding=(PAD, 0, PAD, 4))
        self.missing_label = ttk.Label(self.missing_frame, text="",
                                       font=(UI, 11), foreground="#f59e0b",
                                       anchor="w")
        self.missing_label.pack(side="left", fill="x", expand=True)
        ttk.Button(self.missing_frame, text="→ Fill overrides",
                   command=self._open_overrides_for_missing,
                   **self._btn_kw("warning-outline" if _BOOT else "secondary")
                   ).pack(side="left", padx=(8, 0))

    # ── Helper: bootstyle-aware button kwargs ─────────────────────
    @staticmethod
    def _btn_kw(bootstyle=""):
        if _BOOT and bootstyle:
            return {"bootstyle": bootstyle}
        return {}

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
            tag = "warn" if ("NOT FOUND" in line or "Missing" in line) else "err"
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

    def _set_running(self, running: bool):
        self._running = running
        state = ["disabled"] if running else ["!disabled"]
        for w in (self.btn_run, self.btn_refresh, self.btn_redownload):
            w.state(state)
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
        n_images = len(list(images_dir.glob("*.png"))) if images_dir.exists() else 0
        has_json = (output_dir / "data.json").exists()
        msg = (f"The following will be deleted:\n"
               f"  • {n_images} images\n"
               f"  • data.json ({'exists' if has_json else 'not found'})\n"
               f"  • last_url.txt, debug files\n\nContinue?")
        if mb.askyesno("Reset — are you sure?", msg, icon="warning"):
            self._do_reset()

    def _do_reset(self):
        import shutil
        output_dir = BASE_DIR / "flashscore_output"
        deleted, errors = [], []
        images_dir = output_dir / "images"
        if images_dir.exists():
            try:
                shutil.rmtree(str(images_dir)); images_dir.mkdir()
                deleted.append("images/ (all photos)")
            except Exception as e:
                errors.append(f"images/: {e}")
        for fname in ["data.json", "last_url.txt", "placeholders.json",
                      "debug.png", "debug_testids.txt", "last_refresh_summary.txt"]:
            fpath = output_dir / fname
            if fpath.exists():
                try:
                    fpath.unlink(); deleted.append(fname)
                except Exception as e:
                    errors.append(f"{fname}: {e}")
        self._log("\n🗑  RESET\n")
        for d in deleted: self._log(f"  ✓ Deleted: {d}\n")
        for e in errors:  self._log(f"  ⚠ Error: {e}\n")
        self._log("  Done.\n\n")
        self.status_var.set("Reset complete.")

    # ── Script runner ─────────────────────────────────────────────

    def _run_script(self, script: str, extra_args: list = None):
        url = self.url_var.get().strip()
        if not url and script == "run.py" and not (extra_args and any(
                a.startswith("--") for a in (extra_args or []))):
            self.status_var.set("⚠ Please enter the Flashscore URL!")
            self._log("⚠ Please enter the Flashscore URL!\n")
            return

        write_match_type(self.match_type.get())
        cmd = [sys.executable, str(BASE_DIR / script)]
        if url and script == "run.py" and not extra_args:
            cmd.append(url)
        if extra_args:
            cmd.extend(extra_args)

        label = "Full Run" if (script == "run.py" and not extra_args) else \
                "Refresh Stats" if script == "refresh_stats.py" else "Re-download"
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

    def _run_player_download(self, player_name: str):
        """Descarca poza unui singur jucator (dupa ce s-a setat un override)."""
        write_match_type(self.match_type.get())
        cmd = [sys.executable, str(BASE_DIR / "run.py"), "--player", player_name]
        label = f"Downloading photo: {player_name}"
        self._log(f"\n{'─'*50}\n▶ {label}\n{'─'*50}\n")
        self.status_var.set(f"Downloading: {player_name}...")
        self._set_running(True)

        def worker():
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
                self._proc.wait()
                rc  = self._proc.returncode
                msg = f"✓ {player_name} — photo updated." if rc == 0 else f"⚠ Exited with code {rc}."
                self.after(0, self._log, f"\n{msg}\n")
                self.after(0, self.status_var.set, msg)
            except Exception as e:
                self.after(0, self._log, f"\nERROR: {e}\n")
                self.after(0, self.status_var.set, f"ERROR: {e}")
            finally:
                self._proc = None
                self.after(0, self._set_running, False)

        threading.Thread(target=worker, daemon=True).start()

    # ── Refresh Stats summary ─────────────────────────────────────

    def _show_refresh_summary(self):
        summary_path = BASE_DIR / "flashscore_output" / "last_refresh_summary.txt"
        try:
            text = summary_path.read_text(encoding="utf-8").strip()
        except Exception:
            text = "Summary not available."

        win = tk.Toplevel(self)
        win.title("Refresh Stats — Summary")
        win.resizable(False, False)
        win.grab_set()

        outer = ttk.Frame(win, padding=PAD)
        outer.pack(fill="both", expand=True)

        ttk.Label(outer, text="Refresh Stats", font=(UI, 18, "bold")).pack(pady=(0, PAD_S))
        ttk.Separator(outer).pack(fill="x", pady=(0, PAD_S))

        lines = text.splitlines()
        if lines:
            ttk.Label(outer, text=lines[0], font=(UI, 12), foreground="#0a84ff").pack(pady=(0, 6))

        body = "\n".join(lines[2:]) if len(lines) > 2 else ""
        if body:
            is_nochange = body.strip().startswith("No changes")
            fg = "#30d158" if is_nochange else "#f59e0b"
            ttk.Label(outer, text=body, font=(UI, 11), foreground=fg,
                      justify="left", anchor="w").pack(fill="x", pady=(0, PAD_S))
        else:
            ttk.Label(outer, text="No changes detected.", foreground="#30d158",
                      font=(UI, 11)).pack(pady=(0, PAD_S))

        ttk.Button(outer, text="OK", command=win.destroy,
                   **self._btn_kw("primary")).pack()
        win.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() - win.winfo_width()) // 2
        y = self.winfo_y() + (self.winfo_height() - win.winfo_height()) // 2
        win.geometry(f"+{x}+{y}")

    # ── Missing players banner ────────────────────────────────────

    def _update_missing_banner(self, missing: list):
        self._missing_players = missing
        if missing:
            n = len(missing)
            self.missing_label.configure(
                text=f"⚠  {n} player{'s' if n > 1 else ''} not found:  " + ",  ".join(missing)
            )
            self.missing_frame.pack(fill="x", before=self.log.master)
        else:
            self.missing_frame.pack_forget()

    def _open_overrides_for_missing(self):
        self._open_overrides(prefill=self._missing_players)

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
        banner = ttk.Frame(self, padding=(PAD, 4, PAD, 4))
        self._update_banner = banner
        ttk.Label(banner, text=f"⬆  Update available: v{local}  →  v{remote}",
                  font=(UI, 11), foreground="#30d158").pack(side="left")
        ttk.Button(banner, text="Update now",
                   command=lambda: self._do_update(remote),
                   **self._btn_kw("success")).pack(side="left", padx=(12, 0))
        ttk.Button(banner, text="✕", command=banner.destroy,
                   **self._btn_kw("light")).pack(side="right")
        banner.pack(fill="x")

    def _check_update_manual(self):
        try: self.btn_check_update.configure(text="Checking...")
        except Exception: pass
        self.btn_check_update.state(["disabled"])
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
        self.btn_check_update.state(["!disabled"])
        try: self.btn_check_update.configure(text="Check for Updates")
        except Exception: pass
        if error:
            self.status_var.set(f"Update check failed: {error}")
            return
        if available:
            self._show_update_banner(local, remote)
        else:
            msg = "Could not reach GitHub." if remote == "?" else f"Already up to date (v{local})."
            self.status_var.set(msg)

    def _do_update(self, remote: str):
        import tkinter.messagebox as mb
        if self._running:
            mb.showwarning("Update", "Please stop the current run before updating.")
            return
        ok = mb.askyesno("Update",
                         f"Download and install v{remote}?\n\n"
                         "App files will be replaced. Match data and overrides are safe.\n\n"
                         "Restart required after update.", icon="question")
        if not ok:
            return

        prog_win = tk.Toplevel(self)
        prog_win.title("Updating...")
        prog_win.resizable(False, False)
        prog_win.grab_set()
        outer = ttk.Frame(prog_win, padding=PAD)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text=f"Installing v{remote}...", font=(UI, 16, "bold")).pack(pady=(0, PAD_S))
        progress_var = tk.StringVar(value="Starting...")
        ttk.Label(outer, textvariable=progress_var, font=(UI, 11),
                  foreground="#6e6e73").pack()
        prog_win.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() - 360) // 2
        y = self.winfo_y() + (self.winfo_height() - 150) // 2
        prog_win.geometry(f"360x150+{x}+{y}")

        def worker():
            try:
                import updater
                def on_progress(current, total, name, ok):
                    status = "✓" if ok else "✗"
                    self.after(0, progress_var.set, f"[{current}/{total}] {status}  {name}")
                updated, failed, ae_results = updater.apply_update(on_progress)
                self.after(0, prog_win.destroy)
                lines = [f"✓ Updated {len(updated)} file(s)."]
                if ae_results:
                    ae_ok  = [r for r in ae_results if r[1]]
                    ae_bad = [r for r in ae_results if not r[1]]
                    if ae_ok:  lines.append(f"\n✓ AE extension: {len(ae_ok)} location(s).")
                    if ae_bad: lines.append(f"\n⚠ AE failed in {len(ae_bad)} location(s).")
                else:
                    lines.append("\nℹ Copy 'Lineup Panel.jsx' to AE Scripts/ScriptUI Panels manually.")
                if failed:
                    lines.append(f"\n⚠ {len(failed)} file(s) failed.")
                lines.append("\n\nPlease restart the app.")
                msg = "\n".join(lines)
                fn = mb.showwarning if (failed or any(not r[1] for r in ae_results)) else mb.showinfo
                self.after(0, lambda: fn(f"Update v{remote}", msg))
                if self._update_banner:
                    self.after(0, self._update_banner.destroy)
                    self._update_banner = None
            except Exception as e:
                self.after(0, prog_win.destroy)
                self.after(0, lambda: mb.showerror("Update failed", str(e)))

        threading.Thread(target=worker, daemon=True).start()

    # ── Overrides window ──────────────────────────────────────────

    def _open_overrides(self, prefill: list = None):
        win = tk.Toplevel(self)
        win.title("SoFIFA Overrides")
        win.geometry("760x520")
        win.resizable(True, True)
        win.grab_set()

        outer = ttk.Frame(win, padding=PAD)
        outer.pack(fill="both", expand=True)

        ttk.Label(outer, text="Manual mappings: Flashscore name  →  SoFIFA URL",
                  font=(UI, 13, "bold")).pack(anchor="w", pady=(0, 2))
        ttk.Label(outer,
                  text="Example:  'Inacio'  →  https://sofifa.com/player/262622/...",
                  font=(UI, 10), foreground="#6e6e73").pack(anchor="w", pady=(0, PAD_S))

        prefill = [p for p in (prefill or []) if p]
        pending_entries = []

        if prefill:
            overrides_now = _load_overrides()
            to_fill = [p for p in prefill if p not in overrides_now]
            if to_fill:
                pf_frame = ttk.LabelFrame(outer, text=f"⚠  {len(to_fill)} player(s) not found",
                                          padding=PAD_S)
                pf_frame.pack(fill="x", pady=(0, PAD_S))
                for pname in to_fill:
                    row = ttk.Frame(pf_frame)
                    row.pack(fill="x", pady=3)
                    ttk.Label(row, text=pname, width=22, font=(UI, 11)).pack(side="left", padx=(0, 8))
                    url_var = tk.StringVar()
                    e = ttk.Entry(row, textvariable=url_var, font=(UI, 11))
                    e.pack(side="left", fill="x", expand=True, ipady=2)
                    def make_paste(entry=e):
                        try: entry.delete(0, "end"); entry.insert(0, win.clipboard_get().strip())
                        except Exception: pass
                    ttk.Button(row, text="Paste", command=make_paste,
                               **self._btn_kw("light")).pack(side="left", padx=(6, 0))
                    pending_entries.append((pname, url_var))

                def save_pending():
                    ov = _load_overrides()
                    saved = []
                    for pname, uv in pending_entries:
                        u = uv.get().strip()
                        if u:
                            ov[pname] = u; saved.append(pname)
                    if saved:
                        _save_overrides(ov); refresh_tree()
                        self._log(f"  Overrides saved: {', '.join(saved)}\n")
                        remaining = [p for p in self._missing_players if p not in saved]
                        self._update_missing_banner(remaining)

                ttk.Button(pf_frame, text="💾  Save all", command=save_pending,
                           **self._btn_kw("primary")).pack(anchor="e", pady=(8, 0))

        # ── Existing list ──────────────────────────────────────────
        list_frame = ttk.Frame(outer)
        list_frame.pack(fill="both", expand=True, pady=(0, PAD_S))

        cols = ("fs_name", "sofifa_url")
        tree = ttk.Treeview(list_frame, columns=cols, show="headings", height=10)
        tree.heading("fs_name",    text="Flashscore Name")
        tree.heading("sofifa_url", text="SoFIFA URL")
        tree.column("fs_name",    width=160, anchor="w")
        tree.column("sofifa_url", width=500, anchor="w")
        sb = ttk.Scrollbar(list_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        tree.pack(side="left", fill="both", expand=True)

        def refresh_tree():
            ov = _load_overrides()
            tree.delete(*tree.get_children())
            for k, v in ov.items():
                tree.insert("", "end", values=(k, v))
        refresh_tree()

        # ── Add form ───────────────────────────────────────────────
        add_frame = ttk.Frame(outer)
        add_frame.pack(fill="x", pady=(0, PAD_S))

        ttk.Label(add_frame, text="Name:", font=(UI, 11)).grid(row=0, column=0, sticky="w", padx=(0, 6))
        entry_name_var = tk.StringVar()
        ttk.Entry(add_frame, textvariable=entry_name_var, width=18, font=(UI, 11)
                  ).grid(row=0, column=1, sticky="ew", padx=(0, 10))
        ttk.Label(add_frame, text="SoFIFA URL:", font=(UI, 11)).grid(row=0, column=2, sticky="w", padx=(0, 6))
        entry_url_var = tk.StringVar()
        ttk.Entry(add_frame, textvariable=entry_url_var, width=34, font=(UI, 11)
                  ).grid(row=0, column=3, sticky="ew", padx=(0, 10))
        add_frame.columnconfigure(3, weight=1)

        def do_add():
            n = entry_name_var.get().strip(); u = entry_url_var.get().strip()
            if not n or not u: return
            ov = _load_overrides(); ov[n] = u; _save_overrides(ov)
            refresh_tree(); entry_name_var.set(""); entry_url_var.set("")
            self._log(f"  Override added: '{n}' → {u}\n")

        def do_paste_url():
            try: entry_url_var.set(win.clipboard_get().strip())
            except Exception: pass

        ttk.Button(add_frame, text="+ Add", command=do_add,
                   **self._btn_kw("primary")).grid(row=0, column=4, padx=(0, 4))
        ttk.Button(add_frame, text="Paste", command=do_paste_url,
                   **self._btn_kw("light")).grid(row=0, column=5)

        # ── Bottom ─────────────────────────────────────────────────
        bot = ttk.Frame(outer)
        bot.pack(fill="x")

        def do_delete():
            for item in tree.selection():
                fs_name = tree.item(item, "values")[0]
                ov = _load_overrides(); ov.pop(fs_name, None); _save_overrides(ov)
            refresh_tree()

        ttk.Button(bot, text="🗑 Delete selected", command=do_delete,
                   **self._btn_kw("danger-outline" if _BOOT else "danger")).pack(side="left")
        ttk.Button(bot, text="Close", command=win.destroy,
                   **self._btn_kw("secondary")).pack(side="right")

    # ── Player Photos window ──────────────────────────────────────

    def _open_player_photos(self):
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
        win.geometry("900x620")
        win.resizable(True, True)
        win.grab_set()

        outer = ttk.Frame(win, padding=PAD)
        outer.pack(fill="both", expand=True)

        # Header
        match_info = data.get("match", {})
        title_text = (f"{match_info.get('home_team','')}  "
                      f"{match_info.get('home_score','')} - "
                      f"{match_info.get('away_score','')}  "
                      f"{match_info.get('away_team','')}")
        ttk.Label(outer, text=title_text, font=(UI, 14, "bold")).pack(anchor="w", pady=(0, 4))
        ttk.Label(outer, text="Click a player → paste SoFIFA URL → Save Override  "
                              "(downloads that player's photo automatically)",
                  font=(UI, 10), foreground="#6e6e73").pack(anchor="w", pady=(0, PAD_S))

        # Treeview
        tree_frame = ttk.Frame(outer)
        tree_frame.pack(fill="both", expand=True, pady=(0, PAD_S))

        cols = ("group", "name", "kit", "sofifa_url", "override")
        tree = ttk.Treeview(tree_frame, columns=cols, show="headings", height=14)
        tree.heading("group",      text="Group")
        tree.heading("name",       text="Player")
        tree.heading("kit",        text="Kit")
        tree.heading("sofifa_url", text="SoFIFA URL (detected / override)")
        tree.heading("override",   text="Override?")
        tree.column("group",      width=90,  anchor="w", stretch=False)
        tree.column("name",       width=150, anchor="w", stretch=False)
        tree.column("kit",        width=38,  anchor="center", stretch=False)
        tree.column("sofifa_url", width=450, anchor="w")
        tree.column("override",   width=80,  anchor="center", stretch=False)

        sb = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        tree.pack(side="left", fill="both", expand=True)

        def populate_tree():
            tree.delete(*tree.get_children())
            ov_fresh = _load_overrides()
            groups_def = [
                ("Home starter", data.get("home", {}).get("players",     [])),
                ("Home sub",     data.get("home", {}).get("substitutes", [])),
                ("Away starter", data.get("away", {}).get("players",     [])),
                ("Away sub",     data.get("away", {}).get("substitutes", [])),
            ]
            for group_label, players in groups_def:
                if not isinstance(players, list):
                    continue
                for p in players:
                    if not isinstance(p, dict):
                        continue
                    pname = p.get("name", "")
                    kit   = p.get("number", "")
                    surl  = p.get("sofifa_url", "")
                    pnorm = pname.lower().strip()
                    pnorm2 = re.sub(r'\s+[a-z]\.?$', '', pnorm).strip()
                    has_ov = any(fs.lower().strip() in (pnorm, pnorm2) for fs in ov_fresh)
                    if has_ov:
                        for fs, fu in ov_fresh.items():
                            if fs.lower().strip() in (pnorm, pnorm2):
                                surl = fu; break
                    tree.insert("", "end", values=(
                        group_label, pname, kit,
                        surl or "— run Full Run v1.0.8+ to detect",
                        "✓" if has_ov else ""
                    ))

        populate_tree()

        # ── Editor ────────────────────────────────────────────────
        edit_frame = ttk.LabelFrame(outer, text="Edit Player Data", padding=PAD_S)
        edit_frame.pack(fill="x", pady=(0, PAD_S))

        # Row 1: player name label
        r1 = ttk.Frame(edit_frame)
        r1.pack(fill="x", pady=(0, 6))
        ttk.Label(r1, text="Player:", font=(UI, 11)).pack(side="left", padx=(0, 8))
        sel_name_var = tk.StringVar(value="← click a player above")
        ttk.Label(r1, textvariable=sel_name_var, font=(UI, 11, "bold"),
                  foreground="#0a84ff").pack(side="left")

        # Row 2: Kit number
        r_kit = ttk.Frame(edit_frame)
        r_kit.pack(fill="x", pady=(0, 6))
        ttk.Label(r_kit, text="Kit #:", font=(UI, 11), width=10,
                  anchor="w").pack(side="left", padx=(0, 8))
        kit_var = tk.StringVar()
        ttk.Entry(r_kit, textvariable=kit_var, font=(UI, 11),
                  width=6).pack(side="left", ipady=3, padx=(0, 8))

        def do_save_kit():
            name = sel_name_var.get().strip()
            kit  = kit_var.get().strip()
            if not name or name.startswith("←"): return
            # Update in-memory data dict and data.json
            all_grps = [
                data.get("home", {}).get("players", []),
                data.get("home", {}).get("substitutes", []),
                data.get("away", {}).get("players", []),
                data.get("away", {}).get("substitutes", []),
            ]
            found = False
            for grp in all_grps:
                for p in grp:
                    if isinstance(p, dict) and _norm(p.get("name", "")) == _norm(name):
                        p["number"] = kit
                        found = True
            if not found:
                self._log(f"  ⚠ Player '{name}' not found in data.json\n")
                return
            dpath = BASE_DIR / "flashscore_output" / "data.json"
            try:
                with open(dpath, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                self._log(f"  ✓ Kit saved: '{name}' → #{kit}\n")
                populate_tree()
            except Exception as e:
                self._log(f"  ⚠ Cannot save data.json: {e}\n")

        ttk.Button(r_kit, text="Save Kit #", command=do_save_kit,
                   **self._btn_kw("primary")).pack(side="left")

        # Row 3: SoFIFA URL
        r2 = ttk.Frame(edit_frame)
        r2.pack(fill="x")
        ttk.Label(r2, text="SoFIFA URL:", font=(UI, 11), width=10,
                  anchor="w").pack(side="left", padx=(0, 8))
        new_url_var = tk.StringVar()
        ttk.Entry(r2, textvariable=new_url_var, font=(UI, 11)
                  ).pack(side="left", fill="x", expand=True, ipady=3, padx=(0, 8))

        def on_tree_select(event=None):
            sel = tree.selection()
            if not sel: return
            vals = tree.item(sel[0], "values")
            if not vals: return
            sel_name_var.set(vals[1])
            # vals: (group, name, kit, sofifa_url, override?)
            kit_var.set(vals[2] if vals[2] and vals[2] != "—" else "")
            surl = vals[3]
            new_url_var.set(surl if surl and not surl.startswith("—") else "")

        tree.bind("<<TreeviewSelect>>", on_tree_select)

        def do_paste():
            try: new_url_var.set(win.clipboard_get().strip())
            except Exception: pass

        def do_save():
            name = sel_name_var.get().strip()
            url  = new_url_var.get().strip()
            if not name or name.startswith("←"): return
            if not url or not url.startswith("http"): return
            ov = _load_overrides(); ov[name] = url; _save_overrides(ov)
            self._log(f"  Override saved: '{name}' → {url}\n")
            win.destroy()
            self._run_player_download(name)

        def do_remove():
            name = sel_name_var.get().strip()
            if not name or name.startswith("←"): return
            ov = _load_overrides()
            for k in list(ov.keys()):
                if k.lower().strip() == name.lower().strip():
                    del ov[k]
            _save_overrides(ov); populate_tree()
            self._log(f"  Override removed: '{name}'\n")

        ttk.Button(r2, text="Paste", command=do_paste,
                   **self._btn_kw("light")).pack(side="left", padx=(0, 4))
        ttk.Button(r2, text="Save Override + Download", command=do_save,
                   **self._btn_kw("success")).pack(side="left", padx=(0, 4))
        ttk.Button(r2, text="Remove Override", command=do_remove,
                   **self._btn_kw("danger-outline" if _BOOT else "danger")).pack(side="left")

        # Bottom
        bot = ttk.Frame(outer)
        bot.pack(fill="x")
        ttk.Button(bot, text="⬇  Redownload All Photos",
                   command=lambda: [win.destroy(), self._run_redownload()],
                   **self._btn_kw("secondary")).pack(side="left")
        ttk.Button(bot, text="Close", command=win.destroy,
                   **self._btn_kw("secondary-outline" if _BOOT else "secondary")
                   ).pack(side="right")


if __name__ == "__main__":
    app = App()
    app.mainloop()
