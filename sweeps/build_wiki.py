#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
import re

from sweeps.fact_notebook import DEFAULT_DB, connect, init_db


ROOT = Path(__file__).resolve().parent.parent
WIKI_DIR = ROOT / "docs" / "wiki"
GENERATED_DIR = WIKI_DIR / "generated"
ENTITY_DIR = GENERATED_DIR / "entities"
SOURCE_DIR = GENERATED_DIR / "sources"
BRIEFING_DIR = GENERATED_DIR / "briefings"
GENERATED_INDEX = GENERATED_DIR / "index.md"
GENERATED_LOG = GENERATED_DIR / "log.md"
LATEST_BRIEFING = BRIEFING_DIR / "latest.md"
WEEKLY_DIR = ROOT / "docs" / "sweeps" / "weekly"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build generated wiki pages from the sweep fact notebook.")
    parser.add_argument("--db", default=str(DEFAULT_DB), help="SQLite notebook path.")
    parser.add_argument("--profile", choices=("core", "extended", "all"), default="all")
    parser.add_argument("--entity-limit", type=int, default=10, help="Number of entity pages to generate.")
    parser.add_argument("--source-limit", type=int, default=10, help="Number of source pages to generate.")
    return parser.parse_args()


def resolve_db(path: str) -> Path:
    db_path = Path(path)
    if not db_path.is_absolute():
        db_path = ROOT / db_path
    return db_path


def mkdirs() -> None:
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    ENTITY_DIR.mkdir(parents=True, exist_ok=True)
    SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    BRIEFING_DIR.mkdir(parents=True, exist_ok=True)


