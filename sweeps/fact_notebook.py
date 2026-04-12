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
CHANGE_TYPES = {
    "release",
    "feature",
    "deprecation",
    "bugfix",
    "benchmark",
    "architecture",
    "compatibility",
    "breaking_change",
}
STACK_RELEVANCE = {"high", "medium", "low", "none"}


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


def entity_for_item(title: str, source_name: str) -> str:
    text = f"{title} {source_name}".lower()
    entities = (
        ("llama.cpp", ("llama.cpp", "ggml")),
        ("Ollama", ("ollama",)),
        ("vLLM", ("vllm",)),
        ("RTX 3090", ("3090", "rtx 3090")),
        ("CUDA", ("cuda",)),
        ("Gemma", ("gemma", "gemma4")),
        ("Qwen", ("qwen",)),
        ("ServeTheHome", ("servethehome",)),
        ("Simon Willison", ("simon willison", "simonw")),
        ("Karpathy", ("karpathy",)),
        ("Hugging Face", ("hugging face",)),
    )
    for entity, needles in entities:
        if any(needle in text for needle in needles):
            return entity
    return source_name or "unknown"


def change_type_for_item(title: str) -> str:
    text = title.lower()
    if any(token in text for token in ("breaking", "remove ", "removed", "incompatible")):
        return "breaking_change"
    if any(token in text for token in ("deprecat", "obsolete")):
        return "deprecation"
    if any(token in text for token in ("fix", "repair", "bug", "regression", "where it doesn't work")):
        return "bugfix"
    if any(token in text for token in ("benchmark", "leaderboard", "perf", "throughput", "latency", "tokens/s")):
        return "benchmark"
    if any(token in text for token in ("tensor parallel", "pipeline parallel", "kv cache", "offload", "architecture", "ralph loop", "notebook")):
        return "architecture"
    if any(token in text for token in ("compat", "support", "cuda", "vulkan", "hip", "older gpus", "gpu")):
        return "compatibility"
    if any(token in text for token in ("release", "released", "v0.", "v1.", "v2.", "v3.", "b8")):
        return "release"
    return "feature"


def stack_relevance_for_item(title: str, source_name: str, topic: str) -> str:
    text = f"{title} {source_name}".lower()
    high_terms = (
        "tensor parallel",
        "pipeline parallel",
        "multi-gpu",
        "split-mode",
        "cuda",
        "kv cache",
        "offload",
        "3090",
        "rtx 3090",
        "pcie",
        "blower",
        "10gbe",
        "gemma4",
    )
    medium_terms = ("ollama", "vllm", "llama.cpp", "ggml", "qwen", "gemma", "nvme", "switch", "server")
    if any(term in text for term in high_terms):
        return "high"
    if any(term in text for term in medium_terms) or topic in {"local-inference", "multi-gpu", "hardware"}:
        return "medium"
    if topic in {"workflow", "model-release"}:
        return "low"
    return "none"


def implication_for_item(title: str, source_name: str, topic: str, change_type: str, stack_relevance: str) -> str:
    text = f"{title} {source_name}".lower()
    if "tensor parallel" in text or "multi-gpu" in text or "split-mode" in text:
        return "May affect 3x3090 serving topology or split strategy."
    if "kv cache" in text or "offload" in text:
        return "May let the node trade CPU/RAM for larger context or larger served models."
    if "cuda" in text:
        return "May affect CUDA throughput or compatibility on RTX 3090."
    if "gemma4" in text or "older gpus" in text:
        return "Check compatibility with Ampere GPUs before upgrading."
    if "10gbe" in text:
        return "Potential rack/networking candidate for node-adjacent infrastructure."
    if stack_relevance == "high":
        return "Directly relevant to the Sovereign Node stack."
    if change_type == "release":
        return "Check release notes before changing local serving versions."
    if topic == "workflow":
        return "Potential workflow pattern for the sweep/wiki loop."
    return ""


