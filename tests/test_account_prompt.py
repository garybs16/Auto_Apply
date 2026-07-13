import os
import unittest
from unittest.mock import patch

from applypilot.apply.launcher import _make_mcp_config
from applypilot.apply.prompt import _build_account_section


PROFILE = {
    "personal": {"email": "candidate@example.com"},
    "accounts": {"create_when_required": True, "email_verification": "gmail"},
}


class AccountPromptTests(unittest.TestCase):
    def test_account_prompt_uses_site_specific_credential(self):
        env = {"JOB_ACCOUNT_MASTER_SECRET": "a-secure-test-master-secret-12345"}
        with patch.dict(os.environ, env, clear=True):
            prompt = _build_account_section(PROFILE, "https://jobs.example.com/apply")
        self.assertIn("candidate@example.com", prompt)
        self.assertIn("jobs.example.com", prompt)
        self.assertIn("Gmail search/read only", prompt)
        self.assertIn("Aa1!", prompt)

    def test_generated_debug_prompt_redacts_credential(self):
        env = {"JOB_ACCOUNT_MASTER_SECRET": "a-secure-test-master-secret-12345"}
        with patch.dict(os.environ, env, clear=True):
            prompt = _build_account_section(
                PROFILE,
                "https://jobs.example.com/apply",
                include_credentials=False,
            )
        self.assertNotIn("Aa1!", prompt)
        self.assertIn("credentials are unavailable", prompt)

    def test_gmail_mcp_is_only_enabled_by_profile(self):
        with patch("applypilot.apply.launcher.config.load_profile", return_value=PROFILE):
            cfg = _make_mcp_config(9222)
        self.assertIn("gmail", cfg["mcpServers"])

    def test_codex_gmail_tools_are_allowlisted(self):
        with patch("applypilot.apply.launcher.config.load_profile", return_value=PROFILE), patch("applypilot.apply.launcher.shutil.which", return_value="codex"):
            from applypilot.apply.launcher import _build_agent_command
            command = _build_agent_command("codex", None, 9222, None)
        rendered = " ".join(command)
        self.assertIn("mcp_servers.gmail.enabled_tools", rendered)
        self.assertIn("search_emails", rendered)
        self.assertNotIn("delete_email", rendered)


if __name__ == "__main__":
    unittest.main()
