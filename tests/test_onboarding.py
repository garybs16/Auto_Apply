import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from applypilot import config
from applypilot.onboarding import import_resume, install_profile, validate_profile


def valid_profile():
    return {
        "personal": {
            "full_name": "Test Candidate",
            "email": "candidate@example.com",
            "phone": "555-0100",
            "city": "Irvine",
            "province_state": "California",
            "country": "United States",
        },
        "work_authorization": {
            "legally_authorized_to_work": True,
            "require_sponsorship": False,
        },
    }


class OnboardingTests(unittest.TestCase):
    def test_profile_validation(self):
        self.assertEqual(validate_profile(valid_profile()), [])
        broken = valid_profile()
        broken["personal"]["phone"] = ""
        self.assertEqual(validate_profile(broken), ["personal.phone"])

    def test_text_resume_import(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.txt"
            destination = root / "private" / "resume.txt"
            source.write_text("Software engineering resume content. " * 10, encoding="utf-8")
            with patch.object(config, "RESUME_PATH", destination), patch.object(config, "ensure_dirs", lambda: destination.parent.mkdir(parents=True, exist_ok=True)):
                text_path, pdf_path = import_resume(source)
            self.assertEqual(text_path, destination)
            self.assertIsNone(pdf_path)
            self.assertIn("Software engineering", destination.read_text(encoding="utf-8"))

    def test_profile_install_rejects_incomplete_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "profile.json"
            source.write_text(json.dumps({"personal": {}}), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "missing required fields"):
                install_profile(source)


if __name__ == "__main__":
    unittest.main()
