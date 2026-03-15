# AURA VOICE Project File Format — Technical Specification

## Overview

The `.auravoice` file extension is used for AURA VOICE project files. A `.auravoice` file is a **standard ZIP archive** with a renamed extension. Any program that can read ZIP files can inspect the contents.

---

## File Structure

```
myproject.auravoice (ZIP archive)
├── manifest.json
├── project.json
└── script.txt
```

### manifest.json

Identifies the file as a valid AURA VOICE project. Any reader must check this file before attempting to open the archive.

```json
{
  "format": "auravoice_v1",
  "created_by": "AURA VOICE",
  "app_version": "1.0.0"
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `format` | string | yes | Must be exactly `"auravoice_v1"` |
| `created_by` | string | yes | Application identifier |
| `app_version` | string | no | Semver of the app that created the file |

**Validation rule:** If `manifest.json` is missing, or if `format` is not `"auravoice_v1"`, the file must be rejected with an error message. This prevents random ZIP files from being accidentally opened as projects.

---

### project.json

Stores all user-configurable settings at the time the project was saved.

```json
{
  "voice_profile":  "Natural Female",
  "emotion":        "Neutral",
  "speed":          1.0,
  "language":       "English",
  "output_format":  "wav",
  "output_folder":  "/Users/alice/Desktop",
  "reference_wav":  null,
  "created_at":     "2026-03-15T14:23:07",
  "app_version":    "1.0.0"
}
```

| Field | Type | Description |
|---|---|---|
| `voice_profile` | string | One of the VOICE_PROFILES keys |
| `emotion` | string | One of the EMOTION_PREFIXES keys |
| `speed` | float | Speaking speed multiplier (0.5–2.0) |
| `language` | string | Display name, e.g. "English" |
| `output_format` | string | `"wav"` or `"mp3"` |
| `output_folder` | string | Absolute path to the output directory |
| `reference_wav` | string \| null | Absolute path to cloning reference WAV, or null |
| `created_at` | string | ISO 8601 datetime |
| `app_version` | string | App version that saved the project |

---

### script.txt

The full input text, encoded as **UTF-8**. No length limit. Line endings may be LF or CRLF.

---

## ZIP Compression

The archive uses `ZIP_DEFLATED` compression. All three member files are always present. Future versions may add additional members; readers should ignore unknown members.

---

## Versioning

The `"format"` field in `manifest.json` is the version identifier. The current format version is `auravoice_v1`. Future breaking changes will increment this (e.g. `auravoice_v2`). Readers should reject files with unknown format identifiers.

---

## Creating .auravoice Files Programmatically

```python
import io, json, zipfile
from pathlib import Path

def create_auravoice(save_path: str, script: str, settings: dict) -> None:
    manifest = {
        "format":      "auravoice_v1",
        "created_by":  "AURA VOICE",
        "app_version": "1.0.0",
    }
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json", json.dumps(manifest, indent=2))
        zf.writestr("project.json",  json.dumps(settings,  indent=2))
        zf.writestr("script.txt",    script)
    Path(save_path).write_bytes(buf.getvalue())
```

## Reading .auravoice Files Programmatically

```python
import json, zipfile
from pathlib import Path

def read_auravoice(file_path: str):
    with zipfile.ZipFile(file_path, "r") as zf:
        manifest = json.loads(zf.read("manifest.json"))
        if manifest.get("format") != "auravoice_v1":
            raise ValueError("Not a valid AURA VOICE project file.")
        settings = json.loads(zf.read("project.json"))
        script   = zf.read("script.txt").decode("utf-8")
    return script, settings
```

---

## File Association on macOS

To associate `.auravoice` files with AURA VOICE in Finder:

1. Right-click any `.auravoice` file
2. **Get Info** (⌘I)
3. Under **Open with**, click **Other…**
4. Navigate to your Python interpreter or a shell launcher script
5. Tick **Always Open With** and click **Add**

For a better experience, wrap the launch in a `.command` file:

```bash
#!/bin/bash
# aura_voice_launcher.command
cd /path/to/aura_voice
source venv/bin/activate
python3 main.py "$@"
```

Set the `.command` file as the default application for `.auravoice` files.
