import os
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from applypilot import config
from applypilot.credentials import (
    account_creation_enabled,
    derive_site_password,
    normalize_site,
    migrate_legacy_credentials,
    set_email_verification,
)


class CredentialTests(unittest.TestCase):
    def test_normalize_site(self):
        self.assertEqual(normalize_site("https://www.jobs.example.com/apply"), "jobs.example.com")
        self.assertEqual(normalize_site("jobs.example.com"), "jobs.example.com")

    def test_password_is_repeatable_and_unique_per_site(self):
        master = "this-is-a-long-test-master-secret"
        first = derive_site_password(master, "https://jobs.example.com/apply")
        again = derive_site_password(master, "jobs.example.com")
        other = derive_site_password(master, "careers.example.org")
        self.assertEqual(first, again)
        self.assertNotEqual(first, other)
        self.assertEqual(len(first), 20)
        self.assertTrue(first.startswith("Aa1!"))

    def test_account_creation_requires_opt_in(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(account_creation_enabled({"personal": {}}))
            self.assertTrue(account_creation_enabled({"accounts": {"create_when_required": True}}))

    def test_legacy_password_migration_removes_profile_secret(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {}, clear=True):
            root = Path(tmp)
            profile_path = root / "profile.json"
            env_path = root / ".env"
            profile_path.write_text(json.dumps({
                "personal": {"email": "candidate@example.com", "password": "legacy-password"}
            }), encoding="utf-8")
            with patch.object(config, "PROFILE_PATH", profile_path), patch.object(config, "ENV_PATH", env_path):
                self.assertTrue(migrate_legacy_credentials())
            migrated = json.loads(profile_path.read_text(encoding="utf-8"))
            self.assertNotIn("password", migrated["personal"])
            env_text = env_path.read_text(encoding="utf-8")
            self.assertIn("JOB_ACCOUNT_LEGACY_PASSWORD=legacy-password", env_text)
            self.assertIn("JOB_ACCOUNT_MASTER_SECRET=", env_text)

    def test_email_verification_toggle_updates_private_config(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {}, clear=True):
            root = Path(tmp)
            profile_path = root / "profile.json"
            env_path = root / ".env"
            profile_path.write_text(json.dumps({"personal": {"email": "candidate@example.com"}}), encoding="utf-8")
            with patch.object(config, "PROFILE_PATH", profile_path), patch.object(config, "ENV_PATH", env_path):
                set_email_verification(True)
            profile = json.loads(profile_path.read_text(encoding="utf-8"))
            self.assertEqual(profile["accounts"]["email_verification"], "gmail")
            self.assertIn("EMAIL_VERIFICATION_ENABLED=true", env_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
