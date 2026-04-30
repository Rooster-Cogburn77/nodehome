#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sqlite3
from datetime import UTC, date, datetime
from pathlib import Path

from sweeps.fact_notebook import (
    DEFAULT_DB,
    assumption_pressure_rows,
    connect,
    digest_path,
    extract_facts,
    followup_reason,
    followup_rows,
    init_db,
    repair_text,
)


ROOT = Path(__file__).resolve().parent.parent
OPERATOR_DIR = ROOT / "docs" / "sweeps" / "operator"
OLLAMA_TARGETS = ("v0.21.2", "v0.21.1", "v0.21.0")
VLLM_TARGETS = ("v0.19.1", "v0.19.0")
SECTION_LIMIT = 6
FUTURE_SOURCE_LIMIT = 2
WATCH_ENTITY_LIMIT = 2


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a daily operator brief from the sweep digest and notebook.")
    parser.add_argument("--input", dest="input_path", help="Explicit digest markdown path.")
    parser.add_argument("--profile", choices=("core", "extended", "all"), default="all")
    parser.add_argument("--date", dest="run_date", help="Digest date in YYYY-MM-DD format.")
    parser.add_argument("--db", default=str(DEFAULT_DB), help="SQLite notebook path.")
    return parser.parse_args()


def resolve_db(path: str) -> Path:
    db_path = Path(path)
    if not db_path.is_absolute():
        db_path = ROOT / db_path
    return db_path


def output_path_for(run_date: date, profile: str) -> Path:
    suffix = "" if profile == "core" else f".{profile}"
    return OPERATOR_DIR / f"{run_date.isoformat()}{suffix}.md"


def clean_text(value: str) -> str:
    value = repair_text(" ".join((value or "").split()))
    for marker in (" — ", " – ", " Ã¢â‚¬â€ ", " Ã¢â‚¬â€œ ", " ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â ", " ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬â€œ "):
        if marker in value:
            return value.split(marker, 1)[0].strip()
    return value.strip()


def short_id(value: str) -> str:
    return value[:12]


def triage_command(action: str, fact_id: str) -> str:
    return f'python -m sweeps.fact_notebook --{action} {fact_id} --note "<note>"'


def fetch_issue_lines(markdown: str) -> list[str]:
    lines = markdown.splitlines()
    in_fetch = False
    items: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped == "## Fetch Issues":
            in_fetch = True
            continue
        if in_fetch and stripped.startswith("## "):
            break
        if in_fetch and stripped.startswith("- "):
            items.append(stripped)
    return items


def load_fact_rows(conn: sqlite3.Connection, fact_ids: list[str]) -> list[sqlite3.Row]:
    if not fact_ids:
        return []
    conn.row_factory = sqlite3.Row
    placeholders = ",".join("?" for _ in fact_ids)
    return conn.execute(
        f"""
        SELECT
            facts.id,
            facts.claim_text,
            facts.source_name,
            facts.source_url,
            facts.topic,
            facts.entity,
            facts.change_type,
            facts.implication,
            facts.stack_relevance,
            facts.needs_followup,
            facts.confidence,
            facts.seen_count,
            facts.last_seen,
            COALESCE(fact_actions.status, 'open') AS action_status,
            COALESCE(fact_actions.note, '') AS action_note
        FROM facts
        LEFT JOIN fact_actions ON fact_actions.fact_id = facts.id
        WHERE facts.id IN ({placeholders})
        """,
        fact_ids,
    ).fetchall()


def rank_value(row: sqlite3.Row) -> tuple[int, int, int, str]:
    stack_rank = {"high": 0, "medium": 1, "low": 2, "none": 3}.get(row["stack_relevance"] or "none", 3)
    change_rank = {
        "breaking_change": 0,
        "deprecation": 1,
        "architecture": 2,
        "compatibility": 3,
        "release": 4,
        "benchmark": 5,
        "feature": 6,
        None: 7,
    }.get(row["change_type"], 7)
    social_rank = 0 if row["confidence"] == "social-primary" else 1
    return (stack_rank, change_rank, social_rank, clean_text(row["claim_text"]).lower())


def future_architecture_candidate(row: sqlite3.Row) -> bool:
    text = f"{row['claim_text']} {row['source_name']} {row['source_url']}".lower()
    needles = (
        "conductor",
        "orchestrat",
        "multi-agent",
        "manager that delegates",
        "manager of other ais",
        "fugu",
        "openrouter",
        "routing",
        "cloudflare",
        "stripe projects",
        "api token",
        "register a domain",
        "reasoning model",
        "reasoning models",
        "llm 0.32",
    )
    return any(needle in text for needle in needles)