def needs_followup_for_item(confidence: str, stack_relevance: str, change_type: str) -> int:
    if stack_relevance == "high":
        return 1
    if confidence == "social-primary":
        return 1
    if change_type in {"breaking_change", "deprecation"}:
        return 1
    return 0


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
            title = item.get("title", "")
            entity = entity_for_item(title, source_name)
            change_type = change_type_for_item(title)
            stack_relevance = stack_relevance_for_item(title, source_name, topic)
            implication = implication_for_item(title, source_name, topic, change_type, stack_relevance)
            needs_followup = str(needs_followup_for_item(confidence, stack_relevance, change_type))
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
                    "entity": entity,
                    "change_type": change_type,
                    "implication": implication,
                    "stack_relevance": stack_relevance,
                    "needs_followup": needs_followup,
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
            seen_count INTEGER NOT NULL DEFAULT 1,
            entity TEXT,
            change_type TEXT CHECK (change_type IS NULL OR change_type IN ('release', 'feature', 'deprecation', 'bugfix', 'benchmark', 'architecture', 'compatibility', 'breaking_change')),
            implication TEXT,
            stack_relevance TEXT CHECK (stack_relevance IS NULL OR stack_relevance IN ('high', 'medium', 'low', 'none')),
            needs_followup INTEGER CHECK (needs_followup IS NULL OR needs_followup IN (0, 1))
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
    existing_columns = {row[1] for row in conn.execute("PRAGMA table_info(facts)").fetchall()}
    migrations = {
        "entity": "ALTER TABLE facts ADD COLUMN entity TEXT",
        "change_type": (
            "ALTER TABLE facts ADD COLUMN change_type TEXT "
            "CHECK (change_type IS NULL OR change_type IN ('release', 'feature', 'deprecation', "
            "'bugfix', 'benchmark', 'architecture', 'compatibility', 'breaking_change'))"
        ),
        "implication": "ALTER TABLE facts ADD COLUMN implication TEXT",
        "stack_relevance": (
            "ALTER TABLE facts ADD COLUMN stack_relevance TEXT "
            "CHECK (stack_relevance IS NULL OR stack_relevance IN ('high', 'medium', 'low', 'none'))"
        ),
        "needs_followup": "ALTER TABLE facts ADD COLUMN needs_followup INTEGER CHECK (needs_followup IS NULL OR needs_followup IN (0, 1))",
    }
    for column, sql in migrations.items():
        if column not in existing_columns:
            conn.execute(sql)
    conn.executescript(
        """
        CREATE INDEX IF NOT EXISTS idx_facts_entity ON facts(entity);
        CREATE INDEX IF NOT EXISTS idx_facts_change_type ON facts(change_type);
        CREATE INDEX IF NOT EXISTS idx_facts_stack_relevance ON facts(stack_relevance);
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
                    profile = ?, entity = ?, change_type = ?, implication = ?, stack_relevance = ?,
                    needs_followup = ?, last_seen = ?, seen_count = seen_count + 1
                WHERE id = ?
                """,
                (
                    fact["claim_text"],
                    fact["published_at"],
                    fact["topic"],
                    fact["lane"],
                    fact["confidence"],
                    fact["profile"],
                    fact["entity"],
                    fact["change_type"],
                    fact["implication"],
                    fact["stack_relevance"],
                    int(fact["needs_followup"]),
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
                    topic, lane, confidence, profile, first_seen, last_seen, seen_count,
                    entity, change_type, implication, stack_relevance, needs_followup
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?, ?)
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
                    fact["entity"],
                    fact["change_type"],
                    fact["implication"],
                    fact["stack_relevance"],
                    int(fact["needs_followup"]),
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
    print("stack relevance:")
    for relevance, count in conn.execute(
        "SELECT COALESCE(stack_relevance, 'unknown'), COUNT(*) FROM facts GROUP BY stack_relevance ORDER BY COUNT(*) DESC"
    ):
        print(f"- {relevance}: {count}")
    print("change types:")
    for change_type, count in conn.execute(
        "SELECT COALESCE(change_type, 'unknown'), COUNT(*) FROM facts GROUP BY change_type ORDER BY COUNT(*) DESC"
    ):
        print(f"- {change_type}: {count}")
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
