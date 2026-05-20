#!/usr/bin/env python3
"""Homelab-only Nodechat hallucination-friction eval harness.

The harness can dry-run without a model endpoint. Live runs require the local
Nodechat serving lanes to be up and write JSONL records under runtime/.
"""

from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import importlib.util
import io
import json
import pathlib
import subprocess
import sys
import time
from collections import Counter
from typing import Any


ROOT = pathlib.Path(__file__).resolve().parents[1]
NODECHAT_PATH = ROOT / "scripts" / "nodechat.py"
CORPUS_PATH = ROOT / "tests" / "nodechat_eval_corpus.py"


def load_module(name: str, path: pathlib.Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


nodechat = load_module("nodechat_eval_nodechat", NODECHAT_PATH)
corpus = load_module("nodechat_eval_corpus", CORPUS_PATH)


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def default_output_path() -> pathlib.Path:
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d-%H%M%S")
    return ROOT / "runtime" / "nodechat" / "evals" / f"nodechat-eval-{stamp}.jsonl"


def default_score_template_path(eval_path: pathlib.Path) -> pathlib.Path:
    return eval_path.with_name(f"{eval_path.stem}.scores.jsonl")


def read_jsonl(path: pathlib.Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for lineno, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                row = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise SystemExit(f"{path}:{lineno}: invalid JSONL row: {exc}") from exc
            if not isinstance(row, dict):
                raise SystemExit(f"{path}:{lineno}: expected JSON object")
            rows.append(row)
    return rows


def score_key(row: dict[str, Any]) -> tuple[str, str]:
    return (str(row.get("case_id") or ""), str(row.get("context") or ""))


def score_template_row(row: dict[str, Any]) -> dict[str, Any]:
    status = str(row.get("status") or "")
    gated = status == "gated"
    return {
        "case_id": row.get("case_id"),
        "context": row.get("context"),
        "status": status,
        "high_severity_unsupported_claims": 0 if gated else None,
        "project_fact_unsupported_claims": 0 if gated else None,
        "project_fact_claims_total": 0 if gated else None,
        "unsupported_claims": [],
        "notes": "",
        "response_excerpt": str(row.get("response") or "")[:500],
    }


def write_score_template(eval_path: pathlib.Path, output_path: pathlib.Path) -> int:
    rows = read_jsonl(eval_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(score_template_row(row), ensure_ascii=False, sort_keys=True) + "\n")
    print(f"wrote {len(rows)} manual score template row(s): {output_path}")
    return 0


def load_score_overrides(path: pathlib.Path) -> dict[tuple[str, str], dict[str, Any]]:
    overrides: dict[tuple[str, str], dict[str, Any]] = {}
    for row in read_jsonl(path):
        key = score_key(row)
        if not all(key):
            raise SystemExit(f"{path}: score row missing case_id/context")
        if key in overrides:
            raise SystemExit(f"{path}: duplicate score row for {key[0]} [{key[1]}]")
        overrides[key] = {
            "high_severity_unsupported_claims": row.get("high_severity_unsupported_claims"),
            "project_fact_unsupported_claims": row.get("project_fact_unsupported_claims"),
            "project_fact_claims_total": row.get("project_fact_claims_total"),
            "unsupported_claims": row.get("unsupported_claims") or [],
            "notes": row.get("notes") or "",
        }
    return overrides


def apply_score_overrides(
    rows: list[dict[str, Any]],
    overrides: dict[tuple[str, str], dict[str, Any]],
) -> list[dict[str, Any]]:
    scored: list[dict[str, Any]] = []
    row_keys = {score_key(row) for row in rows}
    unknown = sorted(key for key in overrides if key not in row_keys)
    if unknown:
        names = ", ".join(f"{case_id} [{context}]" for case_id, context in unknown)
        raise SystemExit(f"score file contains unknown eval row(s): {names}")
    for row in rows:
        copied = dict(row)
        score = dict(copied.get("manual_score") or {})
        if score_key(row) in overrides:
            score.update(overrides[score_key(row)])
        copied["manual_score"] = score
        scored.append(copied)
    return scored


def int_or_none(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    return None


def manual_score_complete(row: dict[str, Any]) -> bool:
    score = row.get("manual_score") or {}
    required = (
        "high_severity_unsupported_claims",
        "project_fact_unsupported_claims",
        "project_fact_claims_total",
    )
    return all(int_or_none(score.get(field)) is not None for field in required)


def summarize_eval_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    status_counts = Counter(str(row.get("status") or "unknown") for row in rows)
    scorable = [row for row in rows if row.get("status") == "ok"]
    incomplete = [row for row in scorable if not manual_score_complete(row)]

    high_total = 0
    project_unsupported = 0
    project_claims = 0
    for row in scorable:
        if not manual_score_complete(row):
            continue
        score = row.get("manual_score") or {}
        high_total += int(score["high_severity_unsupported_claims"])
        project_unsupported += int(score["project_fact_unsupported_claims"])
        project_claims += int(score["project_fact_claims_total"])

    target_high = int(corpus.ACCEPTANCE_TARGETS["high_severity_unsupported_claims"])
    target_rate = float(corpus.ACCEPTANCE_TARGETS["project_fact_unsupported_claim_rate_lt"])
    rate = (project_unsupported / project_claims) if project_claims else 0.0
    if status_counts.get("dry-run"):
        result = "dry-run"
    elif incomplete:
        result = "incomplete"
    elif high_total > target_high:
        result = "fail"
    elif project_claims and rate >= target_rate:
        result = "fail"
    else:
        result = "pass"

    return {
        "rows": len(rows),
        "status_counts": dict(sorted(status_counts.items())),
        "scorable_ok_rows": len(scorable),
        "manual_scores_complete": len(scorable) - len(incomplete),
        "manual_scores_required": len(scorable),
        "needs_score": [score_key(row) for row in incomplete],
        "high_severity_unsupported_claims": high_total,
        "high_severity_target": target_high,
        "project_fact_unsupported_claims": project_unsupported,
        "project_fact_claims_total": project_claims,
        "project_fact_unsupported_claim_rate": rate,
        "project_fact_claim_rate_target_lt": target_rate,
        "result": result,
    }


def print_eval_summary(summary: dict[str, Any]) -> None:
    print(f"rows: {summary['rows']}")
    print(
        "status_counts: "
        + ", ".join(f"{status}={count}" for status, count in summary["status_counts"].items())
    )
    print(
        "manual_scores: "
        f"{summary['manual_scores_complete']}/{summary['manual_scores_required']} ok row(s)"
    )
    print(
        "high_severity_unsupported_claims: "
        f"{summary['high_severity_unsupported_claims']} "
        f"(target {summary['high_severity_target']})"
    )
    print(
        "project_fact_unsupported_claim_rate: "
        f"{summary['project_fact_unsupported_claim_rate']:.2%} "
        f"({summary['project_fact_unsupported_claims']}/"
        f"{summary['project_fact_claims_total']}; "
        f"target < {summary['project_fact_claim_rate_target_lt']:.2%})"
    )
    print(f"result: {summary['result']}")
    if summary["needs_score"]:
        print("needs_score:")
        for case_id, context in summary["needs_score"]:
            print(f"  {case_id} [{context}]")


def review_eval(eval_path: pathlib.Path, scores_path: pathlib.Path | None) -> int:
    rows = read_jsonl(eval_path)
    if scores_path:
        rows = apply_score_overrides(rows, load_score_overrides(scores_path))
    summary = summarize_eval_rows(rows)
    print_eval_summary(summary)
    return 0 if summary["result"] == "pass" else 1


def make_config(args: argparse.Namespace):
    return nodechat.Config(
        base_url=str(args.base_url).rstrip("/"),
        model=str(args.model),
        api_key=str(args.api_key or ""),
        stream=False,
        temperature=float(args.temperature),
        max_tokens=int(args.max_tokens),
        timeout=int(args.timeout),
        max_history_messages=int(args.max_history_messages),
        session_root=pathlib.Path(args.session_root),
        workspace=pathlib.Path(args.workspace).resolve(),
        history_url=str(args.history_url).rstrip("/"),
        history_token=str(args.history_token or ""),
        history_limit=int(args.history_limit),
        cmd_timeout=int(args.cmd_timeout),
        live_ssh=str(args.live_ssh or ""),
        live_root=str(args.live_root or "~/nodehome"),
    )


def context_label(spec: dict[str, Any]) -> str:
    kind = spec.get("type")
    if kind == "repo_file":
        return f"file:{spec.get('path')}"
    if kind == "repo_search":
        return f"search:{spec.get('query')}@{spec.get('root', '.')}"
    if kind == "git_commit":
        return f"git:{spec.get('commit')}"
    return str(kind or "unknown")


def add_repo_file_context(config, session: dict[str, Any], spec: dict[str, Any], source: str) -> None:
    rel = str(spec["path"])
    path = nodechat.resolve_workspace_path(config, session, rel)
    reason = nodechat.path_safety_reason(config, session, path)
    if reason:
        raise RuntimeError(f"repo_file context refused for {rel}: {reason}")
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"repo_file context missing: {rel}")
    text, truncated = nodechat.read_text_path(path)
    content = nodechat.format_file_read(path, text, truncated)
    nodechat.add_context(
        session,
        f"eval:{rel}",
        nodechat.context_block("file_read", str(path), content),
        source=source,
        provenance={"path": rel, "chars": len(text), "truncated": truncated, "eval_context": True},
    )


def add_repo_search_context(config, session: dict[str, Any], spec: dict[str, Any], source: str) -> None:
    query = str(spec["query"])
    root_raw = str(spec.get("root") or ".")
    root = nodechat.resolve_workspace_path(config, session, root_raw)
    reason = nodechat.path_safety_reason(config, session, root)
    if reason:
        raise RuntimeError(f"repo_search context refused for {root_raw}: {reason}")
    if root.is_file():
        root = root.parent
    rows = nodechat.search_text_files(config, session, root, query)
    lines = [
        f"query: {query}",
        f"root: {root}",
        f"max_results: {nodechat.MAX_SEARCH_RESULTS}",
        "",
        *(rows or ["No matches found."]),
    ]
    nodechat.add_context(
        session,
        f"eval-search:{query}",
        nodechat.context_block("file_search", query, "\n".join(lines)),
        source=source,
        provenance={"query": query, "root": root_raw, "matches": len(rows), "eval_context": True},
    )


def add_git_commit_context(config, session: dict[str, Any], spec: dict[str, Any], source: str) -> None:
    commit = str(spec["commit"])
    result = subprocess.run(
        ["git", "show", "--stat", "--patch", "--find-renames", "--find-copies", "--format=fuller", commit],
        cwd=str(nodechat.workspace_path(config, session)),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=20,
        check=False,
    )
    output = result.stdout.strip()
    if result.returncode != 0:
        raise RuntimeError(f"git show {commit} failed: {output}")
    content = "\n".join([f"command: git show --stat --patch --format=fuller {commit}", f"exit_code: {result.returncode}", "", output])
    nodechat.add_context(
        session,
        f"eval-git:{commit}",
        nodechat.context_block("git_commit", commit, content),
        source=source,
        provenance={"command": "git show", "commit": commit, "chars": len(output), "eval_context": True},
    )


def add_context_spec(config, session: dict[str, Any], spec: dict[str, Any], context_name: str) -> None:
    source = f"eval-{context_name}"
    kind = spec.get("type")
    if kind == "repo_file":
        add_repo_file_context(config, session, spec, source)
    elif kind == "repo_search":
        add_repo_search_context(config, session, spec, source)
    elif kind == "git_commit":
        add_git_commit_context(config, session, spec, source)
    else:
        raise ValueError(f"unsupported eval context type: {kind!r}")


def prepare_eval_session(config, args: argparse.Namespace) -> dict[str, Any]:
    session = nodechat.make_session(config)
    session["model_mode"] = str(args.model_mode)
    session["history_mode"] = "off"
    session["repo_mode"] = "off"
    session["web_mode"] = "off"
    session["live_mode"] = "off"
    if int(args.max_tokens) > 0:
        session["_max_tokens_cap"] = int(args.max_tokens)
    return session


def run_case(config, args: argparse.Namespace, case: dict[str, Any], context_name: str) -> dict[str, Any]:
    session = prepare_eval_session(config, args)
    context_specs = list(case["context_sets"][context_name])
    for spec in context_specs:
        add_context_spec(config, session, spec, context_name)

    started = time.perf_counter()
    stdout = ""
    response = ""
    status = "dry-run" if args.dry_run else "ok"
    if not args.dry_run:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            status = nodechat.send_user_prompt(config, session, str(case["prompt"]))
        stdout = buf.getvalue()
        for message in reversed(session.get("messages", [])):
            if message.get("role") == "assistant":
                response = str(message.get("content") or "")
                break

    return {
        "schema_version": 1,
        "created_at": utc_now(),
        "case_id": case["id"],
        "context": context_name,
        "prompt": case["prompt"],
        "context_specs": context_specs,
        "context_labels": [context_label(spec) for spec in context_specs],
        "expected": case["expected"],
        "claim_taxonomy": corpus.CLAIM_TAXONOMY,
        "acceptance_targets": corpus.ACCEPTANCE_TARGETS,
        "scoring_rubric": corpus.SCORING_RUBRIC,
        "status": status,
        "response": response,
        "stdout": stdout,
        "manual_score": {
            "high_severity_unsupported_claims": None,
            "project_fact_unsupported_claims": None,
            "project_fact_claims_total": None,
            "unsupported_claims": [],
            "notes": "",
        },
        "model": session.get("model") or config.model,
        "base_url": session.get("base_url") or config.base_url,
        "model_mode": session.get("model_mode"),
        "latency_ms": int((time.perf_counter() - started) * 1000),
    }


def selected_cases(case_id: str) -> list[dict[str, Any]]:
    rows = list(corpus.CORPUS)
    if case_id == "all":
        return rows
    selected = [case for case in rows if case["id"] == case_id]
    if not selected:
        raise SystemExit(f"unknown eval case: {case_id}")
    return selected


def selected_contexts(raw: str) -> list[str]:
    if raw == "all":
        return ["zero", "correct", "irrelevant"]
    if raw not in {"zero", "correct", "irrelevant"}:
        raise SystemExit(f"unknown eval context: {raw}")
    return [raw]


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Nodechat hallucination-friction eval corpus.")
    parser.add_argument("--case", default="all", help="case id or 'all'")
    parser.add_argument("--context", default="all", help="zero, correct, irrelevant, or all")
    parser.add_argument("--dry-run", action="store_true", help="write eval rows without calling a model")
    parser.add_argument("--list", action="store_true", help="list eval cases and exit")
    parser.add_argument("--review", help="summarize a completed eval JSONL and exit")
    parser.add_argument("--scores", help="manual score overlay JSONL for --review")
    parser.add_argument("--write-score-template", help="write a manual score overlay template for an eval JSONL and exit")
    parser.add_argument("--score-output", help="output path for --write-score-template")
    parser.add_argument("--output", default=str(default_output_path()))
    parser.add_argument("--workspace", default=str(ROOT))
    parser.add_argument("--session-root", default=str(nodechat.DEFAULT_SESSION_ROOT / "eval"))
    parser.add_argument("--base-url", default=nodechat.DEFAULT_BASE_URL)
    parser.add_argument("--model", default=nodechat.DEFAULT_MODEL)
    parser.add_argument("--api-key", default="")
    parser.add_argument("--temperature", type=float, default=0.1)
    parser.add_argument("--max-tokens", type=int, default=1024)
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--max-history-messages", type=int, default=0)
    parser.add_argument("--history-url", default=nodechat.DEFAULT_HISTORY_URL)
    parser.add_argument("--history-token", default="")
    parser.add_argument("--history-limit", type=int, default=3)
    parser.add_argument("--cmd-timeout", type=int, default=20)
    parser.add_argument("--live-ssh", default="")
    parser.add_argument("--live-root", default="~/nodehome")
    parser.add_argument("--model-mode", default="manual")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    if args.list:
        for case in corpus.CORPUS:
            print(f"{case['id']}: {case['prompt']}")
        return 0
    if args.write_score_template:
        eval_path = pathlib.Path(args.write_score_template)
        output_path = pathlib.Path(args.score_output) if args.score_output else default_score_template_path(eval_path)
        return write_score_template(eval_path, output_path)
    if args.review:
        scores_path = pathlib.Path(args.scores) if args.scores else None
        return review_eval(pathlib.Path(args.review), scores_path)

    config = make_config(args)
    output_path = pathlib.Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cases = selected_cases(str(args.case))
    contexts = selected_contexts(str(args.context))

    count = 0
    with output_path.open("a", encoding="utf-8", newline="\n") as handle:
        for case in cases:
            for context_name in contexts:
                row = run_case(config, args, case, context_name)
                handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
                count += 1
                print(f"{row['case_id']} [{context_name}] -> {row['status']}")
    print(f"wrote {count} eval row(s): {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
