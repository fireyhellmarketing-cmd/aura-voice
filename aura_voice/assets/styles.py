"""AURA VOICE v2 — Complete design system and style definitions.
Aesthetic: Freepik Pikaso — dark near-black, violet accent, amber highlights.
"""

import platform as _platform

# ─── App Identity ──────────────────────────────────────────────────────────────
APP_NAME    = "AURA VOICE"
APP_VERSION = "2.160326"
APP_TAGLINE = "Your words. Your voice. Locally yours."
FORMAT_ID   = "auravoice_v2"

# ─── Window Geometry ───────────────────────────────────────────────────────────
WINDOW = {
    "width":      900,
    "height":     780,
    "min_width":  760,
    "min_height": 600,
}

# ─── New Design-System Colors (v3 redesign) ────────────────────────────────────
BG_DEEP    = "#0A090F"    # near-black with violet undertone
SURFACE    = "#110F1A"    # cards / inputs
SURFACE2   = "#130F1E"    # slightly lighter surface
ACCENT_HOV = "#9D5CF5"    # hover violet
BORDER     = "#1E1B2E"    # subtle border
BORDER2    = "#2A2540"    # slightly lighter border
TEXT       = "#F1F5F9"    # primary text
TEXT_SUB   = "#9D8FC4"    # secondary / muted
TEXT_DIM   = "#6B6880"    # very muted labels
TEXT_GHOST = "#3D3A52"    # placeholder / ghost
ACCENT_DIM2 = "#5B21B6"   # darker violet for gradients (v3 name avoids clash)

# ─── Color Palette ─────────────────────────────────────────────────────────────
COLORS = {
    # Backgrounds
    "bg":           "#0A090F",
    "sidebar":      "#111118",
    "panel":        "#110F1A",
    "card":         "#130F1E",
    "card_hover":   "#1A1630",
    "input_bg":     "#110F1A",

    # Accents
    "accent":           "#7c3aed",
    "accent_hover":     "#9D5CF5",
    "accent_dim":       "#5B21B6",
    "accent2":          "#f59e0b",
    "accent2_hover":    "#fbbf24",

    # Text
    "text":         "#F1F5F9",
    "text_sub":     "#9D8FC4",
    "text_muted":   "#6B6880",
    "text_dim":     "#3D3A52",

    # Semantic
    "success":      "#10b981",
    "success_bg":   "#064e3b",
    "warning":      "#f59e0b",
    "warning_bg":   "#451a03",
    "error":        "#ef4444",
    "error_bg":     "#450a0a",

    # Borders
    "border":       "#1E1B2E",
    "border_light": "#2A2540",

    # Components
    "scrollbar":        "#1E1B2E",
    "progress_track":   "#1E1B2E",
    "progress_fill":    "#7c3aed",
    "selection":        "#5B21B6",
}

# Flat aliases for convenience
BG            = COLORS["bg"]
SIDEBAR       = COLORS["sidebar"]
PANEL         = COLORS["panel"]
CARD          = COLORS["card"]
CARD_HOVER    = COLORS["card_hover"]
INPUT_BG      = COLORS["input_bg"]
ACCENT        = COLORS["accent"]
ACCENT_HOVER  = COLORS["accent_hover"]
ACCENT_DIM    = COLORS["accent_dim"]
ACCENT2       = COLORS["accent2"]
ACCENT2_HOVER = COLORS["accent2_hover"]
TEXT_MUTED    = COLORS["text_muted"]
SUCCESS       = COLORS["success"]
SUCCESS_BG    = COLORS["success_bg"]
WARNING       = COLORS["warning"]
WARNING_BG    = COLORS["warning_bg"]
ERROR         = COLORS["error"]
ERROR_BG      = COLORS["error_bg"]
BORDER_LIGHT  = COLORS["border_light"]

# ─── Typography ────────────────────────────────────────────────────────────────
_OS = _platform.system()

