"""AURA VOICE — Left icon sidebar with navigation and tooltips."""

import customtkinter as ctk
from pathlib import Path
from typing import Callable, Optional

from assets.styles import (
    APP_NAME, APP_VERSION,
    SIDEBAR, CARD, CARD_HOVER, ACCENT, ACCENT_DIM,
    TEXT, TEXT_SUB, TEXT_MUTED,
    BORDER,
    FONTS, PAD, RADIUS,
    SIDEBAR_WIDTH,
)

_ASSETS = Path(__file__).resolve().parent.parent / "assets"


# ─── Nav Items ─────────────────────────────────────────────────────────────────
# Icons match the design sheet: waveform-A / doc / history-clock / gear / profile

NAV_ITEMS = [
    ("generate",  "◈",  "Generate"),
    ("history",   "◷",  "History"),
    ("settings",  "⚙",  "Settings"),
    ("about",     "◯",  "About"),
]


def _load_ctk_image(path: Path, size: tuple) -> Optional[ctk.CTkImage]:
    """Load a PNG as a CTkImage, returns None if file missing or Pillow fails."""
    try:
        from PIL import Image
        img = Image.open(str(path)).convert("RGBA")
        return ctk.CTkImage(light_image=img, dark_image=img, size=size)
    except Exception:
        return None


# ─── Tooltip ───────────────────────────────────────────────────────────────────

class _Tooltip:
    """Simple hover tooltip that appears to the right of the sidebar."""

    def __init__(self, parent: ctk.CTkBaseClass, text: str):
        self.parent = parent
        self.text   = text
        self.window: Optional[ctk.CTkToplevel] = None

        parent.bind("<Enter>", self._show)
        parent.bind("<Leave>", self._hide)

    def _show(self, event=None):
        if self.window:
            return
        x = self.parent.winfo_rootx() + self.parent.winfo_width() + 4
        y = self.parent.winfo_rooty() + self.parent.winfo_height() // 2 - 12

        self.window = ctk.CTkToplevel(self.parent)
        self.window.wm_overrideredirect(True)
        self.window.wm_geometry(f"+{x}+{y}")
        self.window.configure(fg_color=CARD)

        ctk.CTkLabel(
            self.window,
            text=f"  {self.text}  ",
            font=FONTS["sm"],
            text_color=TEXT,
            fg_color=CARD,
            corner_radius=RADIUS["sm"],
        ).pack(padx=4, pady=4)

    def _hide(self, event=None):
        if self.window:
            self.window.destroy()
            self.window = None


# ─── Sidebar Widget ────────────────────────────────────────────────────────────

