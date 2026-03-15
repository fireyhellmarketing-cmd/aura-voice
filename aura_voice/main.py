"""AURA VOICE v2 — Entry point.

Run:
    source venv/bin/activate && python3 main.py
"""

from __future__ import annotations

import os
import sys

# ── Ensure project root is on sys.path ──────────────────────────────────────
_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

# ── Required for Coqui TTS to skip interactive ToS prompt ───────────────────
os.environ.setdefault("COQUI_TOS_AGREED", "1")


# ─── Dependency check ─────────────────────────────────────────────────────────

def _check_dependencies() -> None:
    """Verify all required packages are importable before opening the window."""
    missing: list[str] = []
    required = [
        ("customtkinter", "customtkinter"),
        ("PIL",           "Pillow"),
        ("pydub",         "pydub"),
        ("torch",         "torch"),
    ]
    for module, package in required:
        try:
            __import__(module)
        except ImportError:
            missing.append(package)

    if missing:
        print("=" * 60)
        print("AURA VOICE v2 — Missing dependencies")
        print("=" * 60)
        print("Please install the following packages:\n")
        for pkg in missing:
            print(f"  pip install {pkg}")
        print("\nOr run:  bash setup.sh")
        print("=" * 60)
        sys.exit(1)


# ─── Entry point ──────────────────────────────────────────────────────────────

def main() -> None:
    _check_dependencies()

    # Late imports so dep errors are surfaced first
    from core.model_manager import load_config, save_config

    config = load_config()

    if config.get("first_run", True):
        # ── First run: show startup wizard, then launch main window ──
        import customtkinter as ctk
        from assets.styles import apply_ctk_theme
        apply_ctk_theme()

        # We need a hidden root window to host the wizard (a CTkToplevel)
        root = ctk.CTk()
        root.withdraw()  # hide the dummy root

        completed_config: dict = {}

        def on_wizard_complete(cfg: dict):
            nonlocal completed_config
            completed_config = cfg
            root.quit()

        from ui.startup_wizard import StartupWizard
        wizard = StartupWizard(on_complete=on_wizard_complete)

        # Center wizard
        root.update_idletasks()
        root.mainloop()

        # Destroy the hidden root
        try:
            root.destroy()
        except Exception:
            pass

        if not completed_config:
            # User closed the wizard without completing → exit
            sys.exit(0)

        # Launch the main window with the wizard config
        _launch_main(completed_config)

    else:
        # ── Not first run: go straight to main window ──
        _launch_main(config)


def _launch_main(config: dict) -> None:
    """Construct and run the main application window."""
    from assets.styles import apply_ctk_theme
    apply_ctk_theme()

    from ui.app_window import AuraVoiceApp
    app = AuraVoiceApp(config=config)
    app.mainloop()


if __name__ == "__main__":
    main()