if _OS == "Darwin":
    FONT_FAMILY      = "SF Pro Text"
    FONT_FAMILY_BOLD = "SF Pro Display"
    FONT_MONO        = "SF Mono"
elif _OS == "Windows":
    FONT_FAMILY      = "Segoe UI"
    FONT_FAMILY_BOLD = "Segoe UI Semibold"
    FONT_MONO        = "Consolas"
else:
    FONT_FAMILY      = "DejaVu Sans"
    FONT_FAMILY_BOLD = "DejaVu Sans"
    FONT_MONO        = "DejaVu Sans Mono"

FONT_UI   = FONT_FAMILY
FONT_BOLD = FONT_FAMILY_BOLD

FONT_SIZES = {
    "xs":   10,
    "sm":   11,
    "base": 13,
    "md":   14,
    "lg":   16,
    "xl":   20,
    "2xl":  24,
    "3xl":  30,
    "4xl":  36,
    "5xl":  48,
}

FONTS = {
    # UI sizes
    "xs":        (FONT_FAMILY, FONT_SIZES["xs"]),
    "xs_bold":   (FONT_FAMILY_BOLD, FONT_SIZES["xs"], "bold"),
    "sm":        (FONT_FAMILY, FONT_SIZES["sm"]),
    "sm_bold":   (FONT_FAMILY_BOLD, FONT_SIZES["sm"], "bold"),
    "base":      (FONT_FAMILY, FONT_SIZES["base"]),
    "base_bold": (FONT_FAMILY_BOLD, FONT_SIZES["base"], "bold"),
    "md":        (FONT_FAMILY, FONT_SIZES["md"]),
    "md_bold":   (FONT_FAMILY_BOLD, FONT_SIZES["md"], "bold"),
    "lg":        (FONT_FAMILY, FONT_SIZES["lg"]),
    "lg_bold":   (FONT_FAMILY_BOLD, FONT_SIZES["lg"], "bold"),
    "xl":        (FONT_FAMILY, FONT_SIZES["xl"]),
    "xl_bold":   (FONT_FAMILY_BOLD, FONT_SIZES["xl"], "bold"),
    "2xl":       (FONT_FAMILY, FONT_SIZES["2xl"]),
    "2xl_bold":  (FONT_FAMILY_BOLD, FONT_SIZES["2xl"], "bold"),
    "3xl":       (FONT_FAMILY, FONT_SIZES["3xl"]),
    "3xl_bold":  (FONT_FAMILY_BOLD, FONT_SIZES["3xl"], "bold"),
    # Legacy names for backward compat
    "brand":        (FONT_FAMILY_BOLD, 18, "bold"),
    "h1":           (FONT_FAMILY_BOLD, 15, "bold"),
    "h2":           (FONT_FAMILY_BOLD, 13, "bold"),
    "body":         (FONT_FAMILY, 12),
    "body_med":     (FONT_FAMILY_BOLD, 12, "bold"),
    "caption":      (FONT_FAMILY, 11),
    "caption_med":  (FONT_FAMILY_BOLD, 11, "bold"),
    "tiny":         (FONT_FAMILY, 10),
    "btn":          (FONT_FAMILY_BOLD, 13, "bold"),
    "btn_sm":       (FONT_FAMILY_BOLD, 11, "bold"),
    "btn_lg":       (FONT_FAMILY_BOLD, 14, "bold"),
    "generate":     (FONT_FAMILY_BOLD, 15, "bold"),
    "status":       (FONT_MONO, 11),
    # Mono
    "mono":         (FONT_MONO, FONT_SIZES["base"]),
    "mono_sm":      (FONT_MONO, FONT_SIZES["sm"]),
    "mono_xs":      (FONT_MONO, FONT_SIZES["xs"]),
}

# ─── Spacing / Padding ─────────────────────────────────────────────────────────
PAD = {
    "xs":      2,
    "sm":      4,
    "md":      8,
    "lg":      12,
    "xl":      16,
    "2xl":     20,
    "3xl":     24,
    "4xl":     32,
    "5xl":     40,
    "6xl":     48,
    # Named contexts
    "page":    24,
    "card":    16,
    "sidebar":  8,
    # Legacy
    "xxl":     40,
}

