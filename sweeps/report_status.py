#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sqlite3
import subprocess
from datetime import UTC, datetime
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
SWEEPS_DIR = ROOT / "docs" / "sweeps"
DEGRADED_SOURCES = SWEEPS_DIR / "health" / "degraded_sources.json"
TASK_NAMES = (
    "SovereignNodeSweepCore",
    "SovereignNodeSweepExtended",
    "SovereignNodeSweepWeekly",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Print one-page Nodehome sweep system status.")
    parser.add_argument("--profile", choices=("core", "extended", "all"), default="all")
    parser.add_argument("--db", default=str(DEFAULT_DB), help="SQLite notebook path.")
    parser.add_argument("--limit", type=int, default=5, help="Rows to show for pressure/follow-up sections.")
    return parser.parse_args()


def resolve_db(path: str) -> Path:
    db_path = Path(path)
    if not db_path.is_absolute():
        db_path = ROOT / db_path
    return db_path


def latest_file(directory: Path, pattern: str) -> Path | None:
    paths = [path for path in directory.glob(pattern) if path.is_file()]
    if not paths:
        return None
    return max(paths, key=lambda path: path.stat().st_mtime)


def file_line(label: str, path: Path | None) -> str:
    if path is None:
        return f"- {label}: missing"
    mtime = datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
    return f"- {label}: {path.relative_to(ROOT)} ({mtime}, {path.stat().st_size} bytes)"


def notebook_counts(conn: sqlite3.Connection) -> dict[str, int]:
    total = conn.execute("SELECT COUNT(*) FROM facts").fetchone()[0]
    high = conn.execute("SELECT COUNT(*) FROM facts WHERE stack_relevance = 'high'").fetchone()[0]
    actions = conn.execute("SELECT COUNT(*) FROM fact_actions").fetchone()[0]
    open_actions = conn.execute(
        "SELECT COUNT(*) FROM fact_actions WHERE status IN ('open', 'reviewing')"
    ).fetchone()[0]
    return {"facts": total, "stack_high": high, "actions": actions, "open_actions": open_actions}


def degraded_summary(limit: int) -> tuple[int, list[str]]:
    if not DEGRADED_SOURCES.exists():
        return 0, ["- degraded source state missing"]
    data = json.loads(DEGRADED_SOURCES.read_text(encoding="utf-8"))
    rows = []
    for source_id, record in data.items():
        status = record.get("status", "")
        failures = int(record.get("failures", 0) or 0)
        if status != "ok" or failures:
            rows.append((failures, source_id, status, record.get("last_detail", "")))
    rows.sort(reverse=True)
    lines = [f"- {source_id}: {status}, failures={failures}, {detail}" for failures, source_id, status, detail in rows[:limit]]
    return len(rows), lines


def parse_task_output(output: str) -> dict[str, str]:
    fields = {}
    for line in output.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        fields[key.strip()] = value.strip()
    return fields


def task_status(name: str) -> str:
    try:
        result = subprocess.run(
            ["schtasks", "/Query", "/TN", name, "/V", "/FO", "LIST"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        return f"- {name}: unavailable ({exc})"
    fields = parse_task_output(result.stdout)
    status = fields.get("Status", "unknown")
    next_run = fields.get("Next Run Time", "unknown")
    last_run = fields.get("Last Run Time", "unknown")
    last_result = fields.get("Last Result", "unknown")
    return f"- {name}: {status}; next={next_run}; last={last_run}; result={last_result}"


def short_claim(text: str, max_len: int = 140) -> str:
    text = " ".join(text.split())
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + "..."


def print_rows(title: str, rows: list[sqlite3.Row], limit: int) -> None:
    print(f"\n## {title}")
    if not rows:
        print("- none")
        return
    for row in rows[:limit]:
        if "fact_claim" in row.keys():
            print(
                f"- [{row['severity']} | {row['assumption_entity']}] "
                f"{short_claim(row['fact_claim'])} ({row['fact_id'][:12]})"
            )
        else:
            print(
                f"- [{row['entity'] or 'unknown'} | {followup_reason(row)}] "
                f"{short_claim(row['claim_text'])} ({row['id'][:12]})"
            )


def main() -> int:
    args = parse_args()
    db_path = resolve_db(args.db)

    print("# Nodehome Sweep Status")
    print(f"Generated at {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')}")

    print("\n## Artifacts")
    print(file_line("latest daily core", latest_file(SWEEPS_DIR / "daily", "????-??-??.md")))
    print(file_line("latest daily extended", latest_file(SWEEPS_DIR / "daily", "*.extended.md")))
    print(file_line("latest daily all", latest_file(SWEEPS_DIR / "daily", "*.all.md")))
    print(file_line("latest weekly", latest_file(SWEEPS_DIR / "weekly", "*.md")))

    print("\n## Scheduled Tasks")
    for task_name in TASK_NAMES:
        print(task_status(task_name))

    if not db_path.exists():
        print(f"\n## Notebook\n- missing DB: {db_path}")
        return 0

    conn = connect(db_path)
    init_db(conn)
    counts = notebook_counts(conn)
    followups = followup_rows(conn, args.profile, args.limit)
    pressure = assumption_pressure_rows(conn, args.profile, args.limit)
    conn.close()

    print("\n## Notebook")
    print(f"- facts: {counts['facts']}")
    print(f"- stack-high facts: {counts['stack_high']}")
    print(f"- action rows: {counts['actions']}")
    print(f"- open/reviewing action rows: {counts['open_actions']}")
    print(f"- open follow-up candidates shown: {len(followups)}")
    print(f"- assumption pressure rows shown: {len(pressure)}")

    degraded_count, degraded_lines = degraded_summary(args.limit)
    print("\n## Source Health")
    print(f"- degraded/non-ok sources: {degraded_count}")
    for line in degraded_lines:
        print(line)

    print_rows("Assumption Pressure", pressure, args.limit)
    print_rows("Follow-Up Queue", followups, args.limit)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
