"""Routing corpus + harness for Nodechat auto-routers (Phase A).

Drives ``detect_history_query`` / ``detect_repo_targets`` /
``detect_web_targets`` / ``detect_live_targets`` against a labeled corpus
of realistic prompts and emits per-router precision/recall plus the
list of false positives (FP) and false negatives (FN). No behavior
change to ``scripts/nodechat.py``; this module is measurement
infrastructure for the Nodechat auto-routing recall pass.

Usage as a CLI (prints baseline matrix):

    py -3 tests/routing_corpus.py

Usage as a library (from tests/test_nodechat_safety.py):

    import importlib.util, pathlib, sys
    spec = importlib.util.spec_from_file_location(
        "routing_corpus", pathlib.Path(__file__).parent / "routing_corpus.py")
    m = importlib.util.module_from_spec(spec); sys.modules["routing_corpus"] = m
    spec.loader.exec_module(m)
    config, session = m.make_corpus_config_and_session()
    matrix = m.evaluate(config, session)

Labels reflect the *intended* routing decision per router, not the
current heuristic behavior. Divergence between intent and reality is
exactly what Phase B widens.
"""
from __future__ import annotations

import importlib.util
import pathlib
import sys
from collections import Counter
from typing import Any


ROOT = pathlib.Path(__file__).resolve().parents[1]
NODECHAT_PATH = ROOT / "scripts" / "nodechat.py"


