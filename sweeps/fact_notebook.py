#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import re
import sqlite3
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from sweeps.send_digest_email import _parse_digest


ROOT = Path(__file__).resolve().parent.parent
NOTEBOOK_DIR = ROOT / "docs" / "sweeps" / "notebook"
DEFAULT_DB = NOTEBOOK_DIR / "facts.sqlite"


def digest_path(profile: str, run_date: date) -> Path:
    suffix = "" if profile == "core" else f".{profile}"
    return ROOT / "docs" / "sweeps" / "daily" / f"{run_date.isoformat()}{suffix}.md"


def normalize_text(value: str) -> str:
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def normalize_claim(value: str) -> str:
    value = normalize_text(value).lower()
    value = re.sub(r"https?://\S+", "", value)
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return normalize_text(value)


def fact_id(claim: str, source_url: str, source_name: str) -> str:
    normalized = f"{normalize_claim(claim)}|{source_url.strip().lower()}|{source_name.strip().lower()}"
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def topic_for_item(lane: str, title: str, source: str) -> str:
    text = f"{title} {source}".lower()
    topics = (
        ("local-inference", ("ollama", "vllm", "llama.cpp", "ggml", "local", "serving")),
        ("multi-gpu", ("multi-gpu", "multi gpu", "tensor parallel", "pipeline parallel", "split-mode", "3090")),
        ("model-release", ("qwen", "llama", "gemma", "mistral", "deepseek", "phi", "model")),
        ("hardware", ("serve", "gpu", "10gbe", "switch", "nvme", "epyc", "supermicro", "rack")),
        ("workflow", ("agent", "mcp", "claude", "codex", "obsidian", "notebook", "research", "simon", "karpathy")),
        ("x-social", ("x email", "bluesky", "twitter", "x notifications", "x: @")),
    )
    for topic, needles in topics:
        if any(needle in text for needle in needles):
            return topic
    return lane


def claim_from_item(section: str, item: dict[str, Any]) -> str:
    title = normalize_text(item.get("title", ""))
    meta = item.get("meta", {})
    why = normalize_text(meta.get("Why it matters", ""))
    if why and len(why) < 180:
        return f"{title} — {why}"
    return title


