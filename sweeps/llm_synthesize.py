#!/usr/bin/env python3
"""
LLM synthesis for Nodehome operator briefs.

Reads the most recent operator brief from `docs/sweeps/operator/`, sends its
content to the local Ollama API for a "top 3 items that matter" synthesis,
and appends a `## Local LLM Synthesis` section to the brief in place.

Project alignment: closes the loop on the stated automated-research goal —
sweeps synthesis runs through the owned inference layer (local Ollama), not
an external paid API. By default uses `mistral-small3.1:24b` (the daily-driver
interactive model on this hardware, benchmarked at ~51 tok/s).

Idempotent: if a `## Local LLM Synthesis` section already exists in the brief,
it is replaced rather than appended again.

Usage:
    python sweeps/llm_synthesize.py
    python sweeps/llm_synthesize.py 2026-05-09
    python sweeps/llm_synthesize.py --profile extended
    python sweeps/llm_synthesize.py --model qwen2.5:32b-instruct-q4_K_M
    python sweeps/llm_synthesize.py --endpoint http://localhost:8000/v1/chat/completions
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
OPERATOR_DIR = REPO_ROOT / "docs" / "sweeps" / "operator"
DEFAULT_MODEL = "mistral-small3.1:24b"
DEFAULT_ENDPOINT = "http://localhost:11434/v1/chat/completions"
SYNTHESIS_HEADER = "## Local LLM Synthesis"

SYSTEM_PROMPT = (
    "You are an analyst reviewing a daily operator brief from an AI-research sweeps "
    "pipeline. The brief contains classified items from RSS, X/Bluesky, GitHub, and "
    "other sources, scored and grouped by relevance to a small AI infrastructure "
    "project (local LLM serving on owned hardware, sweeps automation, agent layer). "
    "Your job is to identify the items in the brief that actually matter for the "
    "project's near-term decisions. Be specific, skeptical, and concise. Do not "
    "invent facts not present in the brief. If the brief is thin or mostly noise, "
    "say so plainly. Avoid stock newsletter filler such as 'busy day', 'no single "
    "breakthrough', 'pace of small fixes', or 'worth watching' unless the sentence "
    "also names the concrete source item and the specific operator implication."
)

USER_PROMPT_TEMPLATE = (
    "Operator brief for {brief_date}. Identify the top 3 items that matter, in "
    "priority order. Use the format:\n\n"
    "1. **<short title>** — what it is in one sentence. Why it matters or what "
    "action it suggests in one sentence.\n"
    "2. **<short title>** — same format.\n"
    "3. **<short title>** — same format.\n\n"
    "Then on a separate final line starting with `Skip:`, name one signal you "
    "would explicitly NOT prioritize and why. If the brief contains no top-3-worthy "
    "items, say so plainly and explain why instead of inventing items.\n\n"
    "Brief content follows:\n\n{brief_content}"
)


def suffix_for_profile(profile: str) -> str:
    return "" if profile == "core" else f".{profile}"


def latest_brief_path(profile: str = "core") -> Path:
    suffix = suffix_for_profile(profile)
    pattern = f"*{suffix}.md"
    candidates = sorted(OPERATOR_DIR.glob(pattern))
    if profile == "core":
        candidates = [p for p in candidates if p.stem.count(".") == 0]
    if not candidates:
        sys.exit(f"No {profile} briefs found in {OPERATOR_DIR}")
    return candidates[-1]


def brief_path_for_date(brief_date: str, profile: str = "core") -> Path:
    p = OPERATOR_DIR / f"{brief_date}{suffix_for_profile(profile)}.md"
    if not p.exists():
        sys.exit(f"No brief at {p}")
    return p


def call_chat_completions(
    endpoint: str, model: str, system: str, user: str, timeout: int = 600
) -> str:
    body = json.dumps(
        {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.2,
            "max_tokens": 1024,
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        endpoint,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.load(resp)
    except urllib.error.URLError as exc:
        sys.exit(f"LLM endpoint {endpoint} not reachable: {exc}")
    try:
        return payload["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError) as exc:
        sys.exit(f"Unexpected response shape from {endpoint}: {payload!r} ({exc})")


def replace_or_append_synthesis(
    brief_path: Path, model: str, endpoint: str, synthesis: str
) -> None:
    existing = brief_path.read_text(encoding="utf-8")
    if SYNTHESIS_HEADER in existing:
        existing = existing.split(SYNTHESIS_HEADER)[0].rstrip() + "\n"
    timestamp = datetime.now().isoformat(timespec="seconds")
    new_section = (
        f"\n{SYNTHESIS_HEADER}\n\n"
        f"_Generated by `{model}` via `{endpoint}` on {timestamp}._\n\n"
        f"{synthesis}\n"
    )
    brief_path.write_text(existing + new_section, encoding="utf-8")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Append a local LLM synthesis section to an operator brief."
    )
    p.add_argument(
        "brief_date",
        nargs="?",
        help="YYYY-MM-DD; defaults to the latest brief in docs/sweeps/operator/",
    )
    p.add_argument(
        "--profile",
        choices=("core", "extended", "all"),
        default="core",
        help="Operator brief profile to synthesize (default: core).",
    )
    p.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"Model tag (default: {DEFAULT_MODEL}). For vLLM, use the HF repo id.",
    )
    p.add_argument(
        "--endpoint",
        default=DEFAULT_ENDPOINT,
        help=(
            "OpenAI-compatible chat-completions endpoint URL "
            f"(default: {DEFAULT_ENDPOINT}). Use http://localhost:8000/v1/chat/completions "
            "for the vLLM container."
        ),
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()
    brief_path = (
        brief_path_for_date(args.brief_date, args.profile)
        if args.brief_date
        else latest_brief_path(args.profile)
    )
    brief_content = brief_path.read_text(encoding="utf-8")
    user = USER_PROMPT_TEMPLATE.format(
        brief_date=brief_path.stem,
        brief_content=brief_content,
    )
    print(
        f"[llm_synthesize] brief={brief_path.name} model={args.model} "
        f"endpoint={args.endpoint}"
    )
    synthesis = call_chat_completions(args.endpoint, args.model, SYSTEM_PROMPT, user)
    replace_or_append_synthesis(brief_path, args.model, args.endpoint, synthesis)
    print(f"[llm_synthesize] wrote {len(synthesis)} chars of synthesis to {brief_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
