"""
AURA VOICE — .auravoice project file save / load logic.

The .auravoice file is a ZIP archive containing:
  - project.json   All user settings
  - script.txt     The full input text
  - manifest.json  Format metadata (used for validation)
"""

from __future__ import annotations

import io
import json
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from assets.styles import APP_VERSION, FORMAT_ID, CREATED_BY


# ─────────────────────────────────────────────────────────────────────────────
# Types
# ─────────────────────────────────────────────────────────────────────────────

ProjectData = Dict[str, Any]


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _build_manifest() -> Dict[str, str]:
    return {
        "format":     FORMAT_ID,
        "created_by": CREATED_BY,
        "app_version": APP_VERSION,
    }


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


# ─────────────────────────────────────────────────────────────────────────────
# Save
# ─────────────────────────────────────────────────────────────────────────────

def save_project(
    save_path: Path,
    script: str,
    voice_profile: str,
    emotion: str,
    speed: float,
    language: str,
    output_format: str,
    output_folder: str,
    reference_wav: Optional[str] = None,
) -> None:
    """
    Serialise all project settings into a .auravoice file at *save_path*.

    The file is a ZIP archive (despite the custom extension) containing:
      - manifest.json  — format identifier
      - project.json   — all settings
      - script.txt     — input text

    Raises:
        OSError:  If the file cannot be written.
        ValueError: If required fields are missing.
    """
    if not script.strip():
        raise ValueError("Cannot save a project with an empty script.")

    project_data: ProjectData = {
        "voice_profile":  voice_profile,
        "emotion":        emotion,
        "speed":          speed,
        "language":       language,
        "output_format":  output_format,
        "output_folder":  output_folder,
        "reference_wav":  reference_wav,
        "created_at":     _now_iso(),
        "app_version":    APP_VERSION,
    }

    manifest = _build_manifest()

    save_path = Path(save_path)
    save_path.parent.mkdir(parents=True, exist_ok=True)

    # Write directly into the ZIP bytes buffer then rename to .auravoice
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json", json.dumps(manifest, indent=2))
        zf.writestr("project.json",  json.dumps(project_data, indent=2))
        zf.writestr("script.txt",    script)

    save_path.write_bytes(buf.getvalue())


# ─────────────────────────────────────────────────────────────────────────────
# Load
# ─────────────────────────────────────────────────────────────────────────────

def load_project(file_path: Path) -> Tuple[str, ProjectData]:
    """
    Load a .auravoice project file.

    Returns:
        A tuple of (script_text, project_settings_dict).

    Raises:
        ValueError: If the file does not have the correct format identifier.
        KeyError:   If required keys are missing from the archive.
        zipfile.BadZipFile: If the archive is corrupt.
    """
    file_path = Path(file_path)

    if not file_path.exists():
        raise FileNotFoundError(f"Project file not found: {file_path}")

    with zipfile.ZipFile(str(file_path), mode="r") as zf:
        names = zf.namelist()

        # ── Validate format ───────────────────────────────────────────────
        if "manifest.json" not in names:
            raise ValueError(
                "This file is not a valid AURA VOICE project (manifest.json missing)."
            )

        manifest: Dict[str, str] = json.loads(zf.read("manifest.json").decode("utf-8"))
        if manifest.get("format") != FORMAT_ID:
            raise ValueError(
                f"Unrecognised project format '{manifest.get('format')}'. "
                f"Expected '{FORMAT_ID}'."
            )

        # ── Read contents ─────────────────────────────────────────────────
        if "project.json" not in names:
            raise KeyError("project.json is missing from the archive.")
        if "script.txt" not in names:
            raise KeyError("script.txt is missing from the archive.")

        project_data: ProjectData = json.loads(
            zf.read("project.json").decode("utf-8")
        )
        script: str = zf.read("script.txt").decode("utf-8")

    return script, project_data


# ─────────────────────────────────────────────────────────────────────────────
# Inspect (non-destructive peek)
# ─────────────────────────────────────────────────────────────────────────────

def peek_project(file_path: Path) -> Dict[str, Any]:
    """
    Return basic metadata from a .auravoice file without loading the full script.
    Useful for showing a preview before the user commits to opening a project.
    """
    file_path = Path(file_path)
    with zipfile.ZipFile(str(file_path), mode="r") as zf:
        manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
        project  = json.loads(zf.read("project.json").decode("utf-8"))
        # Count words in script without fully reading it
        script_bytes = zf.read("script.txt")
        word_count   = len(script_bytes.decode("utf-8", errors="replace").split())

    return {
        "format":       manifest.get("format"),
        "app_version":  project.get("app_version"),
        "created_at":   project.get("created_at"),
        "voice_profile":project.get("voice_profile"),
        "emotion":      project.get("emotion"),
        "language":     project.get("language"),
        "word_count":   word_count,
    }
