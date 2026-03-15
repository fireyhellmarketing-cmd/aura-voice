"""AURA VOICE — Embedded shell terminal panel."""

import os
import platform
import queue
import shlex
import subprocess
import threading
from pathlib import Path
from typing import Optional

import customtkinter as ctk

from assets.styles import (
    BG, PANEL, CARD, CARD_HOVER, INPUT_BG,
    ACCENT, ACCENT_DIM,
    TEXT, TEXT_SUB, TEXT_MUTED,
    BORDER, BORDER_LIGHT,
    SUCCESS, ERROR,
    FONTS, PAD, RADIUS,
    TERMINAL_HEIGHT_EXPANDED, TERMINAL_HEIGHT_COLLAPSED,
)


# ─── Terminal Colors ────────────────────────────────────────────────────────────
T_BG     = "#0a0a0a"
T_FG     = "#00ff88"
T_ERR    = "#ff4444"
T_ECHO   = "#94a3b8"
T_SYS    = "#7c3aed"
T_WARN   = "#f59e0b"


# ─── Terminal Widget ────────────────────────────────────────────────────────────

class TerminalWidget(ctk.CTkFrame):
    """
    Collapsible bottom terminal panel.

    Features:
    - Real shell command execution via subprocess.Popen
    - Non-blocking stdout/stderr reading in background threads
    - Output posted to Tkinter via a thread-safe queue
    - Colour-coded: green for stdout, red for stderr, dim for echo
    - venv-aware prompt: shows [aura_voice venv] if venv is active
    - Expand / Collapse / Clear buttons in the header
    - write(text, color) method for the app to print messages
    """

    # Shell detection
    _SHELL = os.environ.get("SHELL", "/bin/zsh") if platform.system() != "Windows" else "cmd.exe"

    def __init__(
        self,
        parent,
        cwd: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(parent, fg_color=PANEL, corner_radius=0, **kwargs)

        # Working directory
        self._cwd = cwd or str(
            Path(__file__).resolve().parent.parent  # aura_voice/
        )

        self._expanded  = True
        self._queue:    queue.Queue = queue.Queue()
        self._proc:     Optional[subprocess.Popen] = None
        self._running   = False
        self._history:  list[str] = []
        self._hist_idx  = -1

        self._build()
        self._start_queue_poll()

    # ── Build ──────────────────────────────────────────────────────────────────

    def _build(self):
        # ── Header bar ──
        self._header = ctk.CTkFrame(
            self, fg_color=CARD, corner_radius=0, height=TERMINAL_HEIGHT_COLLAPSED,
        )
        self._header.pack(fill="x")
        self._header.pack_propagate(False)

        # Shell indicator
        shell_name = Path(self._SHELL).name
        ctk.CTkLabel(
            self._header,
            text=f"  Terminal  ",
            font=FONTS["sm_bold"],
            text_color=TEXT_SUB,
        ).pack(side="left", pady=8)

        ctk.CTkLabel(
            self._header,
            text=f"  {shell_name}  ",
            font=FONTS["xs"],
            text_color=T_FG,
            fg_color=CARD_HOVER,
            corner_radius=RADIUS["full"],
        ).pack(side="left", pady=8)

        # Venv badge
        in_venv = (
            os.environ.get("VIRTUAL_ENV")
            or os.environ.get("CONDA_DEFAULT_ENV")
        )
        if in_venv:
            ctk.CTkLabel(
                self._header,
                text="  aura_voice venv  ",
                font=FONTS["xs"],
                text_color=T_SYS,
                fg_color=CARD_HOVER,
                corner_radius=RADIUS["full"],
            ).pack(side="left", padx=4, pady=8)

        # Clear button
        ctk.CTkButton(
            self._header,
            text="✕ Clear",
            width=70, height=26,
            fg_color="transparent",
            hover_color=CARD_HOVER,
            text_color=TEXT_MUTED,
            corner_radius=RADIUS["sm"],
            font=FONTS["xs"],
            command=self.clear,
        ).pack(side="right", padx=4, pady=8)

        # Collapse / Expand
        self._toggle_btn = ctk.CTkButton(
            self._header,
            text="▼ Collapse",
            width=90, height=26,
            fg_color="transparent",
            hover_color=CARD_HOVER,
            text_color=TEXT_MUTED,
            corner_radius=RADIUS["sm"],
            font=FONTS["xs"],
            command=self._toggle,
        )
        self._toggle_btn.pack(side="right", padx=(0, 4), pady=8)

        # ── Terminal display (CTkTextbox) ──
        self._display = ctk.CTkTextbox(
            self,
            height=TERMINAL_HEIGHT_EXPANDED - TERMINAL_HEIGHT_COLLAPSED - 40,
            fg_color=T_BG,
            text_color=T_FG,
            font=FONTS["mono_sm"],
            corner_radius=0,
            wrap="word",
            border_width=0,
        )
        self._display.pack(fill="x", expand=False)
        self._display.configure(state="disabled")

        # Configure text tags for color coding
        self._display._textbox.tag_configure("stdout", foreground=T_FG)
        self._display._textbox.tag_configure("stderr", foreground=T_ERR)
        self._display._textbox.tag_configure("echo",   foreground=T_ECHO)
        self._display._textbox.tag_configure("system", foreground=T_SYS)
        self._display._textbox.tag_configure("warn",   foreground=T_WARN)

        # ── Input row ──
        self._input_row = ctk.CTkFrame(self, fg_color=T_BG, corner_radius=0)
        self._input_row.pack(fill="x")

        self._prompt_label = ctk.CTkLabel(
            self._input_row,
            text=self._make_prompt(),
            font=FONTS["mono_sm"],
            text_color=T_SYS,
        )
        self._prompt_label.pack(side="left", padx=(8, 0))

        self._input_entry = ctk.CTkEntry(
            self._input_row,
            fg_color=T_BG,
            border_width=0,
            text_color=TEXT,
            font=FONTS["mono_sm"],
            placeholder_text="Type a command…",
            placeholder_text_color="#334155",
        )
        self._input_entry.pack(side="left", fill="x", expand=True, padx=4, pady=4)
        self._input_entry.bind("<Return>",   self._on_enter)
        self._input_entry.bind("<Up>",       self._history_prev)
        self._input_entry.bind("<Down>",     self._history_next)
        self._input_entry.bind("<Control-c>", self._send_interrupt)
        self._input_entry.bind("<Control-l>", lambda e: self.clear())

        # Welcome message
        self._print_sys(
            f"AURA VOICE v2 — Terminal  [{shell_name}]  cwd: {self._cwd}\n"
            "Type any shell command. Ctrl+C to interrupt. Ctrl+L to clear.\n"
        )

    # ── Prompt ─────────────────────────────────────────────────────────────────

    def _make_prompt(self) -> str:
        in_venv = os.environ.get("VIRTUAL_ENV") or os.environ.get("CONDA_DEFAULT_ENV")
        prefix  = "[aura_voice venv] " if in_venv else ""
        # Show shortened cwd
        cwd = self._cwd
        home = str(Path.home())
        if cwd.startswith(home):
            cwd = "~" + cwd[len(home):]
        return f"{prefix}{cwd} $ "

    def _update_prompt(self):
        self._prompt_label.configure(text=self._make_prompt())

    # ── Toggle expand/collapse ─────────────────────────────────────────────────

    def _toggle(self):
        self._expanded = not self._expanded
        if self._expanded:
            self._display.pack(fill="x", expand=False)
            self._input_row.pack(fill="x")
            self._toggle_btn.configure(text="▼ Collapse")
            self.configure(height=TERMINAL_HEIGHT_EXPANDED)
        else:
            self._display.pack_forget()
            self._input_row.pack_forget()
            self._toggle_btn.configure(text="▲ Expand")
            self.configure(height=TERMINAL_HEIGHT_COLLAPSED)

    def expand(self):
        if not self._expanded:
            self._toggle()

    def collapse(self):
        if self._expanded:
            self._toggle()

    # ── Output writing ─────────────────────────────────────────────────────────

    def _write_to_display(self, text: str, tag: str = "stdout"):
        """Write text with a color tag to the display textbox (main thread only)."""
        self._display.configure(state="normal")
        self._display._textbox.insert("end", text, tag)
        self._display._textbox.see("end")
        self._display.configure(state="disabled")

    def write(self, text: str, color: str = T_FG):
        """
        Public method: let the app print a message to the terminal.

        color can be: "green", "red", "blue", "yellow", or a hex string.
        """
        color_map = {
            "green":   "stdout",
            "red":     "stderr",
            "yellow":  "warn",
            "blue":    "system",
            "grey":    "echo",
            "gray":    "echo",
        }
        tag = color_map.get(color.lower(), "stdout")
        # Post to queue so it's safe from any thread
        self._queue.put((text, tag))

    def _print_sys(self, text: str):
        self._queue.put((text, "system"))

    def _print_echo(self, text: str):
        self._queue.put((text, "echo"))

    def _print_err(self, text: str):
        self._queue.put((text, "stderr"))

    def _print_out(self, text: str):
        self._queue.put((text, "stdout"))

    def clear(self):
        self._display.configure(state="normal")
        self._display.delete("0.0", "end")
        self._display.configure(state="disabled")

    # ── Queue polling (main thread) ────────────────────────────────────────────

    def _start_queue_poll(self):
        self._poll_queue()

    def _poll_queue(self):
        try:
            while True:
                text, tag = self._queue.get_nowait()
                self._write_to_display(text, tag)
        except queue.Empty:
            pass
        self.after(40, self._poll_queue)

    # ── Command execution ──────────────────────────────────────────────────────

    def _on_enter(self, event=None):
        cmd = self._input_entry.get().strip()
        self._input_entry.delete(0, "end")

        if not cmd:
            return

        # History
        if not self._history or self._history[-1] != cmd:
            self._history.append(cmd)
        self._hist_idx = len(self._history)

        # Echo
        self._print_echo(f"{self._make_prompt()}{cmd}\n")

        # Handle builtins
        if cmd.startswith("cd "):
            self._builtin_cd(cmd[3:].strip())
        elif cmd == "cd":
            self._builtin_cd(str(Path.home()))
        elif cmd in ("clear", "cls"):
            self.clear()
        elif cmd == "exit":
            self._print_sys("[Session closed]\n")
        else:
            self._run_external(cmd)

    def _builtin_cd(self, path: str):
        target = Path(path).expanduser()
        if not target.is_absolute():
            target = Path(self._cwd) / target
        target = target.resolve()
        if target.is_dir():
            self._cwd = str(target)
            self._update_prompt()
        else:
            self._print_err(f"cd: no such directory: {path}\n")

    def _run_external(self, cmd: str):
        """Run a shell command non-blocking via subprocess.Popen."""
        if self._proc and self._proc.poll() is None:
            self._print_err("[!] Previous command still running. Ctrl+C to cancel.\n")
            return

        self._running = True
        t = threading.Thread(
            target=self._exec_thread,
            args=(cmd,),
            daemon=True,
        )
        t.start()

    def _exec_thread(self, cmd: str):
        """Execute cmd in a thread, stream output to the queue."""
        env = os.environ.copy()
        env["TERM"] = "dumb"

        # Determine shell / args
        if platform.system() == "Windows":
            shell_args = ["cmd.exe", "/c", cmd]
        else:
            shell_args = [self._SHELL, "-c", cmd]

        try:
            self._proc = subprocess.Popen(
                shell_args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=self._cwd,
                env=env,
                text=True,
                bufsize=1,
            )

            # Stream stdout
            def read_stdout():
                for line in self._proc.stdout:
                    self._print_out(line)
                self._proc.stdout.close()

            # Stream stderr
            def read_stderr():
                for line in self._proc.stderr:
                    self._print_err(line)
                self._proc.stderr.close()

            t_out = threading.Thread(target=read_stdout, daemon=True)
            t_err = threading.Thread(target=read_stderr, daemon=True)
            t_out.start()
            t_err.start()
            t_out.join()
            t_err.join()

            ret = self._proc.wait()
            if ret != 0:
                self._print_err(f"\n[Process exited with code {ret}]\n")
            else:
                self._print_sys(f"[Done — exit 0]\n")

        except FileNotFoundError:
            self._print_err(f"Command not found: {cmd.split()[0]}\n")
        except Exception as exc:
            self._print_err(f"Error: {exc}\n")
        finally:
            self._running = False
            self._proc    = None

    def _send_interrupt(self, event=None):
        """Send SIGINT to the running process (Ctrl+C)."""
        if self._proc and self._proc.poll() is None:
            import signal
            try:
                self._proc.send_signal(signal.SIGINT)
                self._print_sys("\n[Interrupted]\n")
            except Exception:
                self._proc.kill()
                self._print_sys("\n[Killed]\n")

    # ── History navigation ─────────────────────────────────────────────────────

    def _history_prev(self, event=None):
        if not self._history:
            return
        self._hist_idx = max(0, self._hist_idx - 1)
        self._set_input(self._history[self._hist_idx])

    def _history_next(self, event=None):
        if not self._history:
            return
        self._hist_idx = min(len(self._history), self._hist_idx + 1)
        if self._hist_idx == len(self._history):
            self._set_input("")
        else:
            self._set_input(self._history[self._hist_idx])

    def _set_input(self, text: str):
        self._input_entry.delete(0, "end")
        self._input_entry.insert(0, text)
        self._input_entry.icursor("end")

    # ── Cleanup ────────────────────────────────────────────────────────────────

    def destroy(self):
        if self._proc and self._proc.poll() is None:
            try:
                self._proc.kill()
            except Exception:
                pass
        super().destroy()