class Sidebar(ctk.CTkFrame):
    """
    Narrow (~58 px) icon sidebar.

    - App logo at the top
    - Nav icon buttons (with tooltips)
    - Active item highlighted with violet left border + dimmer background
    - Version label at the bottom
    """

    def __init__(
        self,
        parent,
        on_nav: Callable[[str], None],
        initial_section: str = "generate",
        **kwargs,
    ):
        super().__init__(
            parent,
            fg_color=SIDEBAR,
            corner_radius=0,
            width=SIDEBAR_WIDTH,
            **kwargs,
        )
        self.pack_propagate(False)
        self.on_nav          = on_nav
        self.active_section  = initial_section
        self._buttons: dict[str, ctk.CTkFrame]  = {}
        self._tooltips: list[_Tooltip]           = []

        self._build()

    # ── Build ──────────────────────────────────────────────────────────────────

    def _build(self):
        # ── App logo / brand area ──
        logo_frame = ctk.CTkFrame(self, fg_color="transparent", height=64)
        logo_frame.pack(fill="x")
        logo_frame.pack_propagate(False)

        # Try logo.png first, fall back to icon.png, then text glyph
        logo_img = (
            _load_ctk_image(_ASSETS / "logo.png",  (36, 36)) or
            _load_ctk_image(_ASSETS / "icon.png",  (36, 36))
        )
        if logo_img:
            ctk.CTkLabel(
                logo_frame,
                text="",
                image=logo_img,
                fg_color="transparent",
            ).place(relx=0.5, rely=0.5, anchor="center")
        else:
            ctk.CTkLabel(
                logo_frame,
                text="◈",
                font=(FONTS["xl"][0], 24),
                text_color=ACCENT,
            ).place(relx=0.5, rely=0.5, anchor="center")

        # Thin separator
        ctk.CTkFrame(self, fg_color=BORDER, height=1).pack(fill="x")

        # ── Nav items area ──
        nav_container = ctk.CTkFrame(self, fg_color="transparent")
        nav_container.pack(fill="x", expand=False, pady=(8, 0))

        for section_id, icon, label in NAV_ITEMS:
            self._build_nav_button(nav_container, section_id, icon, label)

        # ── Spacer ──
        ctk.CTkFrame(self, fg_color="transparent").pack(fill="both", expand=True)

        # Thin separator
        ctk.CTkFrame(self, fg_color=BORDER, height=1).pack(fill="x")

        # ── Version ──
        version_frame = ctk.CTkFrame(self, fg_color="transparent", height=32)
        version_frame.pack(fill="x")
        version_frame.pack_propagate(False)

        ctk.CTkLabel(
            version_frame,
            text=APP_VERSION,
            font=FONTS["xs"],
            text_color=TEXT_MUTED,
        ).place(relx=0.5, rely=0.5, anchor="center")

    def _build_nav_button(
        self,
        parent,
        section_id: str,
        icon: str,
        label: str,
    ):
        is_active = section_id == self.active_section

        # Outer container (holds left-border indicator + button)
        outer = ctk.CTkFrame(parent, fg_color="transparent", height=52)
        outer.pack(fill="x", pady=2)
        outer.pack_propagate(False)

        # Left accent bar
        accent_bar = ctk.CTkFrame(
            outer,
            fg_color=ACCENT if is_active else "transparent",
            width=3,
        )
        accent_bar.pack(side="left", fill="y")

        # Button
        btn = ctk.CTkButton(
            outer,
            text=icon,
            width=SIDEBAR_WIDTH - 3,
            height=52,
            font=(FONTS["xl"][0], 20),
            fg_color=ACCENT_DIM if is_active else "transparent",
            hover_color=CARD_HOVER,
            text_color=ACCENT if is_active else TEXT_MUTED,
            corner_radius=0,
            command=lambda s=section_id: self._on_click(s),
        )
        btn.pack(side="left", fill="both", expand=True)

        # Store references for later highlight updates
        self._buttons[section_id] = {
            "outer":      outer,
            "accent_bar": accent_bar,
            "btn":        btn,
        }

        # Tooltip
        tt = _Tooltip(outer, label)
        self._tooltips.append(tt)

    # ── Interaction ────────────────────────────────────────────────────────────

    def _on_click(self, section_id: str):
        if section_id == self.active_section:
            return
        self._deactivate(self.active_section)
        self._activate(section_id)
        self.active_section = section_id
        self.on_nav(section_id)

    def _activate(self, section_id: str):
        entry = self._buttons.get(section_id)
        if not entry:
            return
        entry["accent_bar"].configure(fg_color=ACCENT)
        entry["btn"].configure(
            fg_color=ACCENT_DIM,
            text_color=ACCENT,
        )

    def _deactivate(self, section_id: str):
        entry = self._buttons.get(section_id)
        if not entry:
            return
        entry["accent_bar"].configure(fg_color="transparent")
        entry["btn"].configure(
            fg_color="transparent",
            text_color=TEXT_MUTED,
        )

    def set_active(self, section_id: str):
        """Programmatically change the active section."""
        if section_id == self.active_section:
            return
        self._deactivate(self.active_section)
        self._activate(section_id)
        self.active_section = section_id
