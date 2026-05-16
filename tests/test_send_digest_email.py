import os
import tempfile
import unittest
from pathlib import Path

from sweeps.send_digest_email import (
    build_email_payload,
    load_env_file,
    parse_recipients,
    resolve_visible_to_email,
)


class SendDigestEmailTests(unittest.TestCase):
    def test_parse_recipients_trims_and_filters_empty_values(self):
        self.assertEqual(
            parse_recipients(" one@example.com, ,two@example.com "),
            ["one@example.com", "two@example.com"],
        )

    def test_email_payload_bccs_digest_recipients(self):
        payload = build_email_payload(
            from_email="digest@example.com",
            from_name="AI Sweep",
            visible_to_email="list@example.com",
            recipients=["one@example.com", "two@example.com"],
            subject="Daily Sweep",
            text_body="text",
            html_body="<p>html</p>",
        )

        self.assertEqual(payload["to"], ["list@example.com"])
        self.assertEqual(payload["bcc"], ["one@example.com", "two@example.com"])
        self.assertNotIn("one@example.com", payload["to"])
        self.assertNotIn("two@example.com", payload["to"])

    def test_visible_to_requires_explicit_address_for_personal_gmail_sender(self):
        with self.assertRaisesRegex(RuntimeError, "DIGEST_VISIBLE_TO_EMAIL is required"):
            resolve_visible_to_email("bmoore7789@gmail.com", "")

    def test_visible_to_can_fallback_to_non_personal_sender(self):
        self.assertEqual(
            resolve_visible_to_email("digest@example.com", ""),
            "digest@example.com",
        )

    def test_visible_to_uses_explicit_address(self):
        self.assertEqual(
            resolve_visible_to_email("bmoore7789@gmail.com", "digest@example.com"),
            "digest@example.com",
        )

    def test_load_env_file_sets_missing_values_without_overriding_existing(self):
        key_one = "TEST_DIGEST_ENV_ONE"
        key_two = "TEST_DIGEST_ENV_TWO"
        original_one = os.environ.get(key_one)
        original_two = os.environ.get(key_two)
        try:
            os.environ[key_one] = "shell-value"
            os.environ.pop(key_two, None)

            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / ".env"
                path.write_text(
                    "\n".join(
                        [
                            "# comment",
                            f"{key_one}=file-value",
                            f'{key_two}="quoted file value"',
                        ]
                    ),
                    encoding="utf-8",
                )

                self.assertEqual(load_env_file(path), 1)
                self.assertEqual(os.environ[key_one], "shell-value")
                self.assertEqual(os.environ[key_two], "quoted file value")
        finally:
            if original_one is None:
                os.environ.pop(key_one, None)
            else:
                os.environ[key_one] = original_one
            if original_two is None:
                os.environ.pop(key_two, None)
            else:
                os.environ[key_two] = original_two


if __name__ == "__main__":
    unittest.main()