# ─── Border Radius ─────────────────────────────────────────────────────────────
RADIUS = {
    "xs":   4,
    "sm":   6,
    "md":   8,
    "lg":   12,
    "xl":   16,
    "2xl":  20,
    "full": 9999,
}

# ─── Layout Constants ──────────────────────────────────────────────────────────
SIDEBAR_WIDTH             = 58
CONTROLS_WIDTH            = 320
BOTTOM_BAR_HEIGHT         = 40
TERMINAL_HEIGHT_EXPANDED  = 180
TERMINAL_HEIGHT_COLLAPSED = 36

# ─── Emotion → Color Mapping (thumbnail generation) ───────────────────────────
COLOR_EMOTIONS = {
    "Neutral":                  ("#4a5568", "#2d3748"),
    "Happy & Upbeat":           ("#f59e0b", "#d97706"),
    "Serious & Authoritative":  ("#3b82f6", "#1d4ed8"),
    "Sad & Reflective":         ("#8b5cf6", "#6d28d9"),
    "Excited & Enthusiastic":   ("#ef4444", "#dc2626"),
    "Calm & Meditative":        ("#10b981", "#059669"),
    "Warm & Friendly":          ("#f97316", "#ea580c"),
    "Professional":             ("#64748b", "#475569"),
}

# ─── Preset Accent Colors (for settings color picker) ─────────────────────────
ACCENT_PRESETS = [
    ("#7c3aed", "Violet"),
    ("#3b82f6", "Blue"),
    ("#10b981", "Green"),
    ("#f59e0b", "Amber"),
    ("#ec4899", "Pink"),
    ("#ef4444", "Red"),
]

# ─── Component Style Helpers ───────────────────────────────────────────────────

def btn_primary() -> dict:
    """Kwargs for a primary violet action button."""
    return {
        "fg_color":      ACCENT,
        "hover_color":   ACCENT_HOVER,
        "text_color":    TEXT,
        "corner_radius": RADIUS["md"],
        "font":          FONTS["md_bold"],
    }

def btn_secondary() -> dict:
    """Kwargs for a secondary/outlined button."""
    return {
        "fg_color":      CARD,
        "hover_color":   CARD_HOVER,
        "text_color":    TEXT_SUB,
        "border_color":  BORDER_LIGHT,
        "border_width":  1,
        "corner_radius": RADIUS["md"],
        "font":          FONTS["base"],
    }

def btn_ghost() -> dict:
    """Kwargs for a transparent ghost button."""
    return {
        "fg_color":      "transparent",
        "hover_color":   CARD_HOVER,
        "text_color":    TEXT_SUB,
        "corner_radius": RADIUS["sm"],
        "font":          FONTS["base"],
    }

def card_frame() -> dict:
    """Kwargs for a standard card CTkFrame."""
    return {
        "fg_color":      CARD,
        "corner_radius": RADIUS["lg"],
        "border_color":  BORDER,
        "border_width":  1,
    }

def input_field() -> dict:
    """Kwargs for CTkEntry / CTkTextbox."""
    return {
        "fg_color":      INPUT_BG,
        "border_color":  BORDER_LIGHT,
        "border_width":  1,
        "text_color":    TEXT,
        "corner_radius": RADIUS["md"],
    }

def label_heading() -> dict:
    return {"text_color": TEXT, "font": FONTS["lg_bold"]}

def label_sub() -> dict:
    return {"text_color": TEXT_SUB, "font": FONTS["base"]}

def label_muted() -> dict:
    return {"text_color": TEXT_MUTED, "font": FONTS["sm"]}

# ─── CustomTkinter Theme Bootstrap ────────────────────────────────────────────

def apply_ctk_theme():
    """Call once at startup after importing customtkinter."""
    try:
        import customtkinter as ctk
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")
    except ImportError:
        pass
