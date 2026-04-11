#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import imaplib
import json
import os
import re
from datetime import UTC, datetime, timedelta
from email import message_from_bytes
from email.header import decode_header
from email.message import Message
from email.utils import parsedate_to_datetime
from html import unescape
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = ROOT / "docs" / "sweeps" / "inbox" / "x_email_posts.jsonl"
URL_RE = re.compile(r"https?://(?:www\.)?(?:x|twitter)\.com/[^\s<>()\"']+", re.IGNORECASE)
STATUS_RE = re.compile(r"https?://(?:www\.)?(?:x|twitter)\.com/([^/?#]+)/status/(\d+)", re.IGNORECASE)


def getenv_required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required env var: {name}")
    return value


def decode_mime(value: str | None) -> str:
    if not value:
        return ""
    parts = []
    for payload, charset in decode_header(value):
        if isinstance(payload, bytes):
            parts.append(payload.decode(charset or "utf-8", errors="replace"))
        else:
            parts.append(payload)
    return "".join(parts).strip()


def message_text(message: Message) -> str:
    parts: list[str] = []
    if message.is_multipart():
        for part in message.walk():
            content_type = part.get_content_type()
            if content_type not in {"text/plain", "text/html"}:
                continue
            payload = part.get_payload(decode=True)
            if not payload:
                continue
            charset = part.get_content_charset() or "utf-8"
            parts.append(payload.decode(charset, errors="replace"))
    else:
        payload = message.get_payload(decode=True)
        if payload:
            charset = message.get_content_charset() or "utf-8"
            parts.append(payload.decode(charset, errors="replace"))

    text = "\n".join(parts)
    text = unescape(text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def normalize_url(url: str) -> str:
    url = unescape(url).rstrip(".,);]")
    url = re.sub(r"^https?://(?:www\.)?twitter\.com/", "https://x.com/", url, flags=re.IGNORECASE)
    url = re.sub(r"^https?://(?:www\.)?x\.com/", "https://x.com/", url, flags=re.IGNORECASE)
    return url.split("?", 1)[0].split("#", 1)[0]


def extract_status_urls(text: str) -> list[str]:
    urls: list[str] = []
    for raw_url in URL_RE.findall(text):
        url = normalize_url(raw_url)
        if STATUS_RE.search(url) and url not in urls:
            urls.append(url)
    return urls


def parse_email_date(value: str | None) -> str:
    if not value:
        return ""
    try:
        return parsedate_to_datetime(value).astimezone(UTC).isoformat()
    except (TypeError, ValueError, AttributeError):
        return ""


def item_from_message(message: Message) -> dict[str, str] | None:
    subject = decode_mime(message.get("Subject"))
    sender = decode_mime(message.get("From"))
    body = message_text(message)
    combined = f"{subject}\n{sender}\n{body}"
    urls = extract_status_urls(combined)
    if not urls:
        return None

    link = urls[0]
    status_match = STATUS_RE.search(link)
    status_id = status_match.group(2) if status_match else ""
    handle = status_match.group(1) if status_match else ""
    published = parse_email_date(message.get("Date"))
    digest = hashlib.sha256(f"{subject}|{published}|{link}|{body[:500]}".encode("utf-8")).hexdigest()
    title = subject or body[:180] or link
    if handle and handle.lower() not in title.lower():
        title = f"@{handle}: {title}"
    return {
        "id": f"x-email:{status_id or digest}",
        "title": title[:280],
        "link": link,
        "published": published,
        "summary": body[:500],
        "source": "x-email",
    }


def existing_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    ids = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if item.get("id"):
            ids.add(str(item["id"]))
    return ids


def sender_allowed(message: Message, filters: list[str]) -> bool:
    if not filters:
        return True
    sender = decode_mime(message.get("From")).lower()
    return any(token in sender for token in filters)


def fetch_messages(args: argparse.Namespace) -> list[dict[str, str]]:
    host = getenv_required("X_EMAIL_IMAP_HOST")
    username = getenv_required("X_EMAIL_IMAP_USERNAME")
    password = getenv_required("X_EMAIL_IMAP_PASSWORD")
    port = int(os.getenv("X_EMAIL_IMAP_PORT", "993"))
    mailbox = os.getenv("X_EMAIL_IMAP_MAILBOX", "INBOX")
    raw_filters = os.getenv("X_EMAIL_FROM_FILTER", "x.com,twitter.com")
    filters = [item.strip().lower() for item in raw_filters.split(",") if item.strip()]
    since = (datetime.now(UTC) - timedelta(days=args.since_days)).strftime("%d-%b-%Y")

    items: list[dict[str, str]] = []
    with imaplib.IMAP4_SSL(host, port) as client:
        client.login(username, password)
        client.select(mailbox)
        _status, data = client.search(None, "SINCE", since)
        message_ids = data[0].split()[-args.limit :]
        for message_id in message_ids:
            _status, fetch_data = client.fetch(message_id, "(RFC822)")
            if not fetch_data or not isinstance(fetch_data[0], tuple):
                continue
            message = message_from_bytes(fetch_data[0][1])
            if not sender_allowed(message, filters):
                continue
            item = item_from_message(message)
            if item:
                items.append(item)
    return items


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingest X notification emails into sweep JSONL inbox.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="JSONL output path.")
    parser.add_argument("--since-days", type=int, default=3, help="How many days of mailbox history to scan.")
    parser.add_argument("--limit", type=int, default=300, help="Maximum recent IMAP messages to inspect.")
    parser.add_argument("--dry-run", action="store_true", help="Print discovered items without writing JSONL.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output = Path(args.output)
    if not output.is_absolute():
        output = ROOT / output
    items = fetch_messages(args)
    seen = existing_ids(output)
    new_items = [item for item in items if item["id"] not in seen]

    if args.dry_run:
        print(json.dumps({"found": len(items), "new": len(new_items), "items": new_items[:10]}, indent=2))
        return 0

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("a", encoding="utf-8") as handle:
        for item in new_items:
            handle.write(json.dumps(item, ensure_ascii=False) + "\n")
    print(json.dumps({"found": len(items), "new": len(new_items), "output": str(output)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
