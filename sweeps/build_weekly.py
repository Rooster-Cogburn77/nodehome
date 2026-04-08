#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from collections import Counter
from datetime import UTC, date, datetime, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DAILY_DIR = ROOT / "docs" / "sweeps" / "daily"
WEEKLY_DIR = ROOT / "docs" / "sweeps" / "weekly"


def iso_week_label(run_date: date) -> str:
    year, week, _ = run_date.isocalendar()
    return f"{year}-W{week:02d}"


def week_dates(run_date: date) -> list[date]:
    weekday = run_date.isoweekday()
    monday = run_date - timedelta(days=weekday - 1)
    return [monday + timedelta(days=offset) for offset in range(7)]


def daily_path(day: date, profile: str) -> Path:
    suffix = "" if profile == "core" else f".{profile}"
    return DAILY_DIR / f"{day.isoformat()}{suffix}.md"


def extract_top_signals(text: str) -> list[str]:
    if "## Top Signals" not in text:
        return []
    section = text.split("## Top Signals", 1)[1]
    if "\n## " in section:
        section = section.split("\n## ", 1)[0]
    return [line[2:].strip() for line in section.splitlines() if line.startswith("- ")]


def extract_fetch_issues(text: str) -> list[str]:
    if "## Fetch Issues" not in text:
        return []
    section = text.split("## Fetch Issues", 1)[1]
    if "\n## " in section:
        section = section.split("\n## ", 1)[0]
    return [line[2:].strip() for line in section.splitlines() if line.startswith("- ")]


def detect_themes(signals: list[str]) -> list[str]:
    counters = Counter()
    keywords = {
        "workflow": ["workflow", "agent", "karpathy", "reasoning"],
        "infra": ["vllm", "ollama", "llama.cpp", "release", "batching", "inference"],
        "hardware": ["gpu", "power", "thermal", "3090", "quant"],
        "scene": ["hugging face", "qwen", "gemma", "local", "open source"],
    }
    for signal in signals:
        lowered = signal.lower()
        for theme, words in keywords.items():
            if any(word in lowered for word in words):
                counters[theme] += 1
    ranked = [theme for theme, _count in counters.most_common(4)]
    return ranked


def build_weekly(run_date: date, profile: str) -> Path:
    WEEKLY_DIR.mkdir(parents=True, exist_ok=True)
    week_label = iso_week_label(run_date)
    output_suffix = "" if profile == "core" else f".{profile}"
    output_path = WEEKLY_DIR / f"{week_label}{output_suffix}.md"

    signals: list[str] = []
    issues: list[str] = []
    input_paths: list[Path] = []
    for day in week_dates(run_date):
        path = daily_path(day, profile)
        if not path.exists():
            continue
        input_paths.append(path)
        text = path.read_text(encoding="utf-8")
        signals.extend(extract_top_signals(text))
        issues.extend(extract_fetch_issues(text))

    themes = detect_themes(signals)
    lines = [
        f"# Weekly Sweep Rollup - {week_label} ({profile})",
        "",
        f"Generated at {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        "## Inputs",
        "",
    ]
    if input_paths:
        for path in input_paths:
            lines.append(f"- {path.name}")
    else:
        lines.append("- No daily digests found for this week yet.")
    lines.extend(["", "## Themes", ""])
    if themes:
        for theme in themes:
            lines.append(f"- {theme}")
    else:
        lines.append("- No strong recurring themes detected yet.")
    lines.extend(["", "## Top Signals", ""])
    if signals:
        for signal in signals[:10]:
            lines.append(f"- {signal}")
    else:
        lines.append("- No top signals captured yet.")
    lines.extend(["", "## Operational Notes", ""])
    if issues:
        for issue in issues[:10]:
            lines.append(f"- {issue}")
    else:
        lines.append("- No significant fetch issues recorded.")
    lines.extend(["", "## Candidates For Promotion", "", "- ", "", "## Decisions To Revisit", "", "- ", ""])
    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a weekly sweep rollup from daily digests.")
    parser.add_argument("--date", dest="run_date", help="Anchor date in YYYY-MM-DD format.")
    parser.add_argument("--profile", choices=("core", "extended", "all"), default="core")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    run_date = date.fromisoformat(args.run_date) if args.run_date else date.today()
    output_path = build_weekly(run_date, args.profile)
    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
