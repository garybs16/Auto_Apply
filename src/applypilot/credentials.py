"""Deterministic, per-site credentials for job application accounts.

Only the master secret is stored locally in ``~/.applypilot/.env``.  A unique
password is derived for every employer domain, so a breach at one ATS does not
reuse the credential at another site.  Nothing is written to the repository.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
from urllib.parse import urlparse

from applypilot import config


def normalize_site(value: str) -> str:
    """Return a stable lowercase hostname from a URL or domain."""
    candidate = value.strip()
    if "://" not in candidate:
        candidate = f"https://{candidate}"
    hostname = (urlparse(candidate).hostname or "").lower().strip(".")
    if hostname.startswith("www."):
        hostname = hostname[4:]
    if not hostname or "." not in hostname:
        raise ValueError(f"Invalid job-site URL or domain: {value}")
    return hostname


def derive_site_password(master_secret: str, site: str, length: int = 20) -> str:
    """Derive a strong, repeatable password unique to ``site``."""
    if len(master_secret) < 16:
        raise ValueError("JOB_ACCOUNT_MASTER_SECRET must be at least 16 characters")
    if length < 16:
        raise ValueError("Derived passwords must be at least 16 characters")
    hostname = normalize_site(site)
    digest = hmac.new(
        master_secret.encode("utf-8"),
        hostname.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    token = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    # A fixed complexity prefix satisfies the common upper/lower/number/symbol
    # requirements while the HMAC-derived suffix supplies the entropy.
    return ("Aa1!" + token)[:length]


def account_creation_enabled(profile: dict) -> bool:
    """Whether the user explicitly opted into employer account creation."""
    configured = profile.get("accounts", {}).get("create_when_required")
    if configured is not None:
        return bool(configured)
    env_enabled = os.environ.get("ACCOUNT_CREATION_ENABLED", "").lower() in {"1", "true", "yes", "y"}
    legacy_configured = bool(profile.get("personal", {}).get("password", "").strip())
    return env_enabled or legacy_configured


def email_verification_enabled(profile: dict) -> bool:
    """Whether read-only email verification automation was enabled."""
    configured = profile.get("accounts", {}).get("email_verification")
    if configured is not None:
        return str(configured).lower() in {"gmail", "enabled", "true", "yes"}
    return os.environ.get("EMAIL_VERIFICATION_ENABLED", "").lower() in {"1", "true", "yes", "y"}


def password_for_site(profile: dict, site: str) -> str | None:
    """Return the configured per-site password, or ``None`` if unavailable."""
    config.load_env()
    master = os.environ.get("JOB_ACCOUNT_MASTER_SECRET", "").strip()
    if master:
        return derive_site_password(master, site)

    # Compatibility with profiles created by older releases. New setups never
    # place passwords in profile.json.
    legacy = os.environ.get("JOB_ACCOUNT_LEGACY_PASSWORD", "").strip()
    if not legacy:
        legacy = profile.get("personal", {}).get("password", "").strip()
    return legacy or None


def legacy_password(profile: dict) -> str | None:
    """Return the old shared password only for existing-account sign-in."""
    config.load_env()
    return (
        os.environ.get("JOB_ACCOUNT_LEGACY_PASSWORD", "").strip()
        or profile.get("personal", {}).get("password", "").strip()
        or None
    )


def _upsert_env(values: dict[str, str]) -> None:
    lines = config.ENV_PATH.read_text(encoding="utf-8").splitlines() if config.ENV_PATH.exists() else []
    pending = dict(values)
    updated: list[str] = []
    for line in lines:
        key = line.split("=", 1)[0].strip() if "=" in line else ""
        if key in pending:
            updated.append(f"{key}={pending.pop(key)}")
        else:
            updated.append(line)
    if pending and updated and updated[-1].strip():
        updated.append("")
    updated.extend(f"{key}={value}" for key, value in pending.items())
    config.ENV_PATH.write_text("\n".join(updated).rstrip() + "\n", encoding="utf-8")


def migrate_legacy_credentials() -> bool:
    """Move a plaintext profile password to ignored local environment storage."""
    profile = config.load_profile()
    personal = profile.setdefault("personal", {})
    old_password = personal.get("password", "").strip()
    if not old_password:
        return False

    config.load_env()
    master = os.environ.get("JOB_ACCOUNT_MASTER_SECRET", "").strip() or secrets.token_urlsafe(32)
    _upsert_env({
        "ACCOUNT_CREATION_ENABLED": "true",
        "JOB_ACCOUNT_MASTER_SECRET": master,
        "JOB_ACCOUNT_LEGACY_PASSWORD": old_password,
    })
    personal.pop("password", None)
    profile["accounts"] = {
        "create_when_required": True,
        "email_verification": profile.get("accounts", {}).get("email_verification", "manual"),
    }
    config.PROFILE_PATH.write_text(
        json.dumps(profile, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return True


def set_email_verification(enabled: bool) -> None:
    """Enable or disable Gmail verification without rerunning onboarding."""
    profile = config.load_profile()
    accounts = profile.setdefault("accounts", {})
    accounts["email_verification"] = "gmail" if enabled else "manual"
    _upsert_env({"EMAIL_VERIFICATION_ENABLED": str(enabled).lower()})
    config.PROFILE_PATH.write_text(
        json.dumps(profile, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
