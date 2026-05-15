import unittest

from sweeps.send_digest_email import (
    build_email_payload,
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


if __name__ == "__main__":
    unittest.main()