def release_pressure_candidate(row: sqlite3.Row) -> bool:
    if row["change_type"] != "release":
        return False
    claim = clean_text(row["claim_text"]).lower()
    entity = (row["entity"] or "").lower()
    if entity == "ollama":
        return claim.startswith("v0.") and not claim.startswith(tuple(target.lower() for target in OLLAMA_TARGETS))
    if entity == "vllm":
        return claim.startswith("v0.") and not claim.startswith(tuple(target.lower() for target in VLLM_TARGETS))
    return False


def render_fact(row: sqlite3.Row, extra: str = "") -> str:
    entity = row["entity"] or row["topic"] or "unknown"
    source = f" Source: {clean_text(row['source_name'])}" + (f" ({row['source_url']})" if row["source_url"] else "")
    implication = f" {clean_text(row['implication'])}" if row["implication"] else ""
    review = triage_command("review", short_id(row["id"]))
    done = triage_command("done", short_id(row["id"]))
    detail = f"- [{entity} | {row['change_type'] or 'feature'} | stack:{row['stack_relevance']}] {clean_text(row['claim_text'])}.{implication}{source}"
    action = f" Fact: `{short_id(row['id'])}`. Review: `{review}`. Done: `{done}`."
    if extra:
        return f"{detail}\n  Why: {extra}{action}"
    return f"{detail}{action}"


def recommendation_line(
    act_now: list[tuple[sqlite3.Row, str]],
    watch: list[tuple[sqlite3.Row, str]],
    future: list[tuple[sqlite3.Row, str]],
    fetch_issues: list[str],
) -> str:
    if act_now:
        return "- Recommendation: review the `Act now` items before changing pins or build assumptions."
    if watch:
        return "- Recommendation: no immediate action; note the `Watch` items and continue with the hardware plan."
    if future and fetch_issues:
        return "- Recommendation: no current stack action; log the future-architecture items and treat this run as partially degraded."
    if future:
        return "- Recommendation: no current stack action; only future-architecture items surfaced."
    if fetch_issues:
        return "- Recommendation: no stack action from content; monitor transport health because this run had fetch issues."
    return "- Recommendation: no meaningful operator action from this run."


def classify(
    fact_rows: list[sqlite3.Row],
    pressure_rows: list[sqlite3.Row],
    followup_fact_ids: set[str],
) -> tuple[list[tuple[sqlite3.Row, str]], list[tuple[sqlite3.Row, str]], list[tuple[sqlite3.Row, str]], dict[str, int]]:
    pressure_by_id = {row["fact_id"]: row for row in pressure_rows}
    act_now: list[tuple[sqlite3.Row, str]] = []
    watch: list[tuple[sqlite3.Row, str]] = []
    future: list[tuple[sqlite3.Row, str]] = []
    suppressed = {"release_churn": 0, "social_noise": 0, "background": 0}
    future_counts: dict[str, int] = {}
    watch_counts: dict[str, int] = {}
    seen_claims: set[str] = set()

    for row in sorted(fact_rows, key=rank_value):
        claim = clean_text(row["claim_text"]).lower()
        if claim in seen_claims:
            suppressed["background"] += 1
            continue
        seen_claims.add(claim)

        if row["action_status"] in {"reviewing", "done", "ignored"}:
            suppressed["background"] += 1
            continue

        pressure = pressure_by_id.get(row["id"])
        if pressure and pressure["severity"] == "act":
            act_now.append((row, f"Pressures active build assumptions: {pressure['assumption_ids']} ({pressure['severity']})."))
            continue
        if pressure and pressure["severity"] in {"review", "watch"}:
            entity = row["entity"] or row["source_name"] or "unknown"
            if watch_counts.get(entity, 0) >= WATCH_ENTITY_LIMIT:
                suppressed["background"] += 1
                continue
            watch_counts[entity] = watch_counts.get(entity, 0) + 1
            watch.append((row, f"Pressures active build assumptions: {pressure['assumption_ids']} ({pressure['severity']})."))
            continue

        if release_pressure_candidate(row):
            act_now.append((row, "Release pressure against a pinned serving version; review before changing targets."))
            continue

        if row["id"] in followup_fact_ids and row["stack_relevance"] == "high":
            entity = row["entity"] or row["source_name"] or "unknown"
            if watch_counts.get(entity, 0) >= WATCH_ENTITY_LIMIT:
                suppressed["background"] += 1
                continue
            watch_counts[entity] = watch_counts.get(entity, 0) + 1
            watch.append((row, f"High stack relevance and already in the follow-up queue ({followup_reason(row)})."))
            continue

        if row["stack_relevance"] == "high" and row["change_type"] in {"architecture", "compatibility", "benchmark"}:
            entity = row["entity"] or row["source_name"] or "unknown"
            if watch_counts.get(entity, 0) >= WATCH_ENTITY_LIMIT:
                suppressed["background"] += 1
                continue
            watch_counts[entity] = watch_counts.get(entity, 0) + 1
            watch.append((row, "High-relevance infra/backend change worth watching against the node plan."))
            continue

        if future_architecture_candidate(row):
            source = row["source_name"] or row["entity"] or "unknown"
            if future_counts.get(source, 0) >= FUTURE_SOURCE_LIMIT:
                suppressed["background"] += 1
                continue
            future_counts[source] = future_counts.get(source, 0) + 1
            future.append((row, "Future architecture / workflow-layer signal, not a current hardware or serving action."))
            continue

        if row["confidence"] == "social-primary" and row["stack_relevance"] in {"none", "low"}:
            suppressed["social_noise"] += 1
            continue
        if row["change_type"] == "release":
            suppressed["release_churn"] += 1
            continue
        suppressed["background"] += 1

    return act_now[:SECTION_LIMIT], watch[:SECTION_LIMIT], future[:SECTION_LIMIT], suppressed