def extract_facts(markdown: str, profile: str, run_date: date) -> list[dict[str, str]]:
    digest = _parse_digest(markdown)
    facts: list[dict[str, str]] = []
    for section in digest["sections"]:
        lane = section["name"].lower()
        for item in section["items"]:
            meta = item.get("meta", {})
            claim = claim_from_item(lane, item)
            if not claim:
                continue
            source_url = normalize_text(meta.get("Link", ""))
            source_name = normalize_text(meta.get("Source", ""))
            published = normalize_text(meta.get("Published", ""))
            topic = topic_for_item(lane, item.get("title", ""), source_name)
            confidence = normalize_text(meta.get("Confidence", "")) or "unknown"
            facts.append(
                {
                    "id": fact_id(claim, source_url, source_name),
                    "claim_text": claim,
                    "claim_norm": normalize_claim(claim),
                    "source_url": source_url,
                    "source_name": source_name,
                    "published_at": published,
                    "topic": topic,
                    "lane": lane,
                    "confidence": confidence,
                    "profile": profile,
                    "digest_date": run_date.isoformat(),
                }
            )
    return facts


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS facts (
            id TEXT PRIMARY KEY,
            claim_text TEXT NOT NULL,
            claim_norm TEXT NOT NULL,
            source_url TEXT NOT NULL,
            source_name TEXT NOT NULL,
            published_at TEXT NOT NULL,
            topic TEXT NOT NULL,
            lane TEXT NOT NULL,
            confidence TEXT NOT NULL,
            profile TEXT NOT NULL,
            first_seen TEXT NOT NULL,
            last_seen TEXT NOT NULL,
            seen_count INTEGER NOT NULL DEFAULT 1
        );

        CREATE INDEX IF NOT EXISTS idx_facts_topic ON facts(topic);
        CREATE INDEX IF NOT EXISTS idx_facts_lane ON facts(lane);
        CREATE INDEX IF NOT EXISTS idx_facts_source ON facts(source_name);
        CREATE INDEX IF NOT EXISTS idx_facts_last_seen ON facts(last_seen);

        CREATE TABLE IF NOT EXISTS ingests (
            digest_path TEXT PRIMARY KEY,
            profile TEXT NOT NULL,
            digest_date TEXT NOT NULL,
            ingested_at TEXT NOT NULL,
            fact_count INTEGER NOT NULL
        );
        """
    )
    conn.commit()


def upsert_facts(conn: sqlite3.Connection, facts: list[dict[str, str]], seen_at: str) -> tuple[int, int]:
    inserted = 0
    updated = 0
    for fact in facts:
        cur = conn.execute("SELECT seen_count FROM facts WHERE id = ?", (fact["id"],))
        row = cur.fetchone()
        if row:
            conn.execute(
                """
                UPDATE facts
                SET claim_text = ?, published_at = ?, topic = ?, lane = ?, confidence = ?,
                    profile = ?, last_seen = ?, seen_count = seen_count + 1
                WHERE id = ?
                """,
                (
                    fact["claim_text"],
                    fact["published_at"],
                    fact["topic"],
                    fact["lane"],
                    fact["confidence"],
                    fact["profile"],
                    seen_at,
                    fact["id"],
                ),
            )
            updated += 1
        else:
            conn.execute(
                """
                INSERT INTO facts (
                    id, claim_text, claim_norm, source_url, source_name, published_at,
                    topic, lane, confidence, profile, first_seen, last_seen, seen_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                """,
                (
                    fact["id"],
                    fact["claim_text"],
                    fact["claim_norm"],
                    fact["source_url"],
                    fact["source_name"],
                    fact["published_at"],
                    fact["topic"],
                    fact["lane"],
                    fact["confidence"],
                    fact["profile"],
                    seen_at,
                    seen_at,
                ),
            )
            inserted += 1
    conn.commit()
    return inserted, updated


def record_ingest(conn: sqlite3.Connection, path: Path, profile: str, run_date: date, seen_at: str, fact_count: int) -> None:
    conn.execute(
        """
        INSERT INTO ingests (digest_path, profile, digest_date, ingested_at, fact_count)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(digest_path) DO UPDATE SET
            ingested_at = excluded.ingested_at,
            fact_count = excluded.fact_count
        """,
        (str(path), profile, run_date.isoformat(), seen_at, fact_count),
    )
    conn.commit()


def print_recent(conn: sqlite3.Connection, limit: int) -> None:
    rows = conn.execute(
        """
        SELECT topic, source_name, claim_text
        FROM facts
        ORDER BY last_seen DESC, source_name ASC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    for topic, source_name, claim_text in rows:
        print(f"[{topic}] {source_name}: {claim_text}")


def print_query(conn: sqlite3.Connection, topic: str, source: str, limit: int) -> None:
    where = []
    params: list[str | int] = []
    if topic:
        where.append("topic = ?")
        params.append(topic)
    if source:
        where.append("source_name LIKE ?")
        params.append(f"%{source}%")
    sql = "SELECT topic, source_name, claim_text FROM facts"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY last_seen DESC, source_name ASC LIMIT ?"
    params.append(limit)
    rows = conn.execute(sql, params).fetchall()
    for row_topic, source_name, claim_text in rows:
        print(f"[{row_topic}] {source_name}: {claim_text}")


def print_stats(conn: sqlite3.Connection) -> None:
    total = conn.execute("SELECT COUNT(*) FROM facts").fetchone()[0]
    print(f"facts: {total}")
    print("topics:")
    for topic, count in conn.execute("SELECT topic, COUNT(*) FROM facts GROUP BY topic ORDER BY COUNT(*) DESC, topic"):
        print(f"- {topic}: {count}")
    print("sources:")
    for source_name, count in conn.execute(
        "SELECT source_name, COUNT(*) FROM facts GROUP BY source_name ORDER BY COUNT(*) DESC, source_name LIMIT 12"
    ):
        print(f"- {source_name}: {count}")


def backfill(conn: sqlite3.Connection, profile: str, limit: int) -> tuple[int, int, int]:
    daily_dir = ROOT / "docs" / "sweeps" / "daily"
    paths = sorted(daily_dir.glob("*.md"))
    if profile != "all":
        suffix = "" if profile == "core" else f".{profile}"
        paths = [path for path in paths if path.stem.endswith(suffix)]
        if profile == "core":
            paths = [path for path in paths if "." not in path.stem]
    if limit:
        paths = paths[-limit:]

    total_inserted = 0
    total_updated = 0
    processed = 0
    for path in paths:
        name = path.stem
        parts = name.split(".", 1)
        run_date = date.fromisoformat(parts[0])
        path_profile = parts[1] if len(parts) > 1 else "core"
        facts = extract_facts(path.read_text(encoding="utf-8"), path_profile, run_date)
        seen_at = datetime.now(UTC).isoformat()
        inserted, updated = upsert_facts(conn, facts, seen_at)
        record_ingest(conn, path, path_profile, run_date, seen_at, len(facts))
        total_inserted += inserted
        total_updated += updated
        processed += 1
    return processed, total_inserted, total_updated


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the sweep fact notebook from daily digest markdown.")
    parser.add_argument("--input", dest="input_path", help="Explicit digest markdown path.")
    parser.add_argument("--profile", choices=("core", "extended", "all"), default="core")
    parser.add_argument("--date", dest="run_date", help="Digest date in YYYY-MM-DD format.")
    parser.add_argument("--db", default=str(DEFAULT_DB), help="SQLite notebook path.")
    parser.add_argument("--dry-run", action="store_true", help="Extract facts without writing SQLite.")
    parser.add_argument("--recent", type=int, default=0, help="Print recent facts after ingest.")
    parser.add_argument("--backfill", action="store_true", help="Ingest existing daily digest markdown files.")
    parser.add_argument("--limit", type=int, default=0, help="Limit rows for query/backfill commands.")
    parser.add_argument("--topic", default="", help="Print facts for a topic.")
    parser.add_argument("--source", default="", help="Print facts matching a source name.")
    parser.add_argument("--stats", action="store_true", help="Print fact notebook counts.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    db_path = Path(args.db)
    if not db_path.is_absolute():
        db_path = ROOT / db_path
    conn = connect(db_path)
    init_db(conn)

    if args.backfill:
        processed, inserted, updated = backfill(conn, args.profile, args.limit)
        print({"digests": processed, "inserted": inserted, "updated": updated, "db": str(db_path)})
        conn.close()
        return 0

    if args.stats:
        print_stats(conn)
        conn.close()
        return 0

    if args.topic or args.source:
        print_query(conn, args.topic, args.source, args.limit or 20)
        conn.close()
        return 0

    run_date = date.fromisoformat(args.run_date) if args.run_date else date.today()
    path = Path(args.input_path) if args.input_path else digest_path(args.profile, run_date)
    if not path.is_absolute():
        path = ROOT / path
    if not path.exists():
        raise FileNotFoundError(path)

    markdown = path.read_text(encoding="utf-8")
    facts = extract_facts(markdown, args.profile, run_date)
    if args.dry_run:
        print({"facts": len(facts), "input": str(path)})
        for fact in facts[:10]:
            print(f"[{fact['topic']}] {fact['claim_text']}")
        conn.close()
        return 0

    seen_at = datetime.now(UTC).isoformat()
    inserted, updated = upsert_facts(conn, facts, seen_at)
    record_ingest(conn, path, args.profile, run_date, seen_at, len(facts))
    print({"facts": len(facts), "inserted": inserted, "updated": updated, "db": str(db_path)})
    if args.recent:
        print_recent(conn, args.recent)
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
