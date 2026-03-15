"""AURA VOICE v2 — Startup wizard: hardware detection + model selection."""

import json
import threading
import time
from pathlib import Path
from typing import Callable, Optional

import customtkinter as ctk

# Lazy imports to avoid circular deps at load time
from assets.styles import (
    APP_NAME, APP_VERSION,
    BG, SIDEBAR, PANEL, CARD, CARD_HOVER, INPUT_BG,
    ACCENT, ACCENT_HOVER, ACCENT_DIM,
    ACCENT2, ACCENT2_HOVER,
    TEXT, TEXT_SUB, TEXT_MUTED,
    SUCCESS, SUCCESS_BG, ERROR, ERROR_BG, WARNING,
    BORDER, BORDER_LIGHT,
    FONTS, PAD, RADIUS,
    btn_primary, btn_secondary, card_frame,
)
from core.hardware_detect import detect_hardware, HardwareInfo
from core.model_manager import (
    MODEL_CATALOG, get_compatible_models,
    is_model_downloaded, save_config, load_config,
    CONFIG_PATH,
)


# ─── Wizard Window ─────────────────────────────────────────────────────────────

class StartupWizard(ctk.CTkToplevel):
    """
    Three-step onboarding wizard:
      Page 0 — Welcome + Hardware Detection
      Page 1 — Model Selection
      Page 2 — Ready / Launch
    """

    PAGES = ["Welcome", "Select Model", "Ready"]

    def __init__(self, on_complete: Callable[[dict], None]):
        super().__init__()

        self.on_complete  = on_complete
        self.config_data  = load_config()
        self.hardware: Optional[HardwareInfo] = None
        self.compatible_models: dict = {}
        self.selected_model_name: str = self.config_data.get(
            "selected_model", "XTTS v2 — Multilingual Pro"
        )
        self._download_thread: Optional[threading.Thread] = None
        self._spinner_running = False
        self._spinner_idx = 0
        self._page_index = 0
        self._model_card_widgets: dict = {}  # name -> frame widget

        self.title(f"{APP_NAME} v{APP_VERSION} — Setup")
        self.geometry("720x560")
        self.minsize(680, 520)
        self.resizable(True, True)
        self.configure(fg_color=BG)
        self.grab_set()
        self.focus_set()

        self._build_ui()
        self._show_page(0)
        self._start_hw_detection()
        self._center()

    # ── Centering ──────────────────────────────────────────────────────────────

    def _center(self):
        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        w  = self.winfo_width()
        h  = self.winfo_height()
        self.geometry(f"+{(sw - w) // 2}+{(sh - h) // 2}")

    # ── UI Construction ────────────────────────────────────────────────────────

    def _build_ui(self):
        # ── Header ──
        self.header = ctk.CTkFrame(self, fg_color=SIDEBAR, corner_radius=0, height=64)
        self.header.pack(fill="x", side="top")
        self.header.pack_propagate(False)

        ctk.CTkLabel(
            self.header,
            text=f"  {APP_NAME}",
            font=FONTS["2xl_bold"],
            text_color=TEXT,
        ).place(x=24, y=14)

        ctk.CTkLabel(
            self.header,
            text=f"v{APP_VERSION}",
            font=FONTS["sm"],
            text_color=TEXT_MUTED,
        ).place(x=24, y=42)

        # Step indicator dots
        self._step_dots: list[ctk.CTkLabel] = []
        dot_frame = ctk.CTkFrame(self.header, fg_color="transparent")
        dot_frame.place(relx=0.5, rely=0.5, anchor="center")
        for i, label in enumerate(self.PAGES):
            dot = ctk.CTkLabel(
                dot_frame,
                text=f"  {i + 1}. {label}  ",
                font=FONTS["sm"],
                text_color=TEXT_MUTED,
                fg_color="transparent",
            )
            dot.grid(row=0, column=i * 2, padx=2)
            if i < len(self.PAGES) - 1:
                ctk.CTkLabel(
                    dot_frame, text="›",
                    font=FONTS["md"], text_color=TEXT_MUTED,
                ).grid(row=0, column=i * 2 + 1, padx=0)
            self._step_dots.append(dot)

        # ── Content area (swappable pages) ──
        self.content = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        self.content.pack(fill="both", expand=True)

        # Build all pages
        self._page_frames: list[ctk.CTkFrame] = []
        self._page_frames.append(self._build_welcome_page())
        self._page_frames.append(self._build_model_page())
        self._page_frames.append(self._build_ready_page())

        # ── Footer nav ──
        self.footer = ctk.CTkFrame(self, fg_color=SIDEBAR, corner_radius=0, height=56)
        self.footer.pack(fill="x", side="bottom")
        self.footer.pack_propagate(False)

        self.btn_back = ctk.CTkButton(
            self.footer,
            text="← Back",
            width=110, height=36,
            **btn_secondary(),
            command=self._go_back,
        )
        self.btn_back.place(x=20, rely=0.5, anchor="w")

        self.btn_next = ctk.CTkButton(
            self.footer,
            text="Next →",
            width=140, height=36,
            **btn_primary(),
            command=self._go_next,
        )
        self.btn_next.place(relx=1.0, x=-20, rely=0.5, anchor="e")

    # ── Page 0: Welcome / Hardware ─────────────────────────────────────────────

    def _build_welcome_page(self) -> ctk.CTkFrame:
        frame = ctk.CTkFrame(self.content, fg_color="transparent")

        # Hero title
        ctk.CTkLabel(
            frame,
            text="Welcome to AURA VOICE",
            font=FONTS["3xl_bold"],
            text_color=TEXT,
        ).pack(pady=(32, 4))

        ctk.CTkLabel(
            frame,
            text="100% offline · No API keys · No subscriptions",
            font=FONTS["base"],
            text_color=TEXT_MUTED,
        ).pack()

        # Separator
        sep = ctk.CTkFrame(frame, fg_color=BORDER, height=1)
        sep.pack(fill="x", padx=40, pady=20)

        # Hardware card
        self.hw_card = ctk.CTkFrame(frame, **card_frame(), width=520)
        self.hw_card.pack(padx=40, pady=0, fill="x")

        hw_header = ctk.CTkFrame(self.hw_card, fg_color="transparent")
        hw_header.pack(fill="x", padx=PAD["card"], pady=(PAD["card"], 0))

        ctk.CTkLabel(
            hw_header,
            text="Your Hardware",
            font=FONTS["md_bold"],
            text_color=TEXT,
        ).pack(side="left")

        self.hw_status_badge = ctk.CTkLabel(
            hw_header,
            text="  Detecting…  ",
            font=FONTS["xs"],
            text_color=ACCENT2,
            fg_color=CARD_HOVER,
            corner_radius=RADIUS["full"],
            width=90, height=22,
        )
        self.hw_status_badge.pack(side="right")

        # Spinner label
        self.spinner_label = ctk.CTkLabel(
            self.hw_card,
            text="⠋  Scanning hardware…",
            font=FONTS["mono_sm"],
            text_color=TEXT_SUB,
        )
        self.spinner_label.pack(pady=20)

        # Hardware detail rows (hidden until detected)
        self.hw_detail_frame = ctk.CTkFrame(self.hw_card, fg_color="transparent")

        self.hw_rows: dict[str, ctk.CTkLabel] = {}
        fields = [
            ("cpu",    "CPU"),
            ("ram",    "RAM"),
            ("gpu",    "GPU / Accel"),
            ("device", "Recommended Device"),
        ]
        for key, label_text in fields:
            row = ctk.CTkFrame(self.hw_detail_frame, fg_color="transparent")
            row.pack(fill="x", padx=PAD["card"], pady=3)

            ctk.CTkLabel(
                row, text=label_text,
                font=FONTS["sm"], text_color=TEXT_MUTED,
                width=130, anchor="w",
            ).pack(side="left")

            val_label = ctk.CTkLabel(
                row, text="—",
                font=FONTS["sm_bold"], text_color=TEXT_SUB,
                anchor="w",
            )
            val_label.pack(side="left", fill="x", expand=True)
            self.hw_rows[key] = val_label

        # Device recommendation badge
        self.device_badge = ctk.CTkLabel(
            self.hw_detail_frame,
            text="",
            font=FONTS["sm_bold"],
            text_color=SUCCESS,
            fg_color=SUCCESS_BG,
            corner_radius=RADIUS["md"],
            height=28,
        )

        return frame

    # ── Page 1: Model Selection ────────────────────────────────────────────────

    def _build_model_page(self) -> ctk.CTkFrame:
        frame = ctk.CTkFrame(self.content, fg_color="transparent")

        ctk.CTkLabel(
            frame,
            text="Select a Voice Model",
            font=FONTS["2xl_bold"],
            text_color=TEXT,
        ).pack(pady=(28, 4))

        ctk.CTkLabel(
            frame,
            text="Models are cached locally — only downloaded once.",
            font=FONTS["base"],
            text_color=TEXT_MUTED,
        ).pack()

        sep = ctk.CTkFrame(frame, fg_color=BORDER, height=1)
        sep.pack(fill="x", padx=40, pady=16)

        # Scrollable model list
        self.model_scroll = ctk.CTkScrollableFrame(
            frame,
            fg_color="transparent",
            scrollbar_button_color=BORDER,
            scrollbar_button_hover_color=BORDER_LIGHT,
        )
        self.model_scroll.pack(fill="both", expand=True, padx=32, pady=(0, 8))

        self._model_card_widgets = {}
        self._build_model_cards()

        return frame

    def _build_model_cards(self):
        """Populate model cards in the scrollable frame."""
        # Clear old cards
        for w in self.model_scroll.winfo_children():
            w.destroy()
        self._model_card_widgets.clear()

        catalog_items = list(MODEL_CATALOG.items())
        for name, spec in catalog_items:
            self._build_one_model_card(name, spec)

    def _build_one_model_card(self, name: str, spec: dict):
        downloaded = is_model_downloaded(spec["model_id"])
        is_selected = (name == self.selected_model_name)

        border_color = ACCENT if is_selected else BORDER
        card = ctk.CTkFrame(
            self.model_scroll,
            fg_color=CARD_HOVER if is_selected else CARD,
            corner_radius=RADIUS["lg"],
            border_color=border_color,
            border_width=2 if is_selected else 1,
        )
        card.pack(fill="x", padx=4, pady=5)
        self._model_card_widgets[name] = card

        # Top row: name + badges
        top = ctk.CTkFrame(card, fg_color="transparent")
        top.pack(fill="x", padx=PAD["card"], pady=(PAD["card"], 0))

        ctk.CTkLabel(
            top, text=name,
            font=FONTS["base_bold"], text_color=TEXT,
        ).pack(side="left")

        if spec.get("recommended"):
            ctk.CTkLabel(
                top, text="  RECOMMENDED  ",
                font=FONTS["xs_bold"],
                text_color=ACCENT2,
                fg_color=CARD,
                corner_radius=RADIUS["full"],
            ).pack(side="right", padx=4)

        if downloaded:
            ctk.CTkLabel(
                top, text="  ✓ Ready  ",
                font=FONTS["xs_bold"],
                text_color=SUCCESS,
                fg_color=SUCCESS_BG,
                corner_radius=RADIUS["full"],
            ).pack(side="right", padx=4)

        # Quality + size row
        mid = ctk.CTkFrame(card, fg_color="transparent")
        mid.pack(fill="x", padx=PAD["card"], pady=2)

        ctk.CTkLabel(
            mid, text=spec.get("quality_label", "★★★☆☆"),
            font=FONTS["sm"], text_color=ACCENT2,
        ).pack(side="left")

        ctk.CTkLabel(
            mid, text=f"  {spec.get('size_gb', 0):.2f} GB",
            font=FONTS["sm"], text_color=TEXT_MUTED,
        ).pack(side="left", padx=6)

        langs = spec.get("languages", [])
        lang_str = ", ".join(langs[:4])
        if len(langs) > 4:
            lang_str += f" +{len(langs)-4}"
        ctk.CTkLabel(
            mid, text=lang_str,
            font=FONTS["xs"], text_color=TEXT_MUTED,
        ).pack(side="left", padx=4)

        # Description
        ctk.CTkLabel(
            card, text=spec.get("description", ""),
            font=FONTS["sm"], text_color=TEXT_SUB,
            wraplength=480, justify="left",
        ).pack(anchor="w", padx=PAD["card"], pady=(2, 0))

        # Action row
        action_row = ctk.CTkFrame(card, fg_color="transparent")
        action_row.pack(fill="x", padx=PAD["card"], pady=(6, PAD["lg"]))

        # Select button
        select_btn = ctk.CTkButton(
            action_row,
            text="✓ Selected" if is_selected else "Select",
            width=100, height=30,
            fg_color=ACCENT if is_selected else CARD_HOVER,
            hover_color=ACCENT_HOVER,
            text_color=TEXT,
            corner_radius=RADIUS["sm"],
            font=FONTS["sm_bold"],
            command=lambda n=name: self._select_model(n),
        )
        select_btn.pack(side="left")

        # Download progress (hidden by default)
        progress_frame = ctk.CTkFrame(action_row, fg_color="transparent")
        progress_frame.pack(side="left", padx=8, fill="x", expand=True)
        progress_frame.pack_forget()

        progress_bar = ctk.CTkProgressBar(
            progress_frame,
            height=6,
            fg_color=PANEL,
            progress_color=ACCENT,
            corner_radius=3,
        )
        progress_bar.set(0)
        progress_bar.pack(fill="x")

        progress_label = ctk.CTkLabel(
            progress_frame,
            text="Downloading…",
            font=FONTS["xs"], text_color=TEXT_MUTED,
        )
        progress_label.pack(anchor="w")

        # Download button (if not downloaded)
        if not downloaded:
            dl_btn = ctk.CTkButton(
                action_row,
                text=f"⬇ Download  ({spec.get('size_gb', 0):.2f} GB)",
                width=180, height=30,
                fg_color=ACCENT_DIM,
                hover_color=ACCENT,
                text_color=TEXT,
                corner_radius=RADIUS["sm"],
                font=FONTS["sm"],
                command=lambda n=name, s=spec, pf=progress_frame,
                               pb=progress_bar, pl=progress_label: (
                    self._start_download(n, s, pf, pb, pl)
                ),
            )
            dl_btn.pack(side="left", padx=4)

        # Clicking the card body selects it
        for child in [card, top, mid]:
            child.bind("<Button-1>", lambda e, n=name: self._select_model(n))

    def _select_model(self, name: str):
        """Highlight selected model card and update state."""
        self.selected_model_name = name
        # Rebuild cards to reflect new selection
        self._build_model_cards()

    def _start_download(
        self, name: str, spec: dict,
        progress_frame, progress_bar, progress_label,
    ):
        """Begin downloading a model in a background thread."""
        if self._download_thread and self._download_thread.is_alive():
            return  # already downloading

        progress_frame.pack(side="left", padx=8, fill="x", expand=True)

        def run_download():
            try:
                from TTS.api import TTS
                progress_label.configure(text="Initialising Coqui TTS…")
                progress_bar.set(0.05)
                # TTS constructor with download triggers the model fetch
                tts = TTS(model_name=spec["model_id"], progress_bar=False, gpu=False)
                progress_bar.set(1.0)
                progress_label.configure(text="✓ Download complete")
                self.after(400, self._build_model_cards)
            except Exception as exc:
                progress_label.configure(text=f"Error: {exc}")
                progress_bar.set(0)

        self._download_thread = threading.Thread(target=run_download, daemon=True)
        self._download_thread.start()

    # ── Page 2: Ready ──────────────────────────────────────────────────────────

    def _build_ready_page(self) -> ctk.CTkFrame:
        frame = ctk.CTkFrame(self.content, fg_color="transparent")

        # Large checkmark / success icon
        ctk.CTkLabel(
            frame,
            text="✦",
            font=(FONTS["3xl"][0], 72),
            text_color=ACCENT,
        ).pack(pady=(40, 8))

        ctk.CTkLabel(
            frame,
            text="Setup Complete!",
            font=FONTS["3xl_bold"],
            text_color=TEXT,
        ).pack(pady=4)

        ctk.CTkLabel(
            frame,
            text="AURA VOICE is ready to use.",
            font=FONTS["lg"],
            text_color=TEXT_SUB,
        ).pack(pady=4)

        sep = ctk.CTkFrame(frame, fg_color=BORDER, height=1)
        sep.pack(fill="x", padx=60, pady=20)

        # Summary card
        self.summary_card = ctk.CTkFrame(frame, **card_frame(), width=400)
        self.summary_card.pack(padx=60, pady=0)
        self._build_summary_card()

        return frame

    def _build_summary_card(self):
        for w in self.summary_card.winfo_children():
            w.destroy()

        rows = [
            ("Model",  self.selected_model_name),
            ("Device", self.config_data.get("device", "cpu").upper()),
        ]
        if self.hardware:
            rows.append(("CPU", self.hardware.cpu_name[:40]))
            rows.append(("RAM", f"{self.hardware.ram_gb} GB"))

        for label_text, val_text in rows:
            row = ctk.CTkFrame(self.summary_card, fg_color="transparent")
            row.pack(fill="x", padx=16, pady=4)
            ctk.CTkLabel(
                row, text=label_text,
                font=FONTS["sm"], text_color=TEXT_MUTED,
                width=80, anchor="w",
            ).pack(side="left")
            ctk.CTkLabel(
                row, text=val_text,
                font=FONTS["sm_bold"], text_color=TEXT,
                anchor="w",
            ).pack(side="left")

    # ── Hardware Detection ─────────────────────────────────────────────────────

    def _start_hw_detection(self):
        self._spinner_running = True
        self._animate_spinner()
        t = threading.Thread(target=self._detect_hw_thread, daemon=True)
        t.start()

    def _animate_spinner(self):
        FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        if not self._spinner_running:
            return
        frame = FRAMES[self._spinner_idx % len(FRAMES)]
        self._spinner_idx += 1
        try:
            self.spinner_label.configure(text=f"{frame}  Scanning hardware…")
        except Exception:
            return
        self.after(80, self._animate_spinner)

    def _detect_hw_thread(self):
        try:
            hw = detect_hardware()
        except Exception:
            hw = None
        self.after(0, lambda: self._on_hw_detected(hw))

    def _on_hw_detected(self, hw: Optional[HardwareInfo]):
        self._spinner_running = False
        self.hardware = hw

        try:
            self.spinner_label.pack_forget()
            self.hw_detail_frame.pack(fill="x", pady=(0, PAD["card"]))
        except Exception:
            return

        if hw is None:
            self.hw_status_badge.configure(
                text="  Detection failed  ",
                text_color=ERROR,
            )
            for key in self.hw_rows:
                self.hw_rows[key].configure(text="Unknown")
            return

        # Update rows
        self.hw_rows["cpu"].configure(text=hw.cpu_name[:48])
        self.hw_rows["ram"].configure(text=f"{hw.ram_gb} GB")

        if hw.has_cuda:
            gpu_text = f"{hw.gpu_name}  ({hw.vram_gb} GB VRAM)"
            gpu_color = ACCENT2
        elif hw.has_mps:
            gpu_text  = f"Apple MPS — {hw.gpu_name}"
            gpu_color = SUCCESS
        else:
            gpu_text  = "No dedicated GPU (CPU mode)"
            gpu_color = TEXT_MUTED
        self.hw_rows["gpu"].configure(text=gpu_text, text_color=gpu_color)

        device = hw.recommended_device.upper()
        self.hw_rows["device"].configure(
            text=f"{device}  —  {hw.device_label}",
            text_color=SUCCESS,
        )

        self.hw_status_badge.configure(
            text="  ✓ Detected  ",
            text_color=SUCCESS,
            fg_color=SUCCESS_BG,
        )

        badge_text = {
            "cuda": "  ⚡ NVIDIA GPU Available  ",
            "mps":  "  ⚡ Apple MPS Available  ",
            "cpu":  "  💻 CPU Mode  ",
        }.get(hw.recommended_device, "  CPU Mode  ")
        badge_color = SUCCESS if hw.recommended_device != "cpu" else ACCENT2

        self.device_badge.configure(text=badge_text, text_color=badge_color)
        self.device_badge.pack(padx=PAD["card"], pady=(4, PAD["card"]))

        # Store device in config
        self.config_data["device"] = hw.recommended_device

        # Rebuild model page with compat info
        self.compatible_models = get_compatible_models(hw)

    # ── Navigation ─────────────────────────────────────────────────────────────

    def _show_page(self, index: int):
        for i, frame in enumerate(self._page_frames):
            frame.pack_forget()

        self._page_frames[index].pack(fill="both", expand=True)
        self._page_index = index

        # Update step dot styles
        for i, dot in enumerate(self._step_dots):
            if i == index:
                dot.configure(text_color=ACCENT, font=FONTS["sm_bold"])
            elif i < index:
                dot.configure(text_color=SUCCESS, font=FONTS["sm"])
            else:
                dot.configure(text_color=TEXT_MUTED, font=FONTS["sm"])

        # Update nav buttons
        self.btn_back.configure(state="normal" if index > 0 else "disabled")

        if index == len(self.PAGES) - 1:
            self.btn_next.configure(text="✦ Launch AURA VOICE", width=180)
            self._build_summary_card()
        else:
            self.btn_next.configure(text="Next →", width=140)

    def _go_next(self):
        if self._page_index < len(self.PAGES) - 1:
            self._show_page(self._page_index + 1)
        else:
            self._finish()

    def _go_back(self):
        if self._page_index > 0:
            self._show_page(self._page_index - 1)

    def _finish(self):
        """Save config and call on_complete callback."""
        self.config_data["selected_model"]  = self.selected_model_name
        self.config_data["first_run"]       = False
        if self.hardware:
            self.config_data["device"] = self.hardware.recommended_device

        save_config(self.config_data)
        self.grab_release()
        self.destroy()
        self.on_complete(self.config_data)