def _load_nodechat():
    if "nodechat" in sys.modules:
        return sys.modules["nodechat"]
    spec = importlib.util.spec_from_file_location("nodechat", NODECHAT_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["nodechat"] = module
    spec.loader.exec_module(module)
    return module


nodechat = _load_nodechat()


# ---------------------------------------------------------------------------
# Labeled corpus.
#
# Each case carries:
#   id        -- short stable id; used in failure messages
#   category  -- positive bucket per router, neutral, or guardrail (zero-tol)
#   prompt    -- realistic Nodehome-context prompt
#   expected  -- per-router intent:
#                  history: bool
#                  repo:    list of expected workspace-relative posix paths
#                  web:     "none" | "fetch" | "search"
#                  live:    list of expected check names
# ---------------------------------------------------------------------------

CASES: list[dict[str, Any]] = [
    # --- history positives -------------------------------------------------
    {"id": "h001", "category": "history-positive",
     "prompt": "what did we decide about gpu2 cabling?",
     "expected": {"history": True, "repo": [], "web": "none", "live": []}},
    {"id": "h002", "category": "history-positive",
     "prompt": "remind me what the current sweep schedule looks like",
     "expected": {"history": True, "repo": [], "web": "none", "live": []}},
    {"id": "h003", "category": "history-positive",
     "prompt": "previously we capped gpu0 at 300W and validated thermals",
     "expected": {"history": True, "repo": [], "web": "none", "live": []}},
    {"id": "h004", "category": "history-positive",
     "prompt": "history of the rdimm dispute with SCW Computers",
     "expected": {"history": True, "repo": [], "web": "none", "live": []}},
    {"id": "h005", "category": "history-positive",
     "prompt": "did we ever order the SF-1600F14HT cable?",
     "expected": {"history": True, "repo": [], "web": "none", "live": []}},
    {"id": "h006", "category": "history-positive",
     "prompt": "did we already validate the 70b q4 layer-split run?",
     "expected": {"history": True, "repo": [], "web": "none", "live": []}},
    {"id": "h007", "category": "history-positive",
     "prompt": "when did we install the bmc fan threshold fix?",
     "expected": {"history": True, "repo": [], "web": "none", "live": []}},
    {"id": "h008", "category": "history-positive",
     "prompt": "how did we resolve the SCW Computers rdimm escalation?",
     "expected": {"history": True, "repo": [], "web": "none", "live": []}},
    {"id": "h009", "category": "history-positive",
     "prompt": "why did we pick mistral as the daily driver over qwen?",
     "expected": {"history": True, "repo": [], "web": "none", "live": []}},
    {"id": "h010", "category": "history-positive",
     "prompt": "where did we land on Ubiquiti vs the cable router?",
     "expected": {"history": True, "repo": [], "web": "none", "live": []}},
    {"id": "h011", "category": "history-positive",
     "prompt": "who decided to skip Proxmox for day one?",
     "expected": {"history": True, "repo": [], "web": "none", "live": []}},
    {"id": "h012", "category": "history-positive",
     "prompt": "earlier session we benchmarked Ollama at 51 tok/s",
     "expected": {"history": True, "repo": [], "web": "none", "live": []}},
    {"id": "h013", "category": "history-positive",
     "prompt": "last week we ordered the GPU3 cable from lizzieb753",
     "expected": {"history": True, "repo": [], "web": "none", "live": []}},

    # --- history aspirational (currently miss; Phase B widening targets) --
    {"id": "h101", "category": "history-positive",
     "prompt": "have we ever tested a 70B AWQ run on TP=3?",
     "expected": {"history": True, "repo": [], "web": "none", "live": []}},
    {"id": "h102", "category": "history-positive",
     "prompt": "has the rack PDU ever tripped under load?",
     "expected": {"history": True, "repo": [], "web": "none", "live": []}},
    {"id": "h103", "category": "history-positive",
     "prompt": "what was our reasoning for the 300W cap again?",
     "expected": {"history": True, "repo": [], "web": "none", "live": []}},

    # --- repo positives ---------------------------------------------------
    {"id": "r001", "category": "repo-positive",
     "prompt": "look at CURRENT_STATE for the gpu3 cable status",
     "expected": {"history": False, "repo": ["docs/CURRENT_STATE.md"], "web": "none", "live": []}},
    {"id": "r002", "category": "repo-positive",
     "prompt": "what's in CLAUDE.md right now?",
     "expected": {"history": False, "repo": ["CLAUDE.md"], "web": "none", "live": []}},
    {"id": "r003", "category": "repo-positive",
     "prompt": "open SESSION_LOG and show the latest session focus",
     "expected": {"history": False, "repo": ["docs/SESSION_LOG.md"], "web": "none", "live": []}},
    {"id": "r004", "category": "repo-positive",
     "prompt": "is SCRATCH.md still tracking the storage procurement?",
     "expected": {"history": False, "repo": ["SCRATCH.md"], "web": "none", "live": []}},
    {"id": "r005", "category": "repo-positive",
     "prompt": "is ATTITUDE.md still accurate for tone?",
     "expected": {"history": False, "repo": ["ATTITUDE.md"], "web": "none", "live": []}},
    {"id": "r006", "category": "repo-positive",
     "prompt": "walk me through nodechat-scope",
     "expected": {"history": False, "repo": ["docs/runbooks/nodechat-scope.md"], "web": "none", "live": []}},
    {"id": "r007", "category": "repo-positive",
     "prompt": "explain ipmi-recovery procedure",
     "expected": {"history": False, "repo": ["docs/runbooks/ipmi-recovery.md"], "web": "none", "live": []}},
    {"id": "r008", "category": "repo-positive",
     "prompt": "how is upgrade-cadence structured?",
     "expected": {"history": False, "repo": ["docs/runbooks/upgrade-cadence.md"], "web": "none", "live": []}},
    {"id": "r009", "category": "repo-positive",
     "prompt": "review home-media-server architecture",
     "expected": {"history": False, "repo": ["docs/runbooks/home-media-server.md"], "web": "none", "live": []}},
    {"id": "r010", "category": "repo-positive",
     "prompt": "open scripts/nodechat.py at the auto_route_turn function",
     "expected": {"history": False, "repo": ["scripts/nodechat.py"], "web": "none", "live": []}},
    {"id": "r011", "category": "repo-positive",
     "prompt": "look at scripts/healthcheck.sh",
     "expected": {"history": False, "repo": ["scripts/healthcheck.sh"], "web": "none", "live": []}},
    {"id": "r012", "category": "repo-positive",
     "prompt": "describe sweeps/run_daily.py briefly",
     "expected": {"history": False, "repo": ["sweeps/run_daily.py"], "web": "none", "live": []}},
    {"id": "r013", "category": "repo-positive",
     "prompt": "summarize tests/test_nodechat_safety.py",
     "expected": {"history": False, "repo": ["tests/test_nodechat_safety.py"], "web": "none", "live": []}},
    {"id": "r014", "category": "repo-positive",
     "prompt": "compare CURRENT_STATE and SESSION_LOG side by side",
     "expected": {"history": False,
                  "repo": ["docs/CURRENT_STATE.md", "docs/SESSION_LOG.md"],
                  "web": "none", "live": []}},
    {"id": "r015", "category": "repo-positive",
     "prompt": "look at CLAUDE.md and SCRATCH.md for the Nodechat section",
     "expected": {"history": False,
                  "repo": ["CLAUDE.md", "SCRATCH.md"],
                  "web": "none", "live": []}},

    # --- web positives (URL fetch) ---------------------------------------
    {"id": "w001", "category": "web-positive-url",
     "prompt": "summarize https://example.com",
     "expected": {"history": False, "repo": [], "web": "fetch", "live": []}},
    {"id": "w002", "category": "web-positive-url",
     "prompt": "fetch https://github.com/vllm-project/vllm/releases please",
     "expected": {"history": False, "repo": [], "web": "fetch", "live": []}},
    {"id": "w003", "category": "web-positive-url",
     "prompt": "what does this page say https://docs.python.org/3/library/asyncio.html",
     "expected": {"history": False, "repo": [], "web": "fetch", "live": []}},
    {"id": "w004", "category": "web-positive-url",
     "prompt": "check the listing at https://www.ebay.com/itm/123456789012",
     "expected": {"history": False, "repo": [], "web": "fetch", "live": []}},
    {"id": "w005", "category": "web-positive-url",
     "prompt": "the readme at https://huggingface.co/Qwen/Qwen2.5-32B-Instruct-AWQ",
     "expected": {"history": False, "repo": [], "web": "fetch", "live": []}},

    # --- web positives (search) -------------------------------------------
    {"id": "w101", "category": "web-positive-search",
     "prompt": "what's the latest vllm release",
     "expected": {"history": False, "repo": [], "web": "search", "live": []}},
    {"id": "w102", "category": "web-positive-search",
     "prompt": "current ollama version on github",
     "expected": {"history": False, "repo": [], "web": "search", "live": []}},
    {"id": "w103", "category": "web-positive-search",
     "prompt": "any new cve for nvidia driver",
     "expected": {"history": False, "repo": [], "web": "search", "live": []}},
    {"id": "w104", "category": "web-positive-search",
     "prompt": "current pricing for used 4090s on ebay",
     "expected": {"history": False, "repo": [], "web": "search", "live": []}},
    {"id": "w105", "category": "web-positive-search",
     "prompt": "is open webui v0.9.5 released yet",
     "expected": {"history": False, "repo": [], "web": "search", "live": []}},
    {"id": "w106", "category": "web-positive-search",
     "prompt": "release notes for cuda 13.2",
     "expected": {"history": False, "repo": [], "web": "search", "live": []}},
    {"id": "w107", "category": "web-positive-search",
     "prompt": "look up qwen2.5 awq vllm benchmarks online",
     "expected": {"history": False, "repo": [], "web": "search", "live": []}},
    {"id": "w108", "category": "web-positive-search",
     "prompt": "search for SF-1600F14HT cable availability",
     "expected": {"history": False, "repo": [], "web": "search", "live": []}},
    {"id": "w109", "category": "web-positive-search",
     "prompt": "current pricing for SMT2200 used on ebay",
     "expected": {"history": False, "repo": [], "web": "search", "live": []}},
    {"id": "w110", "category": "web-positive-search",
     "prompt": "verify online that ollama 0.30 is stable",
     "expected": {"history": False, "repo": [], "web": "search", "live": []}},

    # --- live positives ---------------------------------------------------
    {"id": "l001", "category": "live-positive",
     "prompt": "current gpu temperature on the node",
     "expected": {"history": False, "repo": [], "web": "none", "live": ["gpu"]}},
    {"id": "l002", "category": "live-positive",
     "prompt": "is vllm up on the node?",
     "expected": {"history": False, "repo": [], "web": "none", "live": ["vllm"]}},
    {"id": "l003", "category": "live-positive",
     "prompt": "is ollama running?",
     "expected": {"history": False, "repo": [], "web": "none", "live": ["ollama"]}},
    {"id": "l004", "category": "live-positive",
     "prompt": "check stack health",
     "expected": {"history": False, "repo": [], "web": "none", "live": ["health"]}},
    {"id": "l005", "category": "live-positive",
     "prompt": "show me current docker container status",
     "expected": {"history": False, "repo": [], "web": "none", "live": ["docker"]}},
    {"id": "l006", "category": "live-positive",
     "prompt": "what's the current power cap on gpu0?",
     "expected": {"history": False, "repo": [], "web": "none", "live": ["power"]}},
    {"id": "l007", "category": "live-positive",
     "prompt": "current free disk space on the node",
     "expected": {"history": False, "repo": [], "web": "none", "live": ["storage"]}},
    {"id": "l008", "category": "live-positive",
     "prompt": "is the bmc currently reachable",
     "expected": {"history": False, "repo": [], "web": "none", "live": ["bmc"]}},
    {"id": "l009", "category": "live-positive",
     "prompt": "current ups battery status",
     "expected": {"history": False, "repo": [], "web": "none", "live": ["ups"]}},
    {"id": "l010", "category": "live-positive",
     "prompt": "diagnose the homelab stack",
     "expected": {"history": False, "repo": [], "web": "none", "live": ["health"]}},
    {"id": "l011", "category": "live-positive",
     "prompt": "verify nodehome is currently healthy",
     "expected": {"history": False, "repo": [], "web": "none", "live": ["health"]}},
    {"id": "l012", "category": "live-positive",
     "prompt": "is open webui currently running in a container",
     "expected": {"history": False, "repo": [], "web": "none", "live": ["docker"]}},
    {"id": "l013", "category": "live-positive",
     "prompt": "current nvidia gpu power draw across all three cards",
     "expected": {"history": False, "repo": [], "web": "none", "live": ["gpu"]}},
    {"id": "l014", "category": "live-positive",
     "prompt": "check ipmi reachability",
     "expected": {"history": False, "repo": [], "web": "none", "live": ["bmc"]}},

    # --- neutral / general (must not route any router) -------------------
    {"id": "n001", "category": "neutral", "prompt": "hello there",
     "expected": {"history": False, "repo": [], "web": "none", "live": []}},
    {"id": "n002", "category": "neutral", "prompt": "thanks",
     "expected": {"history": False, "repo": [], "web": "none", "live": []}},
    {"id": "n003", "category": "neutral", "prompt": "ok got it",
     "expected": {"history": False, "repo": [], "web": "none", "live": []}},
    {"id": "n004", "category": "neutral", "prompt": "explain transformers in two lines",
     "expected": {"history": False, "repo": [], "web": "none", "live": []}},
    {"id": "n005", "category": "neutral", "prompt": "what is a Kalman filter",
     "expected": {"history": False, "repo": [], "web": "none", "live": []}},
    {"id": "n006", "category": "neutral", "prompt": "write a python function that reverses a string",
     "expected": {"history": False, "repo": [], "web": "none", "live": []}},
    {"id": "n007", "category": "neutral", "prompt": "what's the difference between a list and a tuple",
     "expected": {"history": False, "repo": [], "web": "none", "live": []}},
    {"id": "n008", "category": "neutral", "prompt": "how does TCP slow start work",
     "expected": {"history": False, "repo": [], "web": "none", "live": []}},
    {"id": "n009", "category": "neutral", "prompt": "what is BGP",
     "expected": {"history": False, "repo": [], "web": "none", "live": []}},
    {"id": "n010", "category": "neutral", "prompt": "tell me a joke",
     "expected": {"history": False, "repo": [], "web": "none", "live": []}},
    {"id": "n011", "category": "neutral", "prompt": "explain monads",
     "expected": {"history": False, "repo": [], "web": "none", "live": []}},
    {"id": "n012", "category": "neutral", "prompt": "what year did the Roman Empire fall",
     "expected": {"history": False, "repo": [], "web": "none", "live": []}},
    {"id": "n013", "category": "neutral", "prompt": "convert 100 fahrenheit to celsius",
     "expected": {"history": False, "repo": [], "web": "none", "live": []}},
    {"id": "n014", "category": "neutral", "prompt": "what's the capital of australia",
     "expected": {"history": False, "repo": [], "web": "none", "live": []}},
    {"id": "n015", "category": "neutral", "prompt": "explain the doppler effect",
     "expected": {"history": False, "repo": [], "web": "none", "live": []}},
    {"id": "n016", "category": "neutral", "prompt": "best practices for python project layout",
     "expected": {"history": False, "repo": [], "web": "none", "live": []}},
    {"id": "n017", "category": "neutral", "prompt": "how do I write a regex for an email address",
     "expected": {"history": False, "repo": [], "web": "none", "live": []}},
    {"id": "n018", "category": "neutral", "prompt": "explain async/await",
     "expected": {"history": False, "repo": [], "web": "none", "live": []}},
    {"id": "n019", "category": "neutral", "prompt": "what's the time complexity of mergesort",
     "expected": {"history": False, "repo": [], "web": "none", "live": []}},
    {"id": "n020", "category": "neutral", "prompt": "describe the OSI model briefly",
     "expected": {"history": False, "repo": [], "web": "none", "live": []}},
    {"id": "n021", "category": "neutral", "prompt": "what is a B-tree",
     "expected": {"history": False, "repo": [], "web": "none", "live": []}},
    {"id": "n022", "category": "neutral", "prompt": "how does HTTPS work at a high level",
     "expected": {"history": False, "repo": [], "web": "none", "live": []}},
    {"id": "n023", "category": "neutral", "prompt": "explain CRDT in one paragraph",
     "expected": {"history": False, "repo": [], "web": "none", "live": []}},
    {"id": "n024", "category": "neutral", "prompt": "what is the difference between TCP and UDP",
     "expected": {"history": False, "repo": [], "web": "none", "live": []}},
    {"id": "n025", "category": "neutral", "prompt": "summarize the bible in one sentence",
     "expected": {"history": False, "repo": [], "web": "none", "live": []}},

    # --- guardrails (zero-tolerance must-not-deviate) --------------------
    # These specifically protect the wires we already know are noisy.
    {"id": "g001", "category": "guardrail",
     "prompt": "what is the current state of the build?",
     "expected": {"history": False, "repo": [], "web": "none", "live": []},
     "notes": "vague topic phrase; must not auto-read CURRENT_STATE.md"},
    {"id": "g002", "category": "guardrail",
     "prompt": "tell me about the project",
     "expected": {"history": False, "repo": [], "web": "none", "live": []},
     "notes": "vague topic phrase"},
    {"id": "g003", "category": "guardrail",
     "prompt": "this codebase looks interesting",
     "expected": {"history": False, "repo": [], "web": "none", "live": []},
     "notes": "vague topic phrase"},
    {"id": "g004", "category": "guardrail",
     "prompt": "how does build_operator_brief.py work?",
     "expected": {"history": False, "repo": [], "web": "none", "live": []},
     "notes": "bare filename; must not route -- /read covers this"},
    {"id": "g005", "category": "guardrail",
     "prompt": "what is the current implementation status of nodechat?",
     "expected": {"history": False, "repo": [], "web": "none", "live": []},
     "notes": "vague phrase; not a live-status query and not a history query"},
    {"id": "g006", "category": "guardrail",
     "prompt": "current vLLM status on our node",
     "expected": {"history": False, "repo": [], "web": "none", "live": ["vllm"]},
     "notes": "local-status: live should fire on vllm; web must not"},
    {"id": "g007", "category": "guardrail",
     "prompt": "what's running on the box right now",
     "expected": {"history": False, "repo": [], "web": "none", "live": ["docker"]},
     "notes": "local-status: live should fire on docker fallback; web must not"},
    {"id": "g008", "category": "guardrail",
     "prompt": "the latest model we trained",
     "expected": {"history": False, "repo": [], "web": "none", "live": []},
     "notes": "'latest' + 'model' could trip web; 'we' makes it local"},
    {"id": "g009", "category": "guardrail",
     "prompt": "history of the mongol empire",
     "expected": {"history": False, "repo": [], "web": "none", "live": []},
     "notes": "'history of' is a HISTORY pattern; this is general knowledge"},
    {"id": "g010", "category": "guardrail",
     "prompt": "remind me to call mom tomorrow",
     "expected": {"history": False, "repo": [], "web": "none", "live": []},
     "notes": "'remind me' is a HISTORY pattern; this is a personal reminder"},
    {"id": "g011", "category": "guardrail",
     "prompt": "previously the romans built aqueducts",
     "expected": {"history": False, "repo": [], "web": "none", "live": []},
     "notes": "'previously' is a HISTORY pattern; this is general knowledge"},
    {"id": "g012", "category": "guardrail",
     "prompt": "look at scripts/nonexistent_file.py",
     "expected": {"history": False, "repo": [], "web": "none", "live": []},
     "notes": "path-shaped token but file does not exist; must not route"},
    {"id": "g013", "category": "guardrail",
     "prompt": "what's the latest news about Antarctica",
     "expected": {"history": False, "repo": [], "web": "none", "live": []},
     "notes": "'latest' present but no public-object signal in our domain"},
    {"id": "g014", "category": "guardrail",
     "prompt": "explain the latest machine learning trends",
     "expected": {"history": False, "repo": [], "web": "none", "live": []},
     "notes": "'latest' + general knowledge ask; not a verifiable fresh-data lookup"},
    {"id": "g015", "category": "guardrail",
     "prompt": "is everything healthy in life",
     "expected": {"history": False, "repo": [], "web": "none", "live": []},
     "notes": "'healthy' present but no live-object signal"},
]


# Cases not explicitly listed above can be retrieved by category:
def cases_by_category(category: str) -> list[dict[str, Any]]:
    return [c for c in CASES if c["category"] == category]


# ---------------------------------------------------------------------------
# Harness.
# ---------------------------------------------------------------------------


def _classify_web(predicted: dict | None) -> str:
    if predicted is None:
        return "none"
    if predicted.get("urls"):
        return "fetch"
    if predicted.get("query"):
        return "search"
    return "none"


def _outcome(router: str, expected: Any, actual: Any) -> str:
    """Return 'TP' / 'FP' / 'FN' / 'TN' for a single prompt/router pair."""
    if router == "history":
        exp_pos = bool(expected)
        act_pos = bool(actual)
    elif router == "web":
        exp_pos = expected != "none"
        act_pos = actual != "none"
    else:  # repo, live -- multilabel, treated as exact set match
        exp_pos = bool(expected)
        act_pos = bool(actual)
    if exp_pos and act_pos:
        if router in ("repo", "live"):
            return "TP" if set(expected) == set(actual) else "FN"
        if router == "web":
            return "TP" if expected == actual else "FN"
        return "TP"
    if exp_pos and not act_pos:
        return "FN"
    if not exp_pos and act_pos:
        return "FP"
    return "TN"


def make_corpus_config_and_session():
    """Build a Config + session pointed at the real workspace.

    Repo routing relies on actual file existence in ``ROOT``, so the
    corpus binds to the repo it ships in. Session root is a scratch
    subdir that the harness does not need to write to during evaluation.
    """
    workspace = ROOT
    session_root = workspace / ".routing-corpus-tmp"
    config = nodechat.Config(
        base_url="http://127.0.0.1:8000/v1",
        model=nodechat.DEFAULT_MODEL,
        api_key="",
        stream=False,
        temperature=0.1,
        max_tokens=0,
        timeout=5,
        max_history_messages=8,
        session_root=session_root,
        workspace=workspace.resolve(),
        history_url="http://127.0.0.1:8765",
        history_token="",
        history_limit=3,
        cmd_timeout=5,
        live_ssh="",
        live_root="~/nodehome",
    )
    session = nodechat.make_session(config)
    return config, session


def evaluate(config, session) -> dict[str, Any]:
    """Run all four detectors over CASES; return a matrix dict."""
    routers = ("history", "repo", "web", "live")
    counts: dict[str, Counter] = {r: Counter() for r in routers}
    fps: dict[str, list[tuple[str, str, Any, Any]]] = {r: [] for r in routers}
    fns: dict[str, list[tuple[str, str, Any, Any]]] = {r: [] for r in routers}
    guardrail_failures: list[tuple[str, str, str, Any, Any]] = []

    for case in CASES:
        prompt = case["prompt"]
        expected = case["expected"]

        repo_paths = nodechat.detect_repo_targets(config, session, prompt)
        actual = {
            "history": nodechat.detect_history_query(prompt) is not None,
            "repo": [nodechat.display_path(config, session, p) for p in repo_paths],
            "web": _classify_web(nodechat.detect_web_targets(prompt)),
            "live": list(nodechat.detect_live_targets(prompt)),
        }

        for router in routers:
            outcome = _outcome(router, expected[router], actual[router])
            counts[router][outcome] += 1
            if outcome == "FP":
                fps[router].append((case["id"], prompt, actual[router], expected[router]))
            elif outcome == "FN":
                fns[router].append((case["id"], prompt, actual[router], expected[router]))

        if case.get("category") == "guardrail":
            for router in routers:
                exp = expected[router]
                act = actual[router]
                if router in ("repo", "live"):
                    if set(exp) != set(act):
                        guardrail_failures.append((case["id"], router, prompt, act, exp))
                elif router == "history":
                    if bool(exp) != bool(act):
                        guardrail_failures.append((case["id"], router, prompt, act, exp))
                else:  # web
                    if exp != act:
                        guardrail_failures.append((case["id"], router, prompt, act, exp))

    metrics: dict[str, dict[str, float]] = {}
    for router in routers:
        c = counts[router]
        tp, fp, fn, tn = c["TP"], c["FP"], c["FN"], c["TN"]
        precision = tp / (tp + fp) if (tp + fp) > 0 else 1.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 1.0
        metrics[router] = {
            "TP": tp, "FP": fp, "FN": fn, "TN": tn,
            "precision": precision, "recall": recall,
        }

    return {
        "metrics": metrics,
        "fps": fps,
        "fns": fns,
        "guardrail_failures": guardrail_failures,
        "total_cases": len(CASES),
    }


def summarize(matrix: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append(f"Routing corpus baseline ({matrix['total_cases']} prompts):")
    lines.append("")
    lines.append(f"{'Router':<10} {'Precision':>10} {'Recall':>8} {'TP':>5} {'FP':>5} {'FN':>5} {'TN':>5}")
    for router, m in matrix["metrics"].items():
        lines.append(
            f"{router:<10} {m['precision']:>10.3f} {m['recall']:>8.3f} "
            f"{m['TP']:>5} {m['FP']:>5} {m['FN']:>5} {m['TN']:>5}"
        )
    lines.append("")
    g_total = sum(1 for c in CASES if c.get("category") == "guardrail")
    g_fail = len(matrix["guardrail_failures"])
    lines.append(f"Guardrails ({g_total} prompts): {g_total - g_fail}/{g_total} {'PASS' if g_fail == 0 else 'FAIL'}")
    if g_fail:
        lines.append("Guardrail failures:")
        for cid, router, prompt, act, exp in matrix["guardrail_failures"]:
            lines.append(f"  {cid} [{router}] {prompt!r} -> got={act!r}, expected={exp!r}")
    lines.append("")
    for router in ("history", "repo", "web", "live"):
        if matrix["fps"][router]:
            lines.append(f"FPs ({router}, {len(matrix['fps'][router])}):")
            for cid, prompt, act, exp in matrix["fps"][router]:
                lines.append(f"  {cid} {prompt!r} -> got={act!r}, expected={exp!r}")
        if matrix["fns"][router]:
            lines.append(f"FNs ({router}, {len(matrix['fns'][router])}):")
            for cid, prompt, act, exp in matrix["fns"][router]:
                lines.append(f"  {cid} {prompt!r} -> got={act!r}, expected={exp!r}")
    return "\n".join(lines)


def main() -> int:
    config, session = make_corpus_config_and_session()
    matrix = evaluate(config, session)
    print(summarize(matrix))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
