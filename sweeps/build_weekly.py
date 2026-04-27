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
MOJIBAKE_MARKERS = ("â", "ð", "Ã", "œ", "€", "ā")


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


def repair_text(text: str) -> str:
    if not text:
        return ""
    replacements = {
        "â€”": "—",
        "â€“": "–",
        "â€™": "’",
        "â€œ": "“",
        "â€": "”",
        "â€˜": "‘",
        "ðŸ¡": "🐡",
        "ðŸŸ": "🐟",
        "â€œtrueâ€": "“true”",
    }
    for bad, good in replacements.items():
        text = text.replace(bad, good)
    if not any(marker in text for marker in MOJIBAKE_MARKERS):
        return text.strip()
    try:
        repaired = text.encode("latin-1", errors="ignore").decode("utf-8", errors="ignore")
    except Exception:  # noqa: BLE001
        return text.strip()
    return repaired.strip() or text.strip()


def clean_claim(text: str) -> str:
    text = repair_text(text)
    for marker in (" ā€” ", " — "):
        if marker in text:
            return text.split(marker, 1)[0].strip()
    return text.strip()


def source_suffix(row: sqlite3.Row) -> str:
    if row["source_url"]:
        return f" Source: {repair_text(row['source_name'])} ({row['source_url']})"
    return f" Source: {repair_text(row['source_name'])}"


def triage_command(action: str, fact_id: str) -> str:
    return f'python -m sweeps.fact_notebook --{action} {fact_id} --note "<note>"'


def render_brief_fact(row: sqlite3.Row, include_seen: bool = False) -> str:
    entity = row["entity"] if "entity" in row.keys() and row["entity"] else row["topic"]
    seen = f" Seen {row['seen_count']}x." if include_seen and "seen_count" in row.keys() else ""
    implication = f" {repair_text(row['implication'])}" if "implication" in row.keys() and row["implication"] else ""
    return f"- [{entity}] {clean_claim(row['claim_text'])}.{seen}{implication}{source_suffix(row)}"


def render_brief_followup(row: sqlite3.Row) -> str:
    implication = f" {repair_text(row['implication'])}" if row["implication"] else ""
    short_id = row["id"][:12]
    review = triage_command("review", short_id)
    done = triage_command("done", short_id)
    return (
        f"- [{row['entity'] or 'unknown'} | {followup_reason(row)}] "
        f"{clean_claim(row['claim_text'])}.{implication}{source_suffix(row)} "
        f"Fact: `{short_id}`. Review: `{review}`. Done: `{done}`."
    )


def render_brief_pressure(row: sqlite3.Row) -> str:
    implication = f" {repair_text(row['implication'])}" if row["implication"] else ""
    return (
        f"- [{row['severity']} | {row['assumption_entity']}] "
        f"{clean_claim(row['fact_claim'])}. Pressures: {row['assumption_ids']}.{implication}{source_suffix(row)}"
    )


def noisy_release_claim(text: str) -> bool:
    text = clean_claim(text).lower()
    return text.startswith(("v0.20.4", "v0.20.3", "b87"))


def unique_node_rows(rows: list[sqlite3.Row], exclude_claims: set[str], limit: int) -> list[sqlite3.Row]:
    selected = []
    seen_entities = set()
    seen_claims = set(exclude_claims)
    for row in rows:
        claim = clean_claim(row["claim_text"])
        entity = row["entity"] or row["topic"]
        if claim in seen_claims or noisy_release_claim(claim):
            continue
        if entity in seen_entities and len(selected) >= 3:
            continue
        selected.append(row)
        seen_entities.add(entity)
        seen_claims.add(claim)
        if len(selected) == limit:
            break
    return selected


def dedupe_rows(rows: list[sqlite3.Row], claim_key: str, limit: int) -> list[sqlite3.Row]:
    selected = []
    seen_claims = set()
    for row in rows:
        claim = clean_claim(row[claim_key])
        if claim in seen_claims:
            continue
        selected.append(row)
        seen_claims.add(claim)
        if len(selected) >= limit:
            break
    return selected


def dedupe_output_lines(lines: list[str]) -> list[str]:
    deduped = []
    seen = set()
    for line in lines:
        key = repair_text(line) if line.startswith("- [") else line
        if key in seen:
            continue
        deduped.append(repair_text(line))
        seen.add(key)
    return deduped