def build_brief(run_date: date, profile: str, db_path: Path, digest_md: str) -> str:
    facts = extract_facts(digest_md, profile, run_date)
    fact_ids = [fact["id"] for fact in facts]

    conn = connect(db_path)
    init_db(conn)
    fact_rows = load_fact_rows(conn, fact_ids)
    pressure_rows = [
        row
        for row in assumption_pressure_rows(conn, profile, 50, run_date.isoformat(), run_date.isoformat())
        if row["fact_id"] in fact_ids
    ]
    followup_set = {row["id"] for row in followup_rows(conn, profile, 50) if row["id"] in fact_ids}
    conn.close()

    act_now, watch, future, suppressed = classify(fact_rows, pressure_rows, followup_set)
    fetch_issues = fetch_issue_lines(digest_md)
    surfaced = len(act_now) + len(watch) + len(future)
    suppressed_total = max(len(fact_rows) - surfaced, 0)

    lines = [
        f"# Operator Brief - {run_date.isoformat()} ({profile})",
        "",
        f"Generated at {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        f"Source digest: `{digest_path(profile, run_date).relative_to(ROOT)}`",
        "",
        "## Operator Call",
        "",
        f"- Act now: {len(act_now)}",
        f"- Watch: {len(watch)}",
        f"- Future architecture: {len(future)}",
        f"- Suppressed/background items: {suppressed_total}",
    ]
    if fetch_issues:
        lines.append(f"- Fetch issues: {len(fetch_issues)}")
    lines.append(recommendation_line(act_now, watch, future, fetch_issues))
    lines.append("")

    lines.extend(["## Act Now", ""])
    if act_now:
        for row, why in act_now:
            lines.append(render_fact(row, why))
    else:
        lines.append("- None.")
    lines.append("")

    lines.extend(["## Watch", ""])
    if watch:
        for row, why in watch:
            lines.append(render_fact(row, why))
    else:
        lines.append("- None.")
    lines.append("")

    lines.extend(["## Future Architecture", ""])
    if future:
        for row, why in future:
            lines.append(render_fact(row, why))
    else:
        lines.append("- None.")
    lines.append("")

    lines.extend(["## Suppressed", ""])
    lines.append(f"- Release churn: {suppressed['release_churn']}")
    lines.append(f"- Social/background noise: {suppressed['social_noise']}")
    lines.append(f"- Other background items: {suppressed['background']}")
    lines.append("")

    lines.extend(["## Fetch Issues", ""])
    if fetch_issues:
        lines.extend(fetch_issues)
    else:
        lines.append("- None.")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    run_date = date.fromisoformat(args.run_date) if args.run_date else date.today()
    path = Path(args.input_path) if args.input_path else digest_path(args.profile, run_date)
    if not path.is_absolute():
        path = ROOT / path
    if not path.exists():
        raise FileNotFoundError(path)

    db_path = resolve_db(args.db)
    OPERATOR_DIR.mkdir(parents=True, exist_ok=True)
    output_path = output_path_for(run_date, args.profile)
    digest_md = path.read_text(encoding="utf-8")
    output_path.write_text(build_brief(run_date, args.profile, db_path, digest_md), encoding="utf-8")
    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
