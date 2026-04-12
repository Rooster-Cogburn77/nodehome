#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sqlite3
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from sweeps.fact_notebook import (
    DEFAULT_DB,
    assumption_pressure_rows,
    connect,
    followup_reason,
    followup_rows,
    init_db,
)


ROOT = Path(__file__).resolve().parent.parent
WEEKLY_DIR = ROOT / "docs" / "sweeps" / "weekly"

def iso_week_label(run_date: date) -> str:
    year, week, _ = run_date.isocalendar()
    return f"{year}-W{week:02d}"


def week_bounds(run_date: date) -> tuple[str, str]:
    monday = run_date - timedelta(days=run_date.isoweekday() - 1)
    sunday = monday + timedelta(days=6)
    return monday.isoformat(), sunday.isoformat()


def output_path_for(run_date: date, profile: str) -> Path:
    suffix = "" if profile == "core" else f".{profile}"
    return WEEKLY_DIR / f"{iso_week_label(run_date)}{suffix}.md"


def profile_filter(profile: str) -> tuple[str, list[str]]:
    if profile == "all":
        return "", []
    return "AND profile = ?", [profile]


def fetch_rows(
    conn: sqlite3.Connection,
    sql: str,
    params: list[str | int],
) -> list[sqlite3.Row]:
    conn.row_factory = sqlite3.Row
    return conn.execute(sql, params).fetchall()


def top_themes(conn: sqlite3.Connection, start: str, end: str, profile: str) -> list[sqlite3.Row]:
    extra, params = profile_filter(profile)
    return fetch_rows(
        conn,
        f"""
        SELECT topic, COUNT(*) AS count, COUNT(DISTINCT source_name) AS sources
        FROM facts
        WHERE substr(first_seen, 1, 10) BETWEEN ? AND ?
        {extra}
        GROUP BY topic
        ORDER BY count DESC, sources DESC, topic ASC
        LIMIT 8
        """,
        [start, end, *params],
    )


def reinforced_signals(conn: sqlite3.Connection, start: str, end: str, profile: str) -> list[sqlite3.Row]:
    extra, params = profile_filter(profile)
    return fetch_rows(
        conn,
        f"""
        SELECT topic, source_name, claim_text, source_url, seen_count, entity, change_type, implication, stack_relevance
        FROM facts
        WHERE substr(last_seen, 1, 10) BETWEEN ? AND ?
        AND seen_count > 1
        {extra}
        ORDER BY seen_count DESC, last_seen DESC
        LIMIT 12
        """,
        [start, end, *params],
    )


def new_facts(conn: sqlite3.Connection, start: str, end: str, profile: str) -> list[sqlite3.Row]:
    extra, params = profile_filter(profile)
    return fetch_rows(
        conn,
        f"""
        SELECT topic, source_name, claim_text, source_url, confidence, entity, change_type, implication, stack_relevance
        FROM facts
        WHERE substr(first_seen, 1, 10) BETWEEN ? AND ?
        {extra}
        ORDER BY
            CASE confidence WHEN 'social-primary' THEN 0 WHEN 'primary' THEN 1 ELSE 2 END,
            topic ASC,
            source_name ASC
        LIMIT 20
        """,
        [start, end, *params],
    )


def sovereign_node_impact(conn: sqlite3.Connection, start: str, end: str, profile: str) -> list[sqlite3.Row]:
    extra, params = profile_filter(profile)
    return fetch_rows(
        conn,
        f"""
        SELECT topic, source_name, claim_text, source_url, seen_count, entity, change_type, implication, stack_relevance
        FROM facts
        WHERE substr(first_seen, 1, 10) BETWEEN ? AND ?
        AND stack_relevance = 'high'
        AND NOT (
            (claim_text GLOB 'b[0-9]*' OR claim_text GLOB 'v[0-9]*')
            AND instr(claim_text, ':') = 0
        )
        {extra}
        ORDER BY
            CASE
                WHEN lower(claim_text) LIKE '%tensor parallel%' THEN 0
                WHEN lower(claim_text) LIKE '%multi-gpu%' THEN 0
                WHEN lower(claim_text) LIKE '%cuda%' THEN 1
                WHEN lower(claim_text) LIKE '%kv cache%' THEN 1
                WHEN lower(claim_text) LIKE '%offload%' THEN 1
                WHEN lower(claim_text) LIKE '%3090%' THEN 2
                WHEN lower(claim_text) LIKE '%10gbe%' THEN 2
                WHEN lower(claim_text) LIKE '%gemma4%' THEN 3
                WHEN lower(claim_text) LIKE '%qwen%' THEN 3
                ELSE 9
            END,
            seen_count DESC,
            source_name ASC
        LIMIT 12
        """,
        [start, end, *params],
    )


def article_candidates(conn: sqlite3.Connection, start: str, end: str, profile: str) -> list[sqlite3.Row]:
    extra, params = profile_filter(profile)
    return fetch_rows(
        conn,
        f"""
        SELECT topic, source_name, claim_text, source_url, seen_count, entity, change_type, implication, stack_relevance
        FROM facts
        WHERE substr(first_seen, 1, 10) BETWEEN ? AND ?
        AND (
            confidence = 'social-primary'
            OR seen_count > 1
            OR stack_relevance = 'high'
        )
        AND NOT (
            (claim_text GLOB 'b[0-9]*' OR claim_text GLOB 'v[0-9]*')
            AND instr(claim_text, ':') = 0
            AND stack_relevance != 'high'
        )
        {extra}
        ORDER BY
            seen_count DESC,
            CASE
                WHEN lower(claim_text) LIKE '%tensor parallel%' THEN 0
                WHEN lower(claim_text) LIKE '%multi-gpu%' THEN 0
                WHEN lower(claim_text) LIKE '%cuda%' THEN 1
                WHEN lower(claim_text) LIKE '%offload%' THEN 1
                ELSE 5
            END,
            topic ASC,
            source_name ASC
        LIMIT 12
        """,
        [start, end, *params],
    )