def build_briefing(
    themes: list[sqlite3.Row],
    node_impact: list[sqlite3.Row],
    pressure: list[sqlite3.Row],
    gaps: list[sqlite3.Row],
) -> str:
    if not themes and not node_impact and not pressure:
        return "Quiet week. The notebook did not surface enough new signal to justify a strong read."

    sentences = []
    if pressure:
        first = pressure[0]
        sentences.append(f"The main thing to watch is {first['assumption_entity']}: {clean_claim(first['fact_claim'])}.")
    elif node_impact:
        first = node_impact[0]
        sentences.append(f"The strongest Sovereign Node signal is {clean_claim(first['claim_text'])}.")
    else:
        top = themes[0]
        sentences.append(f"The week was mostly {top['topic']} signal across {top['sources']} sources.")

    if node_impact:
        entities = []
        for row in node_impact:
            entity = row["entity"] or row["topic"]
            if entity not in entities:
                entities.append(entity)
            if len(entities) == 3:
                break
        sentences.append(f"Stack-relevant coverage clustered around {', '.join(entities)}.")

    if gaps:
        sentences.append(f"There are {len(gaps)} open follow-up items worth triaging from the notebook.")

    if themes:
        top_topics = ", ".join(row["topic"] for row in themes[:3])
        sentences.append(f"Top lanes this week: {top_topics}.")

    return " ".join(sentences)


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
        implication = f" Implication: {repair_text(row['implication'])}"
    return f"- [{row['topic']}] {repair_text(row['claim_text'])} — {repair_text(row['source_name'])}{suffix}{implication}"


def render_followup(row: sqlite3.Row) -> str:
    source = f" ({row['source_url']})" if row["source_url"] else ""
    implication = f" Implication: {repair_text(row['implication'])}" if row["implication"] else ""
    return (
        f"- [{row['entity'] or 'unknown'} | {row['change_type']} | stack:{row['stack_relevance']} | "
        f"{followup_reason(row)}] {repair_text(row['claim_text'])} — {repair_text(row['source_name'])}{source}{implication}"
    )


def render_assumption_pressure(row: sqlite3.Row) -> str:
    source = f" ({row['source_url']})" if row["source_url"] else ""
    implication = f" Implication: {repair_text(row['implication'])}" if row["implication"] else ""
    assumptions = row["assumption_ids"]
    return (
        f"- [{row['severity']} | {row['assumption_entity']} | {row['change_type']} | {row['fact_id']}] "
        f"{repair_text(row['fact_claim'])} - {repair_text(row['source_name'])}{source}. Pressures: {assumptions}.{implication}"
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
    candidates = article_candidates(conn, start, end, profile)
    pressure = assumption_pressure_rows(conn, profile, 12, start, end)
    gaps = followup_rows(conn, profile, 12)
    conn.close()

    pressure_rows = dedupe_rows(pressure, "fact_claim", 6)
    followup_items = dedupe_rows(gaps, "claim_text", 6)
    briefing = build_briefing(themes, node_impact, pressure_rows, followup_items)
    pressure_claims = {clean_claim(row["fact_claim"]) for row in pressure_rows}
    extra_node_rows = unique_node_rows(node_impact, pressure_claims, 3)
    lines = [
        f"# Weekly Sweep - {iso_week_label(run_date)} ({profile})",
        "",
        f"Generated at {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')}",
        f"Fact window: {start} to {end}",
        "",
        "## Briefing",
        "",
        briefing,
        "",
        "## What Changed",
        "",
    ]
    if pressure_rows:
        for row in pressure_rows[:4]:
            lines.append(render_brief_pressure(row))
        for row in extra_node_rows:
            lines.append(render_brief_fact(row, include_seen=True))
    elif node_impact:
        for row in extra_node_rows or dedupe_rows(node_impact, "claim_text", 6):
            lines.append(render_brief_fact(row, include_seen=True))
    elif candidates:
        for row in dedupe_rows(candidates, "claim_text", 4):
            lines.append(render_brief_fact(row, include_seen=True))
    else:
        lines.append("- No strong weekly changes surfaced.")

    lines.extend(["", "## Assumptions Under Pressure", ""])
    if pressure_rows:
        for row in pressure_rows:
            lines.append(render_brief_pressure(row))
    else:
        lines.append("- No active build assumptions came under pressure this week.")

    lines.extend(["", "## Follow-Up Queue", ""])
    if followup_items:
        for row in followup_items:
            lines.append(render_brief_followup(row))
    else:
        lines.append("- No structured follow-up candidates detected.")

    lines.extend(["", "## Coverage Map", ""])
    if themes:
        for row in themes:
            lines.append(f"- {row['topic']}: {row['count']} facts across {row['sources']} sources")
    else:
        lines.append("- No notebook facts recorded for this week.")

    lines = dedupe_output_lines(lines)
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
