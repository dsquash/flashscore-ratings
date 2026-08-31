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
from pathlib import Path

BASE_DIR  = Path(__file__).parent
LAST_URL  = BASE_DIR / "flashscore_output" / "last_url.txt"
LAST_SS_URL = BASE_DIR / "flashscore_output" / "last_ss_url.txt"
RUN_PY    = BASE_DIR / "run.py"

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


def read_last_ss_url():
    try:
        return LAST_SS_URL.read_text(encoding="utf-8").strip()
    except Exception:
        return ""


def write_last_ss_url(url: str):
    try:
        LAST_SS_URL.parent.mkdir(parents=True, exist_ok=True)
        LAST_SS_URL.write_text(url or "", encoding="utf-8")
    except Exception:
        pass


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


def _norm(s: str) -> str:
    """Normalizare nume pentru comparatie."""
    return s.lower().strip()






# ── App ───────────────────────────────────────────────────────────

class App(_BASE_CLS):
    def __init__(self):
        if _BOOT:
            super().__init__(themename=_THEME)
        else:
            super().__init__()
            self._setup_plain_ttk_style()

        self.title("Flashscore Ratings")
        self.resizable(False, False)
        self.geometry("820x700")

        self._proc            = None
        self._running         = False
        self._missing_players = []
        self._update_banner   = None
        self._code_update     = (False, "", "")
        self._tpl_update_available = False

        self._build_ui()
        self._load_state()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
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

        self._hdr_sep = ttk.Separator(root)
        self._hdr_sep.pack(fill="x", padx=PAD, pady=(PAD_S, 0))

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

        # ── Sofascore URL (optional) ──────────────────────────────
        ss_url_frame = ttk.Frame(root, padding=(PAD, PAD_S, PAD, 0))
        ss_url_frame.pack(fill="x")

        ttk.Label(ss_url_frame, text="Sofascore link",
                  font=(UI, 11), foreground="#6e6e73" if IS_MAC else "#7a8099"
                  ).pack(anchor="w", pady=(0, 4))

        ss_entry_row = ttk.Frame(ss_url_frame)
        ss_entry_row.pack(fill="x")

        self.ss_url_var = tk.StringVar()
        self.ss_url_entry = ttk.Entry(ss_entry_row, textvariable=self.ss_url_var,
                                      font=(UI, 13))
        self.ss_url_entry.pack(side="left", fill="x", expand=True, ipady=4)

        ttk.Separator(root).pack(fill="x", padx=PAD, pady=PAD_S)

        # ── Primary actions ───────────────────────────────────────
        primary_row = ttk.Frame(root, padding=(PAD, 0, PAD, 0))
        primary_row.pack(fill="x")

        self.btn_run = ttk.Button(primary_row, text="▶  Full Run",
                                  command=self._run_full,
                                  **self._btn_kw("success"))
        self.btn_run.pack(side="left", ipadx=8, ipady=4)

        # ── Secondary actions ─────────────────────────────────────
        sec_row = ttk.Frame(root, padding=(PAD, PAD_S, PAD, 0))
        sec_row.pack(fill="x")

        self.btn_redownload = ttk.Button(sec_row, text="⬇  Re-download",
                                         command=self._run_redownload,
                                         **self._btn_kw("secondary-outline" if _BOOT else "secondary"))
        self.btn_redownload.pack(side="left")



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
        ss_url = read_last_ss_url()
        if ss_url:
            self.ss_url_var.set(ss_url)

    def _on_close(self):
        # Save the Sofascore URL so it persists for next launch
        try:
            write_last_ss_url(self.ss_url_var.get().strip())
        except Exception:
            pass
        # On macOS, close the Terminal window that launched this app
        if IS_MAC:
            try:
                import os as _os
                _tty = ""
                for _fd in (0, 1, 2):
                    try:
                        _tty = _os.ttyname(_fd)
                        if _tty:
                            break
                    except Exception:
                        continue
                if _tty:
                    _short = _tty.replace("/dev/", "")
                    _os.system(
                        "osascript -e 'tell application \"Terminal\" to close "
                        "(every window whose tty contains \"" + _short + "\")' "
                        ">/dev/null 2>&1 &"
                    )
            except Exception:
                pass
        try:
            self.destroy()
        except Exception:
            pass

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
        for w in (self.btn_run, self.btn_redownload):
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

        cmd = [sys.executable, str(BASE_DIR / script)]
        if url and script == "run.py" and not extra_args:
            cmd.append(url)
        if extra_args:
            cmd.extend(extra_args)
        ss_url = self.ss_url_var.get().strip() if hasattr(self, 'ss_url_var') else ""
        if script == "run.py" and not extra_args:
            write_last_ss_url(ss_url)  # remember it for next launch
            if ss_url:
                cmd.extend(["--sofascore-url", ss_url])

        label = "Full Run" if (script == "run.py" and not extra_args) else \
                "Refresh + Photos" if (script == "refresh_stats.py" and extra_args and "--download-missing" in extra_args) else \
                "Refresh Stats" if script == "refresh_stats.py" else "Re-download"
        self._log(f"\n{'─'*50}\n▶ {label}\n{'─'*50}\n")
        self.status_var.set(f"Running: {label}...")
        self._set_running(True)
        is_refresh = (script == "refresh_stats.py")

        def worker():
            collected_missing = []
            try:
                import os
                env = os.environ.copy()
                env["PYTHONIOENCODING"] = "utf-8"
                env["PYTHONUNBUFFERED"]  = "1"
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
                    self.after(600, self._try_refresh_ae_comps)
            except Exception as e:
                self.after(0, self._log, f"\nERROR: {e}\n")
                self.after(0, self.status_var.set, f"ERROR: {e}")
            finally:
                self._proc = None
                self.after(0, self._set_running, False)

        threading.Thread(target=worker, daemon=True).start()

    def _run_full(self):         self._run_script("run.py")
    def _run_redownload(self):   self._run_script("run.py", extra_args=["--images-only"])

    def _run_player_download(self, player_name: str):
        """Download photo for a single player."""
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
                env["PYTHONUNBUFFERED"]  = "1"
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

    # ── Trigger AE comp refresh ───────────────────────────────────

    def _try_refresh_ae_comps(self):
        """Incearca sa ruleze refresh_comps.jsx in AE daca e deschis."""
        script_path = str(BASE_DIR / "refresh_comps.jsx")
        if IS_MAC:
            ae_names = [
                "Adobe After Effects (Beta)",
                "Adobe After Effects 2025",
                "Adobe After Effects 2024",
                "Adobe After Effects 2023",
                "Adobe After Effects",
            ]
            for ae_name in ae_names:
                try:
                    escaped = script_path.replace('"', '\\"')
                    r = subprocess.run(
                        ["osascript", "-e",
                         f'tell application "{ae_name}" to do script "{escaped}"'],
                        capture_output=True, timeout=8
                    )
                    if r.returncode == 0:
                        self._log("  ✓ AE compositions updated via osascript.\n")
                        return
                except Exception:
                    pass
            self._log("  ℹ After Effects not detected — open the AE panel and press "
                      "↻ Refresh Stats there to update compositions.\n")
        elif IS_WIN:
            updated = False
            try:
                import importlib
                win32com = importlib.import_module("win32com.client")
                ae = win32com.GetActiveObject("AfterEffects.Application")
                ae.DoScript(script_path)
                self._log("  ✓ AE compositions updated via COM.\n")
                updated = True
            except ImportError:
                pass
            except Exception:
                pass
            if not updated:
                self._log("  ℹ After Effects not detected — open the AE panel and press "
                          "↻ Refresh Stats there to update compositions.\n")

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
            c_avail, c_local, c_remote = updater.check_for_update(timeout=8)
            try:
                t_avail, _tl, _tr = updater.check_template_update(timeout=8)
            except Exception:
                t_avail = False
            if c_avail or t_avail:
                self.after(0, self._show_update_banner, c_avail, c_local, c_remote, t_avail)
        except Exception:
            pass

    def _show_update_banner(self, code_avail: bool, local: str, remote: str, tpl_avail: bool = False):
        self._code_update = (code_avail, local, remote)
        self._tpl_update_available = tpl_avail
        if self._update_banner:
            self._update_banner.destroy()
        banner = ttk.Frame(self, padding=(PAD, 4, PAD, 4))
        self._update_banner = banner
        if code_avail and tpl_avail:
            txt = f"⬆  Update available: v{local}  →  v{remote}   (+ AE template)"
        elif code_avail:
            txt = f"⬆  Update available: v{local}  →  v{remote}"
        else:
            txt = "⬆  After Effects template update available"
        ttk.Label(banner, text=txt,
                  font=(UI, 11), foreground="#30d158").pack(side="left")
        ttk.Button(banner, text="Update now",
                   command=lambda: self._do_update(remote),
                   **self._btn_kw("success")).pack(side="left", padx=(12, 0))
        ttk.Button(banner, text="✕", command=banner.destroy,
                   **self._btn_kw("light")).pack(side="right")
        banner.pack(fill="x", after=self._hdr_sep)

    def _check_update_manual(self):
        try: self.btn_check_update.configure(text="Checking...")
        except Exception: pass
        self.btn_check_update.state(["disabled"])
        self.update_idletasks()

        def worker():
            try:
                import updater
                available, local, remote = updater.check_for_update(timeout=12)
                try:
                    t_avail, _tl, _tr = updater.check_template_update(timeout=12)
                except Exception:
                    t_avail = False
            except Exception as e:
                self.after(0, lambda: self._update_check_result(False, "?", "?", str(e), False))
                return
            self.after(0, lambda: self._update_check_result(available, local, remote, "", t_avail))

        threading.Thread(target=worker, daemon=True).start()

    def _update_check_result(self, available: bool, local: str, remote: str, error: str = "", tpl_avail: bool = False):
        self.btn_check_update.state(["!disabled"])
        try: self.btn_check_update.configure(text="Check for Updates")
        except Exception: pass
        if error:
            self.status_var.set(f"Update check failed: {error}")
            return
        if available or tpl_avail:
            self._show_update_banner(available, local, remote, tpl_avail)
            if available and tpl_avail:
                self.status_var.set(f"⬆ Update available: v{local} → v{remote} (+ template)")
            elif available:
                self.status_var.set(f"⬆ Update available: v{local} → v{remote}")
            else:
                self.status_var.set("⬆ After Effects template update available")
        else:
            msg = "Could not reach GitHub." if remote == "?" else f"✓ Already up to date (v{local})."
            self.status_var.set(msg)

    def _do_update(self, remote: str):
        import tkinter.messagebox as mb
        if self._running:
            mb.showwarning("Update", "Please stop the current run before updating.")
            return
        code_avail = self._code_update[0]
        tpl_avail  = self._tpl_update_available
        _what = []
        if code_avail: _what.append(f"app files (v{remote})")
        if tpl_avail:  _what.append("After Effects template")
        ok = mb.askyesno("Update",
                         "Download and install:\n  • " + "\n  • ".join(_what) +
                         "\n\nMatch data is safe."
                         + ("\n\nThe AE template will be replaced directly." if tpl_avail else "")
                         + "\n\nRestart required after update.", icon="question")
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
                updated, failed = [], []
                if code_avail:
                    def on_progress(current, total, name, ok):
                        status = "✓" if ok else "✗"
                        self.after(0, progress_var.set, f"[{current}/{total}] {status}  {name}")
                    updated, failed, _ae_done = updater.apply_update(on_progress)

                tpl_line = ""
                if tpl_avail:
                    self.after(0, progress_var.set, "Updating After Effects template...")
                    tok, tmsg = updater.apply_template_update(
                        lambda m: self.after(0, progress_var.set, m))
                    tpl_line = "✓ AE template updated." if tok else f"⚠ Template update failed: {tmsg}"

                self.after(0, prog_win.destroy)
                lines = []
                if code_avail:
                    lines.append(f"✓ Updated {len(updated)} file(s).")
                    if failed:
                        lines.append(f"⚠ {len(failed)} file(s) failed.")
                if code_avail and _ae_done:
                    lines.append("✓ After Effects panel updated (restart AE to load it).")
                if tpl_line:
                    lines.append(tpl_line)
                # Restart needed only if app files changed
                if code_avail:
                    lines.append("\nThe app will now close. Please reopen it.")
                msg = "\n".join(lines)
                fn = mb.showwarning if (failed or (tpl_avail and "failed" in tpl_line)) else mb.showinfo

                def _finish():
                    fn("Update", msg)
                    if code_avail:
                        self.destroy()
                    else:
                        if self._update_banner:
                            self._update_banner.destroy()
                            self._update_banner = None
                        self._tpl_update_available = False
                        self.status_var.set("✓ Template updated.")

                self.after(0, _finish)
                if self._update_banner and code_avail:
                    self._update_banner = None
            except Exception as e:
                self.after(0, prog_win.destroy)
                self.after(0, lambda: mb.showerror("Update failed", str(e)))

        threading.Thread(target=worker, daemon=True).start()





if __name__ == "__main__":
    app = App()
    app.mainloop()
