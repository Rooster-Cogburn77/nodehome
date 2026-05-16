#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, date, datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INBOX = ROOT / "docs" / "sweeps" / "inbox" / "manual_stack_articles.jsonl"
LANES = ("workflow", "infra", "hardware", "scene")


def normalize_text(value: str) -> str:
    return " ".join((value or "").strip().split())


def stable_id(title: str, url: str) -> str:
    digest = hashlib.sha256(f"{normalize_text(title)}|{url.strip().lower()}".encode("utf-8")).hexdigest()
    return f"manual-stack:{digest[:16]}"


def read_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    ids: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        row_id = normalize_text(str(row.get("id", "")))
        if row_id:
            ids.add(row_id)
    return ids


def append_article(args: argparse.Namespace) -> int:
    title = normalize_text(args.title)
    url = normalize_text(args.url)
    if not title:
        raise SystemExit("--title is required")
    if not url.startswith(("http://", "https://")):
        raise SystemExit("--url must be http(s)")

    path = Path(args.output)
    if not path.is_absolute():
        path = ROOT / path
    path.parent.mkdir(parents=True, exist_ok=True)

    row_id = normalize_text(args.id) or stable_id(title, url)
    if row_id in read_ids(path):
        print(f"already queued: {row_id}")
        return 0

    row = {
        "id": row_id,
        "title": title,
        "link": url,
        "published": normalize_text(args.published) or date.today().isoformat(),
        "summary": normalize_text(args.summary) or title,
        "lane": args.lane,
        "source": normalize_text(args.source) or "Manual Stack Article Inbox",
        "confidence": normalize_text(args.confidence) or "manual-primary",
        "novelty": normalize_text(args.novelty) or "operator-curated",
        "action": normalize_text(args.action) or "review",
        "why": normalize_text(args.why) or "Manually queued by the operator for the afternoon stack digest.",
        "validation_status": "n/a",
        "added_at": datetime.now(UTC).isoformat(),
    }
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")
    print(f"queued: {row_id}")
    print(path)
    return 0


def list_articles(args: argparse.Namespace) -> int:
    path = Path(args.output)
    if not path.is_absolute():
        path = ROOT / path
    if not path.exists():
        print(f"no manual article inbox: {path}")
        return 0
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            print(f"invalid jsonl row: {line[:120]}")
            continue
        print(f"{row.get('id', '')} | {row.get('lane', '')} | {row.get('title', '')}")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Queue operator-curated articles for the afternoon stack digest.")
    parser.add_argument(
        "--output",
        default=str(DEFAULT_INBOX.relative_to(ROOT)),
        help="JSONL inbox path; defaults to docs/sweeps/inbox/manual_stack_articles.jsonl",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    add = sub.add_parser("add", help="Append one article if it is not already queued.")
    add.add_argument("--title", required=True)
    add.add_argument("--url", required=True)
    add.add_argument("--summary", default="")
    add.add_argument("--lane", choices=LANES, default="workflow")
    add.add_argument("--published", default="")
    add.add_argument("--source", default="Manual Stack Article Inbox")
    add.add_argument("--confidence", default="manual-primary")
    add.add_argument("--novelty", default="operator-curated")
    add.add_argument("--action", default="review")
    add.add_argument("--why", default="")
    add.add_argument("--id", default="")
    add.set_defaults(func=append_article)

    listing = sub.add_parser("list", help="List queued manual articles.")
    listing.set_defaults(func=list_articles)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
