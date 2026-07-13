"""Resume and profile ingestion for unattended Auto Apply setup."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from applypilot import config


REQUIRED_PROFILE_FIELDS = (
    "personal.full_name",
    "personal.email",
    "personal.phone",
    "personal.city",
    "personal.province_state",
    "personal.country",
    "work_authorization.legally_authorized_to_work",
    "work_authorization.require_sponsorship",
)


def _nested_value(data: dict, dotted_key: str):
    value = data
    for part in dotted_key.split("."):
        if not isinstance(value, dict) or part not in value:
            return None
        value = value[part]
    return value


def validate_profile(profile: dict) -> list[str]:
    """Return missing fields that would block accurate form completion."""
    return [
        field for field in REQUIRED_PROFILE_FIELDS
        if _nested_value(profile, field) in (None, "")
    ]


def install_profile(source: str | Path) -> Path:
    """Validate and install a JSON profile into the private app directory."""
    src = Path(source).expanduser().resolve()
    if not src.exists():
        raise FileNotFoundError(f"Profile not found: {src}")
    profile = json.loads(src.read_text(encoding="utf-8"))
    missing = validate_profile(profile)
    if missing:
        raise ValueError("Profile is missing required fields: " + ", ".join(missing))
    config.ensure_dirs()
    config.PROFILE_PATH.write_text(
        json.dumps(profile, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return config.PROFILE_PATH


def extract_pdf_text(source: str | Path) -> str:
    """Extract selectable text from a PDF resume."""
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover - dependency error path
        raise RuntimeError("PDF extraction requires pypdf; reinstall Auto Apply") from exc

    reader = PdfReader(str(source))
    text = "\n".join((page.extract_text() or "").strip() for page in reader.pages).strip()
    if len(text) < 100:
        raise ValueError(
            "The PDF contains too little selectable text. Use a text-based PDF "
            "or OCR the scanned resume before importing it."
        )
    return text


def import_resume(source: str | Path) -> tuple[Path, Path | None]:
    """Install a TXT or PDF resume and always create ``resume.txt``."""
    src = Path(source).expanduser().resolve()
    if not src.exists():
        raise FileNotFoundError(f"Resume not found: {src}")
    suffix = src.suffix.lower()
    if suffix not in {".txt", ".pdf"}:
        raise ValueError("Resume must be a .pdf or .txt file")

    config.ensure_dirs()
    if suffix == ".txt":
        text = src.read_text(encoding="utf-8").strip()
        if len(text) < 100:
            raise ValueError("Resume text is too short to use safely")
        config.RESUME_PATH.write_text(text + "\n", encoding="utf-8")
        return config.RESUME_PATH, None

    shutil.copy2(src, config.RESUME_PDF_PATH)
    text = extract_pdf_text(src)
    config.RESUME_PATH.write_text(text + "\n", encoding="utf-8")
    return config.RESUME_PATH, config.RESUME_PDF_PATH