def render_fact(row: sqlite3.Row, include_seen: bool = False) -> str:
    suffix = ""
    meta = []
    if "entity" in row.keys() and row["entity"]:
        meta.append(row["entity"])
    if "change_type" in row.keys() and row["change_type"]:
        meta.append(row["change_type"])
    if "stack_relevance" in row.keys() and row["stack_relevance"]:
        meta.append(f"stack:{row['stack_relevance']}")
    if meta:
        suffix += f" [{', '.join(meta)}]"
    if row["source_url"]:
        suffix += f" ({row['source_url']})"
    if include_seen and "seen_count" in row.keys():
        suffix += f" — seen {row['seen_count']}x"
    implication = ""
    if "implication" in row.keys() and row["implication"]:
        implication = f" Implication: {row['implication']}"
    return f"- [{row['topic']}] {row['claim_text']} — {row['source_name']}{suffix}{implication}"


def render_followup(row: sqlite3.Row) -> str:
    source = f" ({row['source_url']})" if row["source_url"] else ""
    implication = f" Implication: {row['implication']}" if row["implication"] else ""
    return (
        f"- [{row['entity'] or 'unknown'} | {row['change_type']} | stack:{row['stack_relevance']} | "
        f"{followup_reason(row)}] {row['claim_text']} — {row['source_name']}{source}{implication}"
    )


def render_assumption_pressure(row: sqlite3.Row) -> str:
    source = f" ({row['source_url']})" if row["source_url"] else ""
    implication = f" Implication: {row['implication']}" if row["implication"] else ""
    return (
        f"- [{row['assumption_entity']} | {row['change_type']} | {row['fact_id']}] "
        f"{row['assumption_claim']} Pressure: {row['fact_claim']} - {row['source_name']}{source}{implication}"
    )


def build_weekly(run_date: date, profile: str, db_path: Path = DEFAULT_DB) -> Path:
    WEEKLY_DIR.mkdir(parents=True, exist_ok=True)
    output_path = output_path_for(run_date, profile)
    if not db_path.is_absolute():
        db_path = ROOT / db_path

    conn = connect(db_path)
    init_db(conn)
    start, end = week_bounds(run_date)
    themes = top_themes(conn, start, end, profile)
    reinforced = reinforced_signals(conn, start, end, profile)
    node_impact = sovereign_node_impact(conn, start, end, profile)
    new_items = new_facts(conn, start, end, profile)
    candidates = article_candidates(conn, start, end, profile)
    pressure = assumption_pressure_rows(conn, profile, 12, start, end)
    gaps = followup_rows(conn, profile, 12)
    conn.close()

    lines = [
        f"# Weekly Sweep Rollup - {iso_week_label(run_date)} ({profile})",
        "",
        f"Generated at {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')}",
        f"Fact window: {start} to {end}",
        "",
        "## Top Themes",
        "",
    ]
    if themes:
        for row in themes:
            lines.append(f"- {row['topic']}: {row['count']} facts across {row['sources']} sources")
    else:
        lines.append("- No notebook facts recorded for this week.")

    lines.extend(["", "## Sovereign Node Impact", ""])
    if node_impact:
        for row in node_impact:
            lines.append(render_fact(row, include_seen=True))
    else:
        lines.append("- No direct stack-impact facts found this week.")

    lines.extend(["", "## Reinforced Signals", ""])
    if reinforced:
        for row in reinforced:
            lines.append(render_fact(row, include_seen=True))
    else:
        lines.append("- No reinforced facts yet.")

    lines.extend(["", "## New Facts This Week", ""])
    if new_items:
        for row in new_items:
            lines.append(render_fact(row))
    else:
        lines.append("- No new facts recorded this week.")

    lines.extend(["", "## Article Candidates", ""])
    if candidates:
        for row in candidates:
            lines.append(render_fact(row, include_seen=True))
    else:
        lines.append("- No article candidates yet.")

    lines.extend(["", "## Assumption Pressure", ""])
    if pressure:
        for row in pressure:
            lines.append(render_assumption_pressure(row))
    else:
        lines.append("- No active assumptions under pressure this week.")

    lines.extend(["", "## Gaps / Follow-Up", ""])
    if gaps:
        for row in gaps:
            lines.append(render_followup(row))
    else:
        lines.append("- No structured follow-up candidates detected.")

    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a weekly sweep rollup from the fact notebook.")
    parser.add_argument("--date", dest="run_date", help="Anchor date in YYYY-MM-DD format.")
    parser.add_argument("--week", help="ISO week label, e.g. 2026-W15. Overrides --date.")
    parser.add_argument("--profile", choices=("core", "extended", "all"), default="core")
    parser.add_argument("--db", default=str(DEFAULT_DB), help="SQLite notebook path.")
    return parser.parse_args()


def date_from_week(label: str) -> date:
    year_text, week_text = label.split("-W", 1)
    return date.fromisocalendar(int(year_text), int(week_text), 1)


def main() -> int:
    args = parse_args()
    if args.week:
        run_date = date_from_week(args.week)
    else:
        run_date = date.fromisoformat(args.run_date) if args.run_date else date.today()
    db_path = Path(args.db)
    output_path = build_weekly(run_date, args.profile, db_path)
    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