def slugify(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = re.sub(r"-+", "-", value).strip("-")
    return value or "unknown"


def clean_text(value: str) -> str:
    value = " ".join(value.split())
    for marker in (" â€” ", " — ", " Ã¢â‚¬â€ "):
        if marker in value:
            return value.split(marker, 1)[0].strip()
    return value.strip()


def profile_clause(profile: str) -> tuple[str, list[str]]:
    if profile == "all":
        return "", []
    return "AND profile = ?", [profile]


def latest_weekly(profile: str) -> Path | None:
    pattern = "*.md" if profile == "all" else ("*.md" if profile == "core" else f"*.{profile}.md")
    candidates = []
    for path in WEEKLY_DIR.glob(pattern):
        if profile == "core" and "." in path.stem:
            continue
        candidates.append(path)
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


def extract_briefing(path: Path | None) -> tuple[str, list[str]]:
    if path is None or not path.exists():
        return ("No weekly briefing generated yet.", [])
    lines = path.read_text(encoding="utf-8").splitlines()
    in_briefing = False
    paragraph = []
    what_changed = []
    in_what_changed = False
    in_themes = False
    fallback_paragraph = []
    for line in lines:
        stripped = line.strip()
        if stripped == "## Briefing":
            in_briefing = True
            in_what_changed = False
            in_themes = False
            continue
        if stripped.startswith("## "):
            if stripped == "## What Changed":
                in_what_changed = True
                in_briefing = False
                in_themes = False
                continue
            if stripped == "## Themes":
                in_themes = True
                in_briefing = False
                in_what_changed = False
                continue
            in_briefing = False
            in_what_changed = False
            in_themes = False
        if in_briefing and stripped:
            paragraph.append(stripped)
        elif in_what_changed and stripped.startswith("- "):
            what_changed.append(stripped)
        elif not stripped.startswith("#") and stripped and not paragraph and not in_what_changed and not in_themes:
            fallback_paragraph.append(stripped)
        elif in_themes and stripped.startswith("- "):
            what_changed.append(stripped)
    summary = " ".join(paragraph).strip() or " ".join(fallback_paragraph).strip()
    if not summary and what_changed:
        summary = "Latest weekly source is using a legacy rollup format, so only section bullets were recovered."
    if not summary:
        summary = "No weekly briefing generated yet."
    return (summary, what_changed[:6])


def fetch_rows(conn: sqlite3.Connection, sql: str, params: list[str | int]) -> list[sqlite3.Row]:
    conn.row_factory = sqlite3.Row
    return conn.execute(sql, params).fetchall()


def top_entities(conn: sqlite3.Connection, profile: str, limit: int) -> list[sqlite3.Row]:
    extra, params = profile_clause(profile)
    return fetch_rows(
        conn,
        f"""
        SELECT
            entity,
            COUNT(*) AS fact_count,
            SUM(CASE WHEN stack_relevance = 'high' THEN 1 ELSE 0 END) AS high_count,
            MAX(last_seen) AS last_seen
        FROM facts
        WHERE entity IS NOT NULL
          AND entity != ''
          AND stack_relevance IN ('high', 'medium', 'low')
          {extra}
        GROUP BY entity
        ORDER BY high_count DESC, fact_count DESC, entity ASC
        LIMIT ?
        """,
        [*params, limit],
    )


def entity_facts(conn: sqlite3.Connection, entity: str, profile: str, limit: int = 12) -> list[sqlite3.Row]:
    extra, params = profile_clause(profile)
    return fetch_rows(
        conn,
        f"""
        SELECT claim_text, source_name, source_url, topic, change_type, implication, stack_relevance, seen_count, last_seen
        FROM facts
        WHERE entity = ?
          {extra}
        ORDER BY
            CASE stack_relevance WHEN 'high' THEN 0 WHEN 'medium' THEN 1 WHEN 'low' THEN 2 ELSE 3 END,
            seen_count DESC,
            last_seen DESC
        LIMIT ?
        """,
        [entity, *params, limit],
    )


def top_sources(conn: sqlite3.Connection, profile: str, limit: int) -> list[sqlite3.Row]:
    extra, params = profile_clause(profile)
    return fetch_rows(
        conn,
        f"""
        SELECT source_name, COUNT(*) AS fact_count, MAX(last_seen) AS last_seen
        FROM facts
        WHERE source_name IS NOT NULL
          AND source_name != ''
          {extra}
        GROUP BY source_name
        ORDER BY fact_count DESC, source_name ASC
        LIMIT ?
        """,
        [*params, limit],
    )


def source_facts(conn: sqlite3.Connection, source_name: str, profile: str, limit: int = 12) -> list[sqlite3.Row]:
    extra, params = profile_clause(profile)
    return fetch_rows(
        conn,
        f"""
        SELECT claim_text, source_url, topic, entity, change_type, implication, stack_relevance, seen_count, last_seen
        FROM facts
        WHERE source_name = ?
          {extra}
        ORDER BY
            CASE stack_relevance WHEN 'high' THEN 0 WHEN 'medium' THEN 1 WHEN 'low' THEN 2 ELSE 3 END,
            seen_count DESC,
            last_seen DESC
        LIMIT ?
        """,
        [source_name, *params, limit],
    )


def recent_ingests(conn: sqlite3.Connection, limit: int = 20) -> list[sqlite3.Row]:
    return fetch_rows(
        conn,
        """
        SELECT digest_path, profile, digest_date, ingested_at, fact_count
        FROM ingests
        ORDER BY ingested_at DESC
        LIMIT ?
        """,
        [limit],
    )


def recent_actions(conn: sqlite3.Connection, limit: int = 20) -> list[sqlite3.Row]:
    return fetch_rows(
        conn,
        """
        SELECT fact_actions.fact_id, fact_actions.status, fact_actions.note, fact_actions.updated_at, facts.claim_text
        FROM fact_actions
        JOIN facts ON facts.id = fact_actions.fact_id
        ORDER BY fact_actions.updated_at DESC
        LIMIT ?
        """,
        [limit],
    )


def render_fact_line(row: sqlite3.Row, source_first: bool = False) -> str:
    lead = row["source_name"] if source_first and "source_name" in row.keys() else row["entity"] if "entity" in row.keys() and row["entity"] else row["topic"]
    meta = []
    if "change_type" in row.keys() and row["change_type"]:
        meta.append(row["change_type"])
    if "stack_relevance" in row.keys() and row["stack_relevance"]:
        meta.append(f"stack:{row['stack_relevance']}")
    if "seen_count" in row.keys():
        meta.append(f"seen:{row['seen_count']}")
    meta_text = f" [{' | '.join(meta)}]" if meta else ""
    implication = f" {row['implication']}" if "implication" in row.keys() and row["implication"] else ""
    source_url = ""
    if "source_url" in row.keys() and row["source_url"]:
        source_url = f" Source: {row['source_url']}"
    return f"- [{lead}] {clean_text(row['claim_text'])}.{meta_text}{implication}{source_url}"


def write_latest_briefing(profile: str) -> None:
    weekly = latest_weekly(profile)
    briefing, changes = extract_briefing(weekly)
    lines = [
        "# Latest Sweep Briefing",
        "",
        f"Generated at {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')}",
        f"Profile: {profile}",
        f"Weekly source: {weekly.relative_to(ROOT) if weekly else 'none'}",
        "",
        "## Summary",
        "",
        briefing,
        "",
        "## What Changed",
        "",
    ]
    if changes:
        lines.extend(changes)
    else:
        lines.append("- No weekly briefing changes available yet.")
    LATEST_BRIEFING.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_entity_pages(conn: sqlite3.Connection, profile: str, limit: int) -> list[tuple[str, Path, int, int]]:
    written = []
    for row in top_entities(conn, profile, limit):
        entity = row["entity"]
        path = ENTITY_DIR / f"{slugify(entity)}.md"
        facts = entity_facts(conn, entity, profile)
        lines = [
            f"# {entity}",
            "",
            "type: generated",
            f"profile: {profile}",
            f"facts: {row['fact_count']}",
            f"stack_high: {row['high_count']}",
            f"last_seen: {row['last_seen']}",
            "",
            "## Current Read",
            "",
            f"{entity} appears in {row['fact_count']} notebook facts, with {row['high_count']} high-relevance items.",
            "",
            "## Recent Facts",
            "",
        ]
        if facts:
            lines.extend(render_fact_line(fact) for fact in facts)
        else:
            lines.append("- No facts recorded.")
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        written.append((entity, path, int(row["fact_count"]), int(row["high_count"])))
    return written


def write_source_pages(conn: sqlite3.Connection, profile: str, limit: int) -> list[tuple[str, Path, int]]:
    written = []
    for row in top_sources(conn, profile, limit):
        source_name = row["source_name"]
        path = SOURCE_DIR / f"{slugify(source_name)}.md"
        facts = source_facts(conn, source_name, profile)
        lines = [
            f"# {source_name}",
            "",
            "type: generated",
            f"profile: {profile}",
            f"facts: {row['fact_count']}",
            f"last_seen: {row['last_seen']}",
            "",
            "## Current Read",
            "",
            f"{source_name} has produced {row['fact_count']} notebook facts in the current store.",
            "",
            "## Recent Facts",
            "",
        ]
        if facts:
            lines.extend(render_fact_line(fact) for fact in facts)
        else:
            lines.append("- No facts recorded.")
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        written.append((source_name, path, int(row["fact_count"])))
    return written


def write_generated_log(conn: sqlite3.Connection) -> None:
    ingests = recent_ingests(conn)
    actions = recent_actions(conn)
    lines = [
        "# Generated Wiki Log",
        "",
        f"Generated at {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        "## Recent Ingests",
        "",
    ]
    if ingests:
        for row in ingests:
            lines.append(
                f"- [{row['digest_date']} | {row['profile']}] {Path(row['digest_path']).name} -> {row['fact_count']} facts at {row['ingested_at']}"
            )
    else:
        lines.append("- No ingests recorded.")
    lines.extend(["", "## Recent Actions", ""])
    if actions:
        for row in actions:
            note = f" Note: {row['note']}" if row["note"] else ""
            lines.append(f"- [{row['status']}] {row['fact_id'][:12]} -> {clean_text(row['claim_text'])}.{note}")
    else:
        lines.append("- No fact actions recorded.")
    GENERATED_LOG.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_generated_index(
    profile: str,
    entity_pages: list[tuple[str, Path, int, int]],
    source_pages: list[tuple[str, Path, int]],
) -> None:
    lines = [
        "# Generated Wiki Index",
        "",
        f"Generated at {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')}",
        f"Profile: {profile}",
        "",
        "This layer is generated from the sweep fact notebook. Treat it as a browsable view, not the source of truth.",
        "",
        "## Entry Points",
        "",
        f"- [Latest Briefing](briefings/{LATEST_BRIEFING.name})",
        f"- [Generated Log]({GENERATED_LOG.name})",
        "",
        "## Entities",
        "",
    ]
    if entity_pages:
        for entity, path, fact_count, high_count in entity_pages:
            rel = path.relative_to(GENERATED_DIR)
            lines.append(f"- [{entity}]({rel.as_posix()}) - {fact_count} facts, {high_count} high-relevance")
    else:
        lines.append("- No entity pages generated.")
    lines.extend(["", "## Sources", ""])
    if source_pages:
        for source_name, path, fact_count in source_pages:
            rel = path.relative_to(GENERATED_DIR)
            lines.append(f"- [{source_name}]({rel.as_posix()}) - {fact_count} facts")
    else:
        lines.append("- No source pages generated.")
    GENERATED_INDEX.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    db_path = resolve_db(args.db)
    mkdirs()
    conn = connect(db_path)
    init_db(conn)
    entity_pages = write_entity_pages(conn, args.profile, args.entity_limit)
    source_pages = write_source_pages(conn, args.profile, args.source_limit)
    write_generated_log(conn)
    conn.close()
    write_latest_briefing(args.profile)
    write_generated_index(args.profile, entity_pages, source_pages)
    print(GENERATED_INDEX)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
