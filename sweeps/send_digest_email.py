#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.request
from datetime import date
from pathlib import Path


RESEND_API_URL = "https://api.resend.com/emails"


def digest_path(profile: str, run_date: date) -> Path:
    root = Path(__file__).resolve().parent.parent
    suffix = "" if profile == "core" else f".{profile}"
    return root / "docs" / "sweeps" / "daily" / f"{run_date.isoformat()}{suffix}.md"


def markdown_to_text(markdown: str) -> str:
    text = markdown
    text = re.sub(r"^###\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^##\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^#\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"\[(.*?)\]\((.*?)\)", r"\1 (\2)", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    return text.strip()


def markdown_to_html(markdown: str) -> str:
    html = markdown
    html = html.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    html = re.sub(r"^### (.+)$", r"<h3>\1</h3>", html, flags=re.MULTILINE)
    html = re.sub(r"^## (.+)$", r"<h2>\1</h2>", html, flags=re.MULTILINE)
    html = re.sub(r"^# (.+)$", r"<h1>\1</h1>", html, flags=re.MULTILINE)
    html = re.sub(r"^- (.+)$", r"<li>\1</li>", html, flags=re.MULTILINE)
    html = re.sub(r"(<li>.*</li>)", r"<ul>\1</ul>", html, flags=re.DOTALL)
    html = re.sub(r"`([^`]+)`", r"<code>\1</code>", html)
    html = re.sub(r"\n{2,}", "</p><p>", html)
    return f"<html><body><p>{html}</p></body></html>"


def getenv_required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required env var: {name}")
    return value


def parse_recipients(value: str) -> list[str]:
    recipients = [item.strip() for item in value.split(",") if item.strip()]
    if not recipients:
        raise RuntimeError("DIGEST_TO_EMAILS is empty")
    return recipients


def send_email(
    api_key: str,
    from_email: str,
    from_name: str,
    recipients: list[str],
    subject: str,
    text_body: str,
    html_body: str,
) -> dict:
    payload = {
        "from": f"{from_name} <{from_email}>",
        "to": recipients,
        "subject": subject,
        "text": text_body,
        "html": html_body,
    }
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        RESEND_API_URL,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "SovereignNodeSweep/0.1 (+local)",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Send a daily sweep digest via Resend.")
    parser.add_argument("--input", dest="input_path", help="Explicit digest file path.")
    parser.add_argument("--profile", choices=("core", "extended", "all"), default="core")
    parser.add_argument("--date", dest="run_date", help="Digest date in YYYY-MM-DD format.")
    parser.add_argument("--dry-run", action="store_true", help="Render and validate without sending.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    enabled = os.getenv("DIGEST_EMAIL_ENABLED", "false").strip().lower() == "true"
    if not enabled:
        print("DIGEST_EMAIL_ENABLED is not true; skipping email send.")
        return 0

    if args.input_path:
        path = Path(args.input_path)
    else:
        run_date = date.fromisoformat(args.run_date) if args.run_date else date.today()
        path = digest_path(args.profile, run_date)

    if not path.exists():
        raise FileNotFoundError(f"Digest file not found: {path}")

    markdown = path.read_text(encoding="utf-8")
    text_body = markdown_to_text(markdown)
    html_body = markdown_to_html(markdown)

    recipients = parse_recipients(getenv_required("DIGEST_TO_EMAILS"))
    from_email = getenv_required("DIGEST_FROM_EMAIL")
    from_name = getenv_required("DIGEST_FROM_NAME")
    api_key = getenv_required("RESEND_API_KEY")
    subject = f"Daily Sweep - {path.stem}"

    if args.dry_run:
        print(json.dumps({"subject": subject, "to": recipients, "input": str(path)}, indent=2))
        return 0

    response = send_email(api_key, from_email, from_name, recipients, subject, text_body, html_body)
    print(json.dumps(response, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
