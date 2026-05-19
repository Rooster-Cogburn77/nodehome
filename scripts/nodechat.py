#!/usr/bin/env python3
"""Terminal client for the local Nodehome model stack.

Local agentic terminal environment for Nodehome. Talks to an OpenAI-compatible
local endpoint (today: vLLM), persists sessions, auto-routes private AI History
and repo file context when the user prompt clearly calls for it, and exposes
explicit slash commands for context, edits, and approved-scope commands.

Authoritative scope: docs/runbooks/nodechat-scope.md.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import html
import ipaddress
import json
import os
import pathlib
import re
import shlex
import shutil
import subprocess
import sys
import textwrap
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, replace
from html.parser import HTMLParser
from pathlib import PurePosixPath
from typing import Any


DEFAULT_MODEL = "Qwen/Qwen2.5-32B-Instruct-AWQ"
DEFAULT_BASE_URL = "http://127.0.0.1:8000/v1"
DEFAULT_HISTORY_URL = "http://127.0.0.1:8765"
DEFAULT_SESSION_ROOT = pathlib.Path.home() / ".nodehome" / "nodechat"
DEFAULT_WORKSPACE = pathlib.Path(os.environ.get("NODECHAT_WORKSPACE", pathlib.Path.cwd()))
BUILTIN_MODEL_PROFILES: dict[str, dict[str, str]] = {
    "fast": {
        "model": "mistral-small3.1:24b",
        "base_url": "http://localhost:11434/v1",
        "provider": "Ollama",
        "speed": "51 tok/s",
        "description": "single-3090 interactive daily-driver lane",
    },
    "strong": {
        "model": DEFAULT_MODEL,
        "base_url": DEFAULT_BASE_URL,
        "provider": "vLLM",
        "speed": "59 tok/s",
        "description": "TP=2 validated main quality lane",
    },
    "deep": {
        "model": "llama3.3:70b-instruct-q4_K_M",
        "base_url": "http://localhost:11434/v1",
        "provider": "Ollama",
        "speed": "8-15 tok/s",
        "description": "slow willing-to-wait deep lane",
    },
}
MAX_CONTEXT_CHARS = 9000
MAX_READ_BYTES = 160000
MAX_WEB_BYTES = 512000
MAX_TREE_ENTRIES = 180
MAX_SEARCH_RESULTS = 40
MAX_SEARCH_FILE_BYTES = 220000
MAX_PROPOSE_FILE_CHARS = 30000
MAX_PROPOSAL_TOKENS = 2400
MAX_CMD_OUTPUT_CHARS = 20000
LIVE_OUTPUT_TRUNCATED_HEAD = "...[truncated earlier output for nodechat live output cap]"
LIVE_OUTPUT_TRUNCATED_TAIL = "...[truncated for nodechat live output cap]"
MAX_APPROVALS = 50
MAX_DIRECT_PASTE_LINES = 400
MAX_DIRECT_PASTE_CHARS = 60000
DIRECT_PASTE_QUIET_SECONDS = 0.03
HUNK_RE = re.compile(r"^@@ -(?P<old_start>\d+)(?:,(?P<old_count>\d+))? \+(?P<new_start>\d+)(?:,(?P<new_count>\d+))? @@")

BLOCKED_PATH_PARTS = {
    ".git",
    ".nodehome",
    ".ssh",
    ".venv",
    "__pycache__",
    "node_modules",
    "chat-exports",
    "node-private",
}
BLOCKED_FILE_EXTENSIONS = {
    ".7z",
    ".aab",
    ".db",
    ".dll",
    ".exe",
    ".iso",
    ".jpg",
    ".jpeg",
    ".pdf",
    ".pem",
    ".p8",
    ".png",
    ".sqlite",
    ".webp",
    ".xlsx",
    ".zip",
}
SECRET_NAME_PATTERNS = (
    ".env",
    "authkey",
    "credential",
    "id_ed25519",
    "id_rsa",
    "password",
    "secret",
    "subscriptionkey",
    "token",
)
TEXT_EXTENSIONS = {
    "",
    ".bat",
    ".cmd",
    ".css",
    ".csv",
    ".dockerfile",
    ".env.example",
    ".gitignore",
    ".html",
    ".js",
    ".json",
    ".jsonl",
    ".jsx",
    ".md",
    ".ps1",
    ".py",
    ".sh",
    ".sql",
    ".toml",
    ".ts",
    ".tsx",
    ".txt",
    ".yaml",
    ".yml",
}

DEFAULT_HISTORY_MODE = "auto"
DEFAULT_REPO_MODE = "auto"
DEFAULT_MODEL_MODE = "auto"
MODEL_MODE_CONTROLS = ("auto", "manual")
MODEL_MODES = ("auto", "manual", "fast", "strong", "deep")
AUTO_STRONG_LENGTH_THRESHOLD = 800
VLLM_PROBE_TTL_S = 60
VLLM_PROBE_TIMEOUT_S = 3
ANTHROPIC_API_VERSION = "2023-06-01"
ANTHROPIC_DEFAULT_MAX_TOKENS = 2048
AUTO_STRONG_CODE_RE = re.compile(
    r"```|"
    r"\b(def|class|function|import|return|async|await|lambda|"
    r"traceback|exception|stack[\s-]?trace|stacktrace|segfault)\b|"
    r"\berror\s*:|"
    r"^\s*from\s+\w+\s+import\b",
    re.I | re.MULTILINE,
)
AUTO_STRONG_ANALYSIS_RE = re.compile(
    r"\b(analy[sz]e|review|compare|diagnose|refactor|design|"
    r"deep\s*dive|walk\s*me\s*through|step[\s-]by[\s-]step|"
    r"explain\s+(?:in\s+detail|thoroughly|carefully)|"
    r"audit|architect)\b",
    re.I,
)
GENERATION_POLICY_DEFAULT = "default"
GENERATION_POLICY_LONG_CONTEXT = "long_context"
GENERATION_POLICY_GROUNDED_ANALYSIS = "grounded_analysis"
GENERATION_POLICY_CODE_PATCH = "code_patch"
GENERATION_POLICY_LIMITS = {
    GENERATION_POLICY_DEFAULT: {"temperature": None, "max_tokens": 0},
    GENERATION_POLICY_LONG_CONTEXT: {"temperature": 0.2, "max_tokens": 3072},
    GENERATION_POLICY_GROUNDED_ANALYSIS: {"temperature": 0.1, "max_tokens": 3072},
    GENERATION_POLICY_CODE_PATCH: {"temperature": 0.0, "max_tokens": 4096},
}
FORCE_ANSWER_PREFIX_RE = re.compile(r"^\s*answer\s+anyway\s*:\s*", re.I)
PROJECT_SPECIFIC_PROMPT_RE = re.compile(
    r"\b("
    r"repo|repository|codebase|project|nodechat|nodehome|homelab|sovereign|"
    r"sweeps?|runbook|current_state|session_log|scratch|bmc|ipmi|gpu\d?|"
    r"vllm|ollama|open\s*webui|jellyfin|x\s+email|ingest_x_email|"
    r"commit|diff|branch|working\s+tree|git\s+status"
    r")\b",
    re.I,
)
DEFAULT_WEB_MODE = "auto"
DEFAULT_LIVE_MODE = "auto"
ROUTING_MODES = ("auto", "manual", "off")
REPO_AUTO_LIMIT = 2
WEB_AUTO_URL_LIMIT = 2
WEB_AUTO_TIMEOUT = 12
LIVE_AUTO_LIMIT = 3

# History routing patterns are split into two groups:
#   TIGHT patterns are already project-bound by their phrasing ("we", "session",
#     "prior decision", etc.) and route on a match alone.
#   BROAD patterns ("remind me", "previously", "history of", "have we ever",
#     "has X ever", "what was our reasoning") match enough natural English to
#     trip on personal reminders or general-knowledge questions; they route
#     only when the prompt also contains a project-context token.
# HISTORY_AUTO_PATTERNS keeps the union for any caller that imports it.
HISTORY_TIGHT_PATTERNS = (
    re.compile(r"\bwhat did we\b", re.I),
    re.compile(r"\bwhen did we\b", re.I),
    re.compile(r"\bhow did we\b", re.I),
    re.compile(r"\bwhy did we\b", re.I),
    re.compile(r"\bwhere did we\b", re.I),
    re.compile(r"\bdid we (?:ever|already|decide)\b", re.I),
    re.compile(r"\bwho decided\b", re.I),
    re.compile(r"\bprior (?:decision|run|incident|session)\b", re.I),
    re.compile(r"\bearlier (?:session|today|this week|decision)\b", re.I),
    re.compile(r"\blast (?:session|time|week|month) we\b", re.I),
)
HISTORY_BROAD_PATTERNS = (
    re.compile(r"\bremind me\b", re.I),
    re.compile(r"\bpreviously\b", re.I),
    re.compile(r"\bhistory of\b", re.I),
    re.compile(r"\bhave we (?:ever|already|done|tried|tested|run|configured|fixed|bought|ordered|installed|capped|set|written|added|moved)\b", re.I),
    re.compile(r"\bhas (?:our|the|this|that|a|an) [\w][\w\s]{0,40}? ever\b", re.I),
    re.compile(r"\bwhat was (?:our|the) (?:reasoning|reason|plan|approach|thinking|decision|conclusion|rationale|call)\b", re.I),
)
HISTORY_AUTO_PATTERNS = HISTORY_TIGHT_PATTERNS + HISTORY_BROAD_PATTERNS

HISTORY_PROJECT_CONTEXT_RE = re.compile(
    r"""\b(
        # first-person plural (project-team voice)
        we|our|us|ours
        # node + topology
        |node|nodehome|homelab|sovereign|stack|build|builds|cluster|rack|chassis
        # GPUs / silicon
        |gpu|gpu\d|nvidia|cuda|3090|3090s|epyc|h12ssl|supermicro|tdp|tp=\d
        # memory / storage / power
        |ram|rdimm|lrdimm|samsung|hpe|ddr4|ecc|psu|leadex|sf-1600f14ht
        |cable|cables|pigtail|nvme|ssd|hdd|drive|drives|easystore|paymore
        |ups|smt2200|apc
        # OOB management
        |bmc|ipmi
        # software stack
        |ollama|vllm|qwen|mistral|gemma|llama|docker|webui|open[\s-]?webui
        |claude|codex|nodechat|sweep|sweeps|operator|brief|healthcheck
        # specific sellers / parts we've named
        |scw|kuaka02|lizzieb753|sv2deals|yellowchoo|silverstone|noctua|tedgetal
        # power / thermal / benchmarks
        |cap|capped|thermal|thermals|fan|temp|temps|benchmark|benchmarked
        # decision-state words
        |decide|decision|incident|outage|escalation|dispute
    )\b""",
    re.I | re.VERBOSE,
)

REPO_NAMED_FILE_PATTERNS = (
    (re.compile(r"\bCURRENT_STATE(?:\.md)?\b"), "docs/CURRENT_STATE.md"),
    (re.compile(r"\bSESSION_LOG(?:\.md)?\b"), "docs/SESSION_LOG.md"),
    (re.compile(r"\bCLAUDE\.md\b", re.I), "CLAUDE.md"),
    (re.compile(r"\bSCRATCH\.md\b", re.I), "SCRATCH.md"),
    (re.compile(r"\bATTITUDE\.md\b", re.I), "ATTITUDE.md"),
)

REPO_RUNBOOK_STEMS = (
    "nodechat-scope",
    "nodechat-terminal",
    "ipmi-recovery",
    "ipmi-hardening",
    "home-media-server",
    "hardware-upgrade-roadmap",
    "ai-history-knowledge-base",
    "nvidia-power-cap",
    "upgrade-cadence",
    "bmc-fan-thresholds",
)
REPO_RUNBOOK_RE = re.compile(
    r"\b(" + "|".join(re.escape(stem) for stem in REPO_RUNBOOK_STEMS) + r")\b",
    re.I,
)

REPO_PATH_RE = re.compile(
    r"(?<![A-Za-z0-9_/\\])(?:docs|scripts|sweeps|site|tests|memory)[\\/][A-Za-z0-9_./\\\-]+"
)

REPO_SUMMARY_DOCS = (
    "docs/CURRENT_STATE.md",
    "docs/wiki/concepts/full-stack-inventory.md",
)
REPO_SUMMARY_SUBJECT_RE = re.compile(
    r"\b(codebase|repo(?:sitory)?|project|nodehome|local[_ -]?ai)\b",
    re.I,
)
REPO_SUMMARY_NONLIVE_SUBJECT_RE = re.compile(
    r"\b(codebase|repo(?:sitory)?|project|local[_ -]?ai)\b",
    re.I,
)
REPO_SUMMARY_INTENT_RE = re.compile(
    r"\b("
    r"summari[sz]e|summary|overview|progress|current\s+(?:progress|status)|"
    r"completed|complete|done|outstanding|left|stack|capabilit(?:y|ies)"
    r")\b",
    re.I,
)

WEB_URL_RE = re.compile(r"https?://[^\s<>\]\"')]+", re.I)
WEB_EXPLICIT_RE = re.compile(
    r"\b(search|look up|look for|browse|web|internet|online|google|verify online|check online)\b",
    re.I,
)
WEB_FRESH_RE = re.compile(
    r"\b(latest|current|currently|recent|newest|today|now|upstream|release|released|"
    r"version|changelog|pricing|price|cost|buy|listing|market|stock|available|"
    r"availability|cve|vulnerability|advisory|exploit)\b",
    re.I,
)
WEB_PUBLIC_OBJECT_RE = re.compile(
    r"\b(vllm|ollama|open webui|qwen|llama|nvidia|cuda|driver|firmware|github|"
    r"amazon|ebay|walmart|best buy|router|switch|ups|apc|ram|ssd|hdd|hard drive|"
    r"model|release|pricing|price|cve|vulnerability)\b",
    re.I,
)
WEB_LOCAL_ONLY_RE = re.compile(
    r"""\b(
        # First-person pronouns / project ownership
        our|my|us|ours
        # Project nouns
        |local|nodehome|homelab|sovereign
        |gpu0|gpu1|gpu2|gpu3|pigtail|rack|chassis
        # Status framing that's about local state, not public lookup
        |current\ state|status
        # Plural "all three" / "all 3" only makes sense for our 3-card box
        |across\ all\ (?:three|two|3|2)
        |all\ (?:three|two|3|2)\ (?:cards|gpus|3090s)
        # Prepositional locality: "on the node", "in a container", etc.
        |the\ (?:node|box|rack|chassis|stack|build|cluster|server|host|machine)
        |on\ the\ (?:node|box|server|host|machine)
        |in\ (?:the|a)\ (?:rack|container|chassis|cabinet)
        # Local hardware/operational nouns
        |container|containers
        |power\ draw|power\ cap|power\ limit|fan\ curve
        # First-person plural construction "we built / trained / configured / ordered"
        |we\ (?:built|made|trained|created|configured|installed|capped|bought|
              ordered|wrote|fixed|added|landed|shipped|deployed|patched|tested|
              benchmarked|validated|run|ran)
    )\b""",
    re.I | re.VERBOSE,
)

LIVE_TRIGGER_RE = re.compile(
    r"\b(live|current|currently|status|health|healthy|running|up|down|check|diagnose|"
    r"verify|what is running|what's running|how is)\b",
    re.I,
)
LIVE_OBJECT_RE = re.compile(
    r"\b(node|nodehome|homelab|stack|service|gpu|nvidia|docker|container|vllm|ollama|"
    r"open webui|webui|disk|storage|filesystem|df|bmc|ipmi|power cap|power limit|"
    r"healthcheck|ups|box)\b",
    re.I,
)
# When a prompt clearly points at a public destination ("on github", "on
# huggingface", "online") and has no local hint, live should not fire even
# if it shares an object word with the live router (e.g. "ollama version on
# github" is a web-search prompt, not a live-status prompt).
LIVE_PUBLIC_DEST_RE = re.compile(
    r"\b(github|huggingface|hugging\s*face|amazon|ebay|walmart|best\s*buy|"
    r"newegg|reddit|stack\s*overflow|hacker\s*news|google|"
    r"online|on\s+the\s+(?:web|internet))\b",
    re.I,
)
LIVE_LOCAL_HINT_RE = re.compile(
    r"""\b(
        our|my|us|ours|local|nodehome|homelab|sovereign
        |the\ (?:node|box|rack|chassis|stack|build|cluster|server|host|machine)
        |on\ the\ (?:node|box|server|host|machine)
        |in\ (?:the|a)\ (?:rack|container|chassis|cabinet)
    )\b""",
    re.I | re.VERBOSE,
)
SMART_DEVICE_RE = re.compile(r"^/dev/[A-Za-z0-9_.\-/]+$")

DEFAULT_SYSTEM_PROMPT = """\
You are Nodechat, the local agentic terminal environment for the Nodehome homelab.

Be direct, factual, and pragmatic. Separate observed facts from inference.
Your current serving model and endpoint are provided in a NODECHAT_RUNTIME
system message. If asked what model you are, answer from that runtime message.
Do not claim to be custom-built or model-less.

Some context is auto-routed into the conversation when the user prompt clearly
calls for it (private AI History, repo files, fresh public web context, live
node status). Other context is injected only when the user runs a slash command
such as /history, /read, /tree, /search-files, /git-status, /web-fetch,
/web-search, /live, /cmd, or approved command output from /approve. Treat
HISTORY_CONTEXT and NODECHAT_TOOL_CONTEXT blocks as evidence with provenance,
not as general world knowledge. Do not claim to have searched private history,
read a file, searched/fetched the web, or checked live node state unless the
corresponding context block is present in this conversation.
For repo/project state, stack, capability, file, or implementation claims, if
no repo/history/live/web context block is present, say there is not enough
loaded evidence and ask for a specific context route instead of inferring repo
contents from project names or user wording.

Patch proposals created by /propose-edit are proposals only. Do not claim they
were applied unless the user explicitly applies them.

You do not have arbitrary shell or freeform file-write access. Mutations
require explicit user approval via /approve or /apply --confirm.
"""


@dataclass
class Config:
    base_url: str
    model: str
    api_key: str
    stream: bool
    temperature: float
    max_tokens: int
    timeout: int
    max_history_messages: int
    session_root: pathlib.Path
    workspace: pathlib.Path
    history_url: str
    history_token: str
    history_limit: int
    cmd_timeout: int
    live_ssh: str
    live_root: str


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def session_id() -> str:
    return dt.datetime.now().strftime("%Y%m%d-%H%M%S")


def safe_filename(value: str) -> str:
    keep = []
    for char in value:
        if char.isalnum() or char in {"-", "_", "."}:
            keep.append(char)
        else:
            keep.append("_")
    return "".join(keep)[:120] or "session"


def first_env_name(*names: str) -> str:
    for name in names:
        if os.environ.get(name):
            return name
    return ""


def env_float(name: str, default: float = 0.0) -> float:
    value = os.environ.get(name, "").strip()
    if not value:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def normalize_model_profile(
    name: str,
    raw: Any,
    source: str,
    *,
    allow_remote: bool = False,
) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    profile_name = str(name or "").strip().lower()
    model = str(raw.get("model") or "").strip()
    base_url = str(raw.get("base_url") or raw.get("baseUrl") or raw.get("endpoint") or "").strip().rstrip("/")
    if not profile_name or not model or not base_url:
        return None
    remote = bool(raw.get("remote"))
    if not is_local_model_endpoint(base_url) and not (allow_remote and remote):
        return None
    return {
        "name": profile_name,
        "model": model,
        "base_url": base_url,
        "provider": str(raw.get("provider") or raw.get("runtime") or "").strip(),
        "provider_kind": str(raw.get("provider_kind") or raw.get("providerKind") or "openai-compatible").strip().lower(),
        "speed": str(raw.get("speed") or "").strip(),
        "description": str(raw.get("description") or raw.get("notes") or "").strip(),
        "source": source,
        "remote": remote,
        "api_key_env": str(raw.get("api_key_env") or raw.get("apiKeyEnv") or "").strip(),
        "input_per_mtok_usd": float(raw.get("input_per_mtok_usd") or 0.0),
        "output_per_mtok_usd": float(raw.get("output_per_mtok_usd") or 0.0),
    }


def is_local_model_endpoint(base_url: str) -> bool:
    parsed = urllib.parse.urlparse(base_url)
    host = (parsed.hostname or "").strip().lower()
    if host in {"localhost", "host.docker.internal"}:
        return True
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    return ip.is_loopback or ip.is_private or ip.is_link_local


def model_profiles_path(config: "Config") -> pathlib.Path:
    return config.session_root / "profiles.json"


def builtin_model_profiles(config: "Config") -> dict[str, dict[str, str]]:
    profiles = {name: dict(raw) for name, raw in BUILTIN_MODEL_PROFILES.items()}
    strong_url = os.environ.get("NODECHAT_STRONG_BASE_URL", "").strip().rstrip("/")
    profiles["strong"]["base_url"] = strong_url or str(config.base_url).rstrip("/")
    ollama_url = os.environ.get("NODECHAT_OLLAMA_BASE_URL", "").strip().rstrip("/")
    if ollama_url:
        profiles["fast"]["base_url"] = ollama_url
        profiles["deep"]["base_url"] = ollama_url
    return profiles


def remote_builtin_model_profiles() -> dict[str, dict[str, Any]]:
    """Return env-gated remote profiles.

    Remote providers are intentionally absent unless both an API key and a
    model id are configured. This avoids hard-coding drift-prone remote model
    names and makes cost-bearing providers opt-in at process launch.
    """
    profiles: dict[str, dict[str, Any]] = {}

    openai_key = first_env_name("NODECHAT_OPENAI_API_KEY", "OPENAI_API_KEY")
    openai_model = os.environ.get("NODECHAT_OPENAI_MODEL", "").strip()
    if openai_key and openai_model:
        profiles["openai"] = {
            "model": openai_model,
            "base_url": os.environ.get("NODECHAT_OPENAI_BASE_URL", "https://api.openai.com/v1").strip().rstrip("/"),
            "provider": "OpenAI",
            "provider_kind": "openai",
            "description": "remote OpenAI profile; explicit enable required",
            "remote": True,
            "api_key_env": openai_key,
            "input_per_mtok_usd": env_float("NODECHAT_OPENAI_INPUT_PER_MTOK"),
            "output_per_mtok_usd": env_float("NODECHAT_OPENAI_OUTPUT_PER_MTOK"),
        }

    anthropic_key = first_env_name("NODECHAT_ANTHROPIC_API_KEY", "ANTHROPIC_API_KEY")
    anthropic_model = os.environ.get("NODECHAT_ANTHROPIC_MODEL", "").strip()
    if anthropic_key and anthropic_model:
        profiles["anthropic"] = {
            "model": anthropic_model,
            "base_url": os.environ.get("NODECHAT_ANTHROPIC_BASE_URL", "https://api.anthropic.com/v1").strip().rstrip("/"),
            "provider": "Anthropic",
            "provider_kind": "anthropic",
            "description": "remote Anthropic Messages API profile; explicit enable required",
            "remote": True,
            "api_key_env": anthropic_key,
            "input_per_mtok_usd": env_float("NODECHAT_ANTHROPIC_INPUT_PER_MTOK"),
            "output_per_mtok_usd": env_float("NODECHAT_ANTHROPIC_OUTPUT_PER_MTOK"),
        }

    return profiles


def load_model_profiles(config: "Config") -> dict[str, dict[str, Any]]:
    profiles: dict[str, dict[str, Any]] = {}
    for name, raw in builtin_model_profiles(config).items():
        profile = normalize_model_profile(name, raw, "builtin")
        if profile:
            profiles[name] = profile
    for name, raw in remote_builtin_model_profiles().items():
        profile = normalize_model_profile(name, raw, "remote-builtin", allow_remote=True)
        if profile:
            profiles[name] = profile

    path = model_profiles_path(config)
    if not path.exists():
        return profiles
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return profiles
    if isinstance(raw, dict) and isinstance(raw.get("profiles"), dict):
        raw = raw["profiles"]
    if not isinstance(raw, dict):
        return profiles
    for name, value in raw.items():
        profile = normalize_model_profile(str(name), value, "user")
        if profile:
            profiles[profile["name"]] = profile
    return profiles


def infer_model_profile(config: "Config", base_url: str, model: str) -> str:
    base_url = str(base_url or "").rstrip("/")
    model = str(model or "")
    for name, profile in load_model_profiles(config).items():
        if profile["base_url"].rstrip("/") == base_url and profile["model"] == model:
            return name
    return ""


def active_model_profile(config: "Config", session: dict[str, Any]) -> str:
    profile = str(session.get("profile") or "").strip().lower()
    if profile and profile in load_model_profiles(config):
        return profile
    return infer_model_profile(
        config,
        str(session.get("base_url") or config.base_url),
        str(session.get("model") or config.model),
    )


def apply_model_profile(session: dict[str, Any], profile: dict[str, str]) -> None:
    session["profile"] = profile["name"]
    session["model"] = profile["model"]
    session["base_url"] = profile["base_url"].rstrip("/")


def profile_is_remote(profile: dict[str, Any] | None) -> bool:
    return bool(profile and profile.get("remote"))


def remote_models_enabled(session: dict[str, Any]) -> bool:
    return bool(session.get("remote_models_enabled"))


def model_profile_for_dispatch(config: "Config", profile_name: str) -> dict[str, Any] | None:
    return load_model_profiles(config).get(str(profile_name or "").strip().lower())


def active_model_profile_data(config: "Config", session: dict[str, Any]) -> dict[str, Any] | None:
    name = active_model_profile(config, session)
    if not name:
        return None
    return model_profile_for_dispatch(config, name)


def profile_api_key(profile: dict[str, Any] | None) -> str:
    env_name = str((profile or {}).get("api_key_env") or "")
    return os.environ.get(env_name, "") if env_name else ""


def model_auth_headers(config: "Config", session: dict[str, Any]) -> dict[str, str]:
    profile = active_model_profile_data(config, session)
    if profile_is_remote(profile):
        key = profile_api_key(profile)
        return {"Authorization": f"Bearer {key}"} if key else {}
    return auth_headers(config.api_key)


def valid_model_modes(config: "Config") -> tuple[str, ...]:
    profiles = tuple(sorted(load_model_profiles(config)))
    return MODEL_MODE_CONTROLS + profiles


def model_disclosure(config: "Config", session: dict[str, Any]) -> str:
    profile = active_model_profile(config, session)
    if profile:
        return f"model: {profile}"
    return f"model: literal {session.get('model') or config.model}"


def vllm_available_cached(
    config: "Config",
    session: dict[str, Any],
    base_url: str,
) -> tuple[bool, int]:
    """Cached vLLM /models reachability probe. TTL: VLLM_PROBE_TTL_S seconds.

    Cache lives in session under "_vllm_probe" keyed by base_url so probes
    survive within a session but never persist past TTL. Failures cache too,
    so a long fallback chain doesn't pay the timeout repeatedly.
    """
    base_url = (base_url or "").rstrip("/")
    cache = session.setdefault("_vllm_probe", {})
    cached = cache.get(base_url)
    now = time.time()
    if isinstance(cached, dict) and now - float(cached.get("ts") or 0) < VLLM_PROBE_TTL_S:
        return bool(cached.get("ok")), int(cached.get("latency_ms") or 0)
    started = time.time()
    ok = False
    try:
        with urllib.request.urlopen(base_url + "/models", timeout=VLLM_PROBE_TIMEOUT_S) as res:
            res.read(1)
            ok = True
    except Exception:
        ok = False
    latency_ms = int((time.time() - started) * 1000)
    cache[base_url] = {"ok": ok, "latency_ms": latency_ms, "ts": now}
    return ok, latency_ms


def detect_strong_triggers(config: "Config", session: dict[str, Any], prompt: str) -> list[str]:
    """Return the list of strong-lift trigger reasons that fired on this prompt."""
    reasons: list[str] = []
    text = prompt or ""
    if len(text) > AUTO_STRONG_LENGTH_THRESHOLD:
        reasons.append(f"long prompt ({len(text)} chars)")
    if AUTO_STRONG_CODE_RE.search(text):
        reasons.append("code markers")
    if AUTO_STRONG_ANALYSIS_RE.search(text):
        reasons.append("analysis verbs")
    if detect_history_query(text):
        reasons.append("history-routing intent")
    repo_targets = detect_repo_targets(config, session, text)
    if len(repo_targets) >= 2:
        reasons.append(f"multi-file repo routing ({len(repo_targets)} files)")
    return reasons


def pick_turn_dispatch(
    config: "Config",
    session: dict[str, Any],
    prompt: str,
) -> dict[str, Any]:
    """Resolve the (profile, model, base_url) to dispatch this turn.

    Per-turn only: session.profile / session.model / session.base_url stay
    unchanged. The user's configured profile is only used as the dispatch
    target when model_mode == "manual".
    """
    profiles = load_model_profiles(config)
    mode = str(session.get("model_mode") or DEFAULT_MODEL_MODE).strip().lower()
    if mode not in valid_model_modes(config):
        mode = DEFAULT_MODEL_MODE

    configured_profile_name = active_model_profile(config, session) or ""
    configured_model = str(session.get("model") or config.model)
    configured_base_url = str(session.get("base_url") or config.base_url).rstrip("/")

    def resolved(profile_name: str) -> tuple[str, str, str]:
        profile = profiles.get(profile_name)
        if profile:
            return profile_name, profile["model"], profile["base_url"].rstrip("/")
        # Profile name not found -- fall back to configured.
        return (configured_profile_name or "literal"), configured_model, configured_base_url

    def set_from_profile(profile_name: str) -> None:
        name, model, base_url = resolved(profile_name)
        dispatch["profile"] = name
        dispatch["model"] = model
        dispatch["base_url"] = base_url
        profile = profiles.get(name)
        if profile_is_remote(profile):
            dispatch["remote"] = True
            dispatch["provider_kind"] = profile.get("provider_kind") or "remote"
        else:
            dispatch["remote"] = False
            dispatch["provider_kind"] = (profile or {}).get("provider_kind") or "openai-compatible"

    def remote_disabled_fallback(profile_name: str) -> bool:
        profile = profiles.get(profile_name)
        if not profile_is_remote(profile) or remote_models_enabled(session):
            return False
        set_from_profile("fast")
        dispatch["fallback"] = True
        dispatch["rationale"] = f"remote profile '{profile_name}' disabled: run /remote-models enable"
        dispatch["remote_blocked"] = True
        return True

    dispatch: dict[str, Any] = {
        "mode": mode,
        "configured_profile": configured_profile_name or "literal",
        "configured_model": configured_model,
        "configured_base_url": configured_base_url,
        "auto_routed": False,
        "fallback": False,
        "rationale": "",
        "vllm_available": None,
        "vllm_probe_ms": None,
        "triggers": [],
    }
    triggers = detect_strong_triggers(config, session, prompt)
    dispatch["triggers"] = triggers

    if mode in profiles:
        if remote_disabled_fallback(mode):
            return dispatch
        set_from_profile(mode)
        return dispatch

    if mode == "manual":
        # Use the configured profile / model / endpoint as-is.
        if configured_profile_name and configured_profile_name in profiles:
            if remote_disabled_fallback(configured_profile_name):
                return dispatch
            set_from_profile(configured_profile_name)
        else:
            dispatch["profile"] = configured_profile_name or "literal"
            dispatch["model"] = configured_model
            dispatch["base_url"] = configured_base_url
            dispatch["remote"] = False
            dispatch["provider_kind"] = "openai-compatible"
        return dispatch

    # mode == "auto"
    if not triggers:
        # Default to fast.
        set_from_profile("fast")
        return dispatch

    # Want strong -- probe vLLM first.
    strong_profile = profiles.get("strong")
    strong_base_url = (strong_profile or {}).get("base_url", "").rstrip("/")
    if not strong_base_url:
        # No strong profile available; fall back to fast silently (shouldn't happen with builtins).
        set_from_profile("fast")
        dispatch["fallback"] = True
        dispatch["rationale"] = "strong unavailable: no strong profile registered"
        return dispatch

    ok, latency_ms = vllm_available_cached(config, session, strong_base_url)
    dispatch["vllm_available"] = ok
    dispatch["vllm_probe_ms"] = latency_ms

    if ok:
        set_from_profile("strong")
        dispatch["auto_routed"] = True
        dispatch["rationale"] = "; ".join(triggers)
        return dispatch

    # vLLM unhealthy -- fall back to fast and disclose.
    set_from_profile("fast")
    dispatch["fallback"] = True
    dispatch["rationale"] = f"strong unavailable: vLLM probe failed ({latency_ms}ms)"
    return dispatch


def context_source_names(session: dict[str, Any]) -> list[str]:
    names: list[str] = []
    for block in session.get("context_blocks", []):
        source = str(block.get("source") or "manual-legacy")
        if source not in names:
            names.append(source)
    return names


def resolve_generation_policy(
    config: Config,
    session: dict[str, Any],
    dispatch: dict[str, Any],
) -> dict[str, Any]:
    """Resolve per-turn generation params from existing route signals.

    This consumes model-router triggers and active context source labels. It
    intentionally does not introduce another prompt classifier.
    """
    triggers = [str(item) for item in (dispatch.get("triggers") or [])]
    sources = context_source_names(session)
    reasons: list[str] = []
    policy = GENERATION_POLICY_DEFAULT

    if any(item == "code markers" for item in triggers):
        policy = GENERATION_POLICY_CODE_PATCH
        reasons.append("auto-route trigger: code markers")
    elif any(item == "analysis verbs" for item in triggers):
        policy = GENERATION_POLICY_GROUNDED_ANALYSIS
        reasons.append("auto-route trigger: analysis verbs")
    elif any(source.startswith(("auto-repo", "manual-read", "manual-search", "manual-git-status")) for source in sources):
        policy = GENERATION_POLICY_GROUNDED_ANALYSIS
        reasons.append("repo evidence loaded")
    elif any(source.startswith(("auto-history", "manual-history")) for source in sources):
        policy = GENERATION_POLICY_GROUNDED_ANALYSIS
        reasons.append("history evidence loaded")
    elif any(source.startswith(("auto-web", "manual-web")) for source in sources):
        policy = GENERATION_POLICY_GROUNDED_ANALYSIS
        reasons.append("web evidence loaded")
    elif any(source.startswith(("auto-live", "manual-live")) for source in sources):
        policy = GENERATION_POLICY_GROUNDED_ANALYSIS
        reasons.append("live evidence loaded")
    elif any(str(item).startswith("long prompt") for item in triggers):
        policy = GENERATION_POLICY_LONG_CONTEXT
        reasons.append("auto-route trigger: long prompt")

    limits = GENERATION_POLICY_LIMITS[policy]
    policy_temperature = limits["temperature"]
    if policy_temperature is None:
        temperature = float(config.temperature)
    else:
        temperature = min(float(config.temperature), float(policy_temperature))

    policy_max_tokens = int(limits["max_tokens"])
    max_tokens = max(int(config.max_tokens), policy_max_tokens)

    return {
        "name": policy,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "reasons": reasons,
        "context_sources": sources,
    }


def turn_disclosure(config: "Config", session: dict[str, Any], routed: str | None) -> str:
    """Compatibility shim: builds the legacy [model: X | routed] line.

    The new send_user_prompt path uses dispatch_disclosure() with a dispatch
    dict so it can render auto-route rationales. This helper still exists for
    callers that haven't been updated, and renders without auto-route info.
    """
    parts = [model_disclosure(config, session)]
    if routed:
        text = routed.strip()
        if text.startswith("[") and text.endswith("]"):
            text = text[1:-1]
        if text:
            parts.append(text)
    return "[" + " | ".join(parts) + "]"


def dispatch_disclosure(dispatch: dict[str, Any], routed: str | None) -> str:
    """Render the per-turn disclosure line from a dispatch dict + context-routing line."""
    profile = dispatch.get("profile") or "literal"
    if dispatch.get("fallback"):
        head = f"model: {profile} <- {dispatch.get('rationale', 'fallback')}"
    elif dispatch.get("auto_routed"):
        head = f"model: {profile} <- auto-routed: {dispatch.get('rationale', '')}"
    else:
        head = f"model: {profile}"
    parts = [head]
    if routed:
        text = routed.strip()
        if text.startswith("[") and text.endswith("]"):
            text = text[1:-1]
        if text:
            parts.append(text)
    return "[" + " | ".join(parts) + "]"


def ensure_session_dir(config: Config) -> pathlib.Path:
    path = config.session_root / "sessions"
    path.mkdir(parents=True, exist_ok=True)
    return path


def ensure_backup_dir(config: Config, session: dict[str, Any]) -> pathlib.Path:
    path = config.session_root / "backups" / safe_filename(str(session.get("id", "session")))
    path.mkdir(parents=True, exist_ok=True)
    return path


def ensure_audit_dir(config: Config) -> pathlib.Path:
    path = config.session_root / "audit"
    path.mkdir(parents=True, exist_ok=True)
    return path


def audit_log_path(config: Config) -> pathlib.Path:
    return ensure_audit_dir(config) / "nodechat-audit.jsonl"


def make_session(config: Config) -> dict[str, Any]:
    sid = session_id()
    profile = infer_model_profile(config, config.base_url, config.model)
    return {
        "id": sid,
        "created_at": utc_now(),
        "updated_at": utc_now(),
        "cwd": str(config.workspace),
        "base_url": config.base_url,
        "model": config.model,
        "profile": profile,
        "system": DEFAULT_SYSTEM_PROMPT,
        "messages": [],
        "context_blocks": [],
        "approvals": [],
        "history_mode": DEFAULT_HISTORY_MODE,
        "repo_mode": DEFAULT_REPO_MODE,
        "web_mode": DEFAULT_WEB_MODE,
        "live_mode": DEFAULT_LIVE_MODE,
        "model_mode": DEFAULT_MODEL_MODE,
        "remote_models_enabled": False,
        "costs": {},
    }


def session_path(config: Config, session: dict[str, Any]) -> pathlib.Path:
    return ensure_session_dir(config) / f"{safe_filename(session['id'])}.json"


def save_session(config: Config, session: dict[str, Any]) -> pathlib.Path:
    session["updated_at"] = utc_now()
    path = session_path(config, session)
    try:
        path.write_text(json.dumps(session, indent=2, ensure_ascii=False), encoding="utf-8")
    except OSError as exc:
        print(f"warning: could not save nodechat session {path}: {exc}", file=sys.stderr)
    return path


def output_digest(output: str) -> dict[str, Any]:
    text = str(output or "")
    return {
        "output_chars": len(text),
        "output_sha256": hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest(),
    }


def estimate_tokens_from_chars(chars: int) -> int:
    if chars <= 0:
        return 0
    return max(1, int((chars + 3) / 4))


def remote_cost_estimate(
    config: Config,
    dispatch: dict[str, Any],
    prompt_chars: int,
    response_chars: int,
) -> dict[str, Any]:
    profile = model_profile_for_dispatch(config, str(dispatch.get("profile") or ""))
    if not profile_is_remote(profile):
        return {
            "remote": False,
            "provider_kind": dispatch.get("provider_kind") or "openai-compatible",
            "estimated_input_tokens": 0,
            "estimated_output_tokens": 0,
            "estimated_cost_usd": 0.0,
        }
    input_tokens = estimate_tokens_from_chars(prompt_chars)
    output_tokens = estimate_tokens_from_chars(response_chars)
    input_rate = float(profile.get("input_per_mtok_usd") or 0.0)
    output_rate = float(profile.get("output_per_mtok_usd") or 0.0)
    cost = (input_tokens / 1_000_000.0 * input_rate) + (output_tokens / 1_000_000.0 * output_rate)
    return {
        "remote": True,
        "provider_kind": profile.get("provider_kind") or dispatch.get("provider_kind") or "remote",
        "estimated_input_tokens": input_tokens,
        "estimated_output_tokens": output_tokens,
        "estimated_cost_usd": round(cost, 8),
    }


def record_remote_cost(session: dict[str, Any], estimate: dict[str, Any]) -> None:
    if not estimate.get("remote"):
        return
    costs = session.setdefault("costs", {})
    costs["remote_turns"] = int(costs.get("remote_turns") or 0) + 1
    costs["remote_input_tokens"] = int(costs.get("remote_input_tokens") or 0) + int(estimate.get("estimated_input_tokens") or 0)
    costs["remote_output_tokens"] = int(costs.get("remote_output_tokens") or 0) + int(estimate.get("estimated_output_tokens") or 0)
    costs["remote_estimated_usd"] = round(
        float(costs.get("remote_estimated_usd") or 0.0) + float(estimate.get("estimated_cost_usd") or 0.0),
        8,
    )


def text_sha256(text: str) -> str:
    return hashlib.sha256(str(text or "").encode("utf-8", errors="replace")).hexdigest()


def audit_event(config: Config, session: dict[str, Any], event_type: str, **fields: Any) -> None:
    row = {
        "created_at": utc_now(),
        "event_type": event_type,
        "session_id": session.get("id", ""),
        "cwd": str(workspace_path(config, session)),
        **fields,
    }
    try:
        path = audit_log_path(config)
        with path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    except OSError:
        # Audit is evidence, not a control-plane dependency. A locked or
        # unwritable audit path must not block chat, routing, or command output.
        return


def read_recent_audit(config: Config, limit: int = 20) -> list[dict[str, Any]]:
    try:
        path = audit_log_path(config)
    except OSError:
        return []
    if not path.exists():
        return []
    rows = []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    for line in lines:
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows[-max(1, limit):]


def load_json(path: pathlib.Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def find_session(config: Config, value: str) -> pathlib.Path:
    candidate = pathlib.Path(value)
    if candidate.exists():
        return candidate

    session_dir = ensure_session_dir(config)
    matches = sorted(session_dir.glob(f"{safe_filename(value)}*.json"))
    if not matches:
        raise FileNotFoundError(f"no session matching {value!r}")
    if len(matches) > 1:
        names = ", ".join(path.stem for path in matches[:5])
        raise RuntimeError(f"ambiguous session prefix {value!r}: {names}")
    return matches[0]


def list_sessions(config: Config, limit: int = 12) -> list[dict[str, str]]:
    session_dir = ensure_session_dir(config)
    rows = []
    paths = sorted(session_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    for path in paths:
        try:
            data = load_json(path)
        except Exception:
            continue
        first_user = ""
        for message in data.get("messages", []):
            if message.get("role") == "user":
                first_user = str(message.get("content", "")).replace("\n", " ")[:80]
                break
        rows.append(
            {
                "id": str(data.get("id", path.stem)),
                "updated_at": str(data.get("updated_at", "")),
                "model": str(data.get("model", "")),
                "first_user": first_user,
            }
        )
        if len(rows) >= limit:
            break
    return rows


def endpoint(base_url: str, path: str) -> str:
    return base_url.rstrip("/") + "/" + path.lstrip("/")


def auth_headers(api_key: str) -> dict[str, str]:
    if not api_key:
        return {}
    return {"Authorization": f"Bearer {api_key}"}


def post_json(
    url: str,
    payload: dict[str, Any],
    timeout: int,
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json", **(headers or {})},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as res:
            return json.loads(res.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"could not reach {url}: {exc.reason}") from exc


def get_json(
    url: str,
    timeout: int,
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    req = urllib.request.Request(url, headers=headers or {}, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as res:
            return json.loads(res.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"could not reach {url}: {exc.reason}") from exc


def build_api_messages(config: Config, session: dict[str, Any]) -> list[dict[str, str]]:
    messages = [{"role": "system", "content": str(session.get("system") or DEFAULT_SYSTEM_PROMPT)}]
    messages.append(
        {
            "role": "system",
            "content": runtime_context(config, session),
        }
    )
    messages.append({"role": "system", "content": evidence_state_context(session, limit=5)})
    if session.get("_force_answer_override"):
        messages.append(
            {
                "role": "system",
                "content": "NODECHAT_FORCE_ANSWER_OVERRIDE\nThe operator explicitly bypassed the answerability gate. Start with a caveat if the answer is not fully supported by loaded evidence.",
            }
        )

    for block in session.get("context_blocks", [])[-5:]:
        content = str(block.get("content") or "").strip()
        if content:
            messages.append({"role": "system", "content": content})

    history = session.get("messages", [])[-config.max_history_messages :]
    for message in history:
        role = message.get("role")
        content = str(message.get("content") or "")
        if role in {"user", "assistant"} and content:
            messages.append({"role": role, "content": content})
    return messages


def provider_kind_for_session(config: Config, session: dict[str, Any]) -> str:
    profile = active_model_profile_data(config, session)
    return str((profile or {}).get("provider_kind") or "openai-compatible").lower()


def anthropic_headers(config: Config, session: dict[str, Any]) -> dict[str, str]:
    profile = active_model_profile_data(config, session)
    key = profile_api_key(profile)
    if not key:
        return {}
    return {
        "x-api-key": key,
        "anthropic-version": ANTHROPIC_API_VERSION,
    }


def anthropic_payload_from_messages(
    model: str,
    messages: list[dict[str, str]],
    temperature: float,
    max_tokens: int,
    stream: bool,
) -> dict[str, Any]:
    system_parts: list[str] = []
    chat_messages: list[dict[str, str]] = []
    for message in messages:
        role = message.get("role")
        content = str(message.get("content") or "")
        if not content:
            continue
        if role == "system":
            system_parts.append(content)
            continue
        if role not in {"user", "assistant"}:
            continue
        if chat_messages and chat_messages[-1]["role"] == role:
            chat_messages[-1]["content"] += "\n\n" + content
        else:
            chat_messages.append({"role": role, "content": content})
    if not chat_messages or chat_messages[0]["role"] != "user":
        chat_messages.insert(0, {"role": "user", "content": "Continue."})
    payload: dict[str, Any] = {
        "model": model,
        "messages": chat_messages,
        "max_tokens": max_tokens if max_tokens > 0 else ANTHROPIC_DEFAULT_MAX_TOKENS,
        "temperature": temperature,
        "stream": stream,
    }
    if system_parts:
        payload["system"] = "\n\n".join(system_parts)
    return payload


def stream_chat(config: Config, session: dict[str, Any]) -> str:
    if provider_kind_for_session(config, session) == "anthropic":
        return stream_anthropic_chat(config, session)
    return stream_openai_chat(config, session)


def stream_openai_chat(config: Config, session: dict[str, Any]) -> str:
    payload = {
        "model": session.get("model") or config.model,
        "messages": build_api_messages(config, session),
        "temperature": config.temperature,
        "stream": True,
    }
    if config.max_tokens > 0:
        payload["max_tokens"] = config.max_tokens

    url = endpoint(str(session.get("base_url") or config.base_url), "chat/completions")
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", **model_auth_headers(config, session)},
        method="POST",
    )

    parts: list[str] = []
    try:
        with urllib.request.urlopen(req, timeout=config.timeout) as res:
            for raw_line in res:
                line = raw_line.decode("utf-8", errors="replace").strip()
                if not line or line.startswith(":"):
                    continue
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                try:
                    obj = json.loads(data)
                except json.JSONDecodeError:
                    continue
                choices = obj.get("choices") or []
                if not choices:
                    continue
                delta = choices[0].get("delta") or {}
                token = delta.get("content") or ""
                if token:
                    print(token, end="", flush=True)
                    parts.append(token)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"could not reach chat endpoint: {exc.reason}") from exc

    print()
    return "".join(parts).strip()


def stream_anthropic_chat(config: Config, session: dict[str, Any]) -> str:
    messages = build_api_messages(config, session)
    payload = anthropic_payload_from_messages(
        str(session.get("model") or config.model),
        messages,
        config.temperature,
        config.max_tokens,
        True,
    )
    url = endpoint(str(session.get("base_url") or config.base_url), "messages")
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", **anthropic_headers(config, session)},
        method="POST",
    )
    parts: list[str] = []
    try:
        with urllib.request.urlopen(req, timeout=config.timeout) as res:
            for raw_line in res:
                line = raw_line.decode("utf-8", errors="replace").strip()
                if not line or not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                try:
                    obj = json.loads(data)
                except json.JSONDecodeError:
                    continue
                if obj.get("type") == "content_block_delta":
                    delta = obj.get("delta") or {}
                    token = delta.get("text") or ""
                    if token:
                        print(token, end="", flush=True)
                        parts.append(token)
                if obj.get("type") == "message_stop":
                    break
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"could not reach chat endpoint: {exc.reason}") from exc
    print()
    return "".join(parts).strip()


def complete_chat(config: Config, session: dict[str, Any]) -> str:
    if provider_kind_for_session(config, session) == "anthropic":
        return complete_anthropic_chat(config, session)
    return complete_openai_chat(config, session)


def complete_openai_chat(config: Config, session: dict[str, Any]) -> str:
    payload = {
        "model": session.get("model") or config.model,
        "messages": build_api_messages(config, session),
        "temperature": config.temperature,
        "stream": False,
    }
    if config.max_tokens > 0:
        payload["max_tokens"] = config.max_tokens

    data = post_json(
        endpoint(str(session.get("base_url") or config.base_url), "chat/completions"),
        payload,
        config.timeout,
        model_auth_headers(config, session),
    )
    choices = data.get("choices") or []
    if not choices:
        raise RuntimeError(f"no choices returned: {data}")
    message = choices[0].get("message") or {}
    content = str(message.get("content") or "").strip()
    print(content)
    return content


def complete_anthropic_chat(config: Config, session: dict[str, Any]) -> str:
    payload = anthropic_payload_from_messages(
        str(session.get("model") or config.model),
        build_api_messages(config, session),
        config.temperature,
        config.max_tokens,
        False,
    )
    data = post_json(
        endpoint(str(session.get("base_url") or config.base_url), "messages"),
        payload,
        config.timeout,
        anthropic_headers(config, session),
    )
    content_parts = []
    for part in data.get("content") or []:
        if isinstance(part, dict) and part.get("type") == "text":
            content_parts.append(str(part.get("text") or ""))
    content = "".join(content_parts).strip()
    if not content:
        raise RuntimeError(f"no text returned: {data}")
    print(content)
    return content


def history_headers(config: Config) -> dict[str, str]:
    token = config.history_token
    if not token:
        return {}
    return {"Authorization": f"Bearer {token}"}


def fetch_history_context(config: Config, query: str, force: bool = True) -> str:
    payload = {
        "query": query,
        "limit": config.history_limit,
        "force": force,
    }
    data = post_json(
        endpoint(config.history_url, "prompt"),
        payload,
        config.timeout,
        history_headers(config),
    )
    prompt = str(data.get("prompt") or "").strip()
    if not prompt:
        prompt = json.dumps(data, indent=2, ensure_ascii=False)
    return prompt


def runtime_context(config: Config, session: dict[str, Any]) -> str:
    history_mode = session.get("history_mode", DEFAULT_HISTORY_MODE)
    repo_mode = session.get("repo_mode", DEFAULT_REPO_MODE)
    web_mode = session.get("web_mode", DEFAULT_WEB_MODE)
    live_mode = session.get("live_mode", DEFAULT_LIVE_MODE)
    model_mode = session.get("model_mode", DEFAULT_MODEL_MODE)
    live_target = config.live_ssh or "local"
    profile = active_model_profile(config, session) or "literal"
    return "\n".join(
        [
            "NODECHAT_RUNTIME",
            f"profile: {profile}",
            f"model: {session.get('model') or config.model}",
            f"endpoint: {session.get('base_url') or config.base_url}",
            "interface: scripts/nodechat.py terminal client",
            f"workspace: {session.get('cwd') or config.workspace}",
            "tool_access: auto-routed AI History, repo files, web context, and live node status when prompt indicates; explicit read-only local context; explicit web fetch/search; explicit live checks; read-only /cmd; and selected /approve command output",
            "no_access: no arbitrary shell, no freeform file writes (only /apply --confirm)",
            f"history_mode: {history_mode}",
            f"repo_mode: {repo_mode}",
            f"web_mode: {web_mode}",
            f"live_mode: {live_mode}",
            f"model_mode: {model_mode}",
            f"remote_models_enabled: {str(remote_models_enabled(session)).lower()}",
            f"live_target: {live_target}",
        ]
    )


def tool_messages(
    config: Config,
    session: dict[str, Any],
    prompt: str,
) -> list[dict[str, str]]:
    messages = [{"role": "system", "content": str(session.get("system") or DEFAULT_SYSTEM_PROMPT)}]
    messages.append({"role": "system", "content": runtime_context(config, session)})
    messages.append({"role": "system", "content": evidence_state_context(session, limit=3)})
    if session.get("_force_answer_override"):
        messages.append(
            {
                "role": "system",
                "content": "NODECHAT_FORCE_ANSWER_OVERRIDE\nThe operator explicitly bypassed the answerability gate. Start with a caveat if the answer is not fully supported by loaded evidence.",
            }
        )
    for block in session.get("context_blocks", [])[-3:]:
        content = str(block.get("content") or "").strip()
        if content:
            messages.append({"role": "system", "content": content})
    messages.append({"role": "user", "content": prompt})
    return messages


def complete_tool_prompt(
    config: Config,
    session: dict[str, Any],
    prompt: str,
    max_tokens: int = MAX_PROPOSAL_TOKENS,
) -> str:
    profile = active_model_profile_data(config, session)
    if profile_is_remote(profile) and not remote_models_enabled(session):
        name = active_model_profile(config, session) or "remote"
        raise RuntimeError(f"remote profile '{name}' disabled: run /remote-models enable")
    if provider_kind_for_session(config, session) == "anthropic":
        payload = anthropic_payload_from_messages(
            str(session.get("model") or config.model),
            tool_messages(config, session, prompt),
            0.1,
            max_tokens,
            False,
        )
        data = post_json(
            endpoint(str(session.get("base_url") or config.base_url), "messages"),
            payload,
            config.timeout,
            anthropic_headers(config, session),
        )
        return "".join(
            str(part.get("text") or "")
            for part in data.get("content") or []
            if isinstance(part, dict) and part.get("type") == "text"
        ).strip()

    payload = {
        "model": session.get("model") or config.model,
        "messages": tool_messages(config, session, prompt),
        "temperature": 0.1,
        "stream": False,
        "max_tokens": max_tokens,
    }
    data = post_json(
        endpoint(str(session.get("base_url") or config.base_url), "chat/completions"),
        payload,
        config.timeout,
        model_auth_headers(config, session),
    )
    choices = data.get("choices") or []
    if not choices:
        raise RuntimeError(f"no choices returned: {data}")
    message = choices[0].get("message") or {}
    return str(message.get("content") or "").strip()


def context_block(kind: str, title: str, content: str) -> str:
    body = content.strip()
    if len(body) > MAX_CONTEXT_CHARS:
        body = body[:MAX_CONTEXT_CHARS] + "\n...[truncated for nodechat context cap]"
    return "\n".join(
        [
            "NODECHAT_TOOL_CONTEXT",
            f"kind: {kind}",
            f"title: {title}",
            "Use this only as explicitly supplied context for the current conversation.",
            "",
            body,
        ]
    ).strip()


def add_context(
    session: dict[str, Any],
    query: str,
    content: str,
    *,
    source: str = "manual-legacy",
    provenance: dict[str, Any] | None = None,
) -> None:
    session.setdefault("context_blocks", []).append(
        {
            "created_at": utc_now(),
            "query": query,
            "content": content,
            "source": source,
            "provenance": provenance or {},
        }
    )


def detect_history_query(prompt: str) -> str | None:
    """Return the prompt to use as a history query if any auto pattern matches.

    Tight patterns route on a match alone (their phrasing already binds them
    to the project, e.g. "what did we ..."). Broad patterns ("remind me",
    "previously", "history of", "have we ever ...", "has X ever ...",
    "what was our reasoning ...") additionally require the prompt to contain
    a HISTORY_PROJECT_CONTEXT_RE token; that filters out personal reminders
    and general-knowledge questions that share the same lead phrase.
    """
    if not prompt or not prompt.strip():
        return None
    text = prompt
    for pattern in HISTORY_TIGHT_PATTERNS:
        if pattern.search(text):
            return text.strip()
    if HISTORY_PROJECT_CONTEXT_RE.search(text):
        for pattern in HISTORY_BROAD_PATTERNS:
            if pattern.search(text):
                return text.strip()
    return None


def detect_repo_targets(
    config: Config,
    session: dict[str, Any],
    prompt: str,
) -> list[pathlib.Path]:
    """Return safe, distinct workspace paths to auto-read for this prompt.

    Day-one matches: explicit named files (CURRENT_STATE / SESSION_LOG /
    CLAUDE.md / SCRATCH.md / ATTITUDE.md), known runbook stems, and
    path-like tokens (docs/x, scripts/x, ...). High-confidence project summary
    requests route the two authoritative overview docs. Bare filenames and
    vague topic phrases do not auto-route.
    """
    if not prompt or not prompt.strip():
        return []
    candidates: list[str] = []

    for pattern, rel in REPO_NAMED_FILE_PATTERNS:
        if pattern.search(prompt):
            candidates.append(rel)

    if (
        REPO_SUMMARY_SUBJECT_RE.search(prompt)
        and REPO_SUMMARY_INTENT_RE.search(prompt)
    ):
        candidates.extend(REPO_SUMMARY_DOCS)

    for match in REPO_RUNBOOK_RE.finditer(prompt):
        candidates.append(f"docs/runbooks/{match.group(1).lower()}.md")

    for match in REPO_PATH_RE.finditer(prompt):
        candidates.append(match.group(0).replace("\\", "/"))

    out: list[pathlib.Path] = []
    seen: set[str] = set()
    for raw in candidates:
        path = resolve_workspace_path(config, session, raw)
        key = os.path.normcase(str(path))
        if key in seen:
            continue
        seen.add(key)
        if path_safety_reason(config, session, path):
            continue
        if not path.exists() or not path.is_file():
            continue
        if not is_text_candidate(path):
            continue
        out.append(path)
        if len(out) >= REPO_AUTO_LIMIT:
            break
    return out


def detect_web_targets(prompt: str) -> dict[str, Any] | None:
    """Return auto-web targets for prompts needing fresh public context.

    Direct URLs route to fetch. Non-URL prompts route to search only when they
    carry both a fresh/current-data signal and a public-object signal, or when
    the user explicitly asks to search/browse/check online for a public object.
    Local-only status phrasing is intentionally skipped unless the prompt also
    has an explicit web/search signal.
    """
    if not prompt or not prompt.strip():
        return None
    text = prompt.strip()
    urls = []
    for match in WEB_URL_RE.finditer(text):
        url = match.group(0).rstrip(".,;:")
        if url not in urls:
            urls.append(url)
        if len(urls) >= WEB_AUTO_URL_LIMIT:
            break
    if urls:
        return {"urls": urls, "query": None}

    explicit = bool(WEB_EXPLICIT_RE.search(text))
    fresh = bool(WEB_FRESH_RE.search(text))
    public_object = bool(WEB_PUBLIC_OBJECT_RE.search(text))
    local_only = bool(WEB_LOCAL_ONLY_RE.search(text))

    if public_object and explicit:
        return {"urls": [], "query": text}
    if public_object and fresh and not local_only:
        return {"urls": [], "query": text}
    if public_object and fresh and re.search(r"\b(release|version|changelog|pricing|price|cost|cve|vulnerability|advisory|availability|stock)\b", text, re.I):
        return {"urls": [], "query": text}
    # Explicit "search for X / look up X" with a freshness signal but no
    # public-object hit (e.g. proprietary part numbers like SF-1600F14HT).
    # Local context still wins -- "search for our local docs" stays put.
    if explicit and fresh and not local_only:
        return {"urls": [], "query": text}
    return None


def detect_live_targets(prompt: str) -> list[str]:
    """Return read-only live checks to auto-run for clear live-status prompts.

    A prompt with a public destination ("on github", "online") or an explicit
    web-search signal ("look up", "verify online") and no local hint is treated
    as a web-routing prompt, not a live-status prompt, even if it shares an
    object word like "vllm" or "ollama" with the live router.
    """
    if not prompt or not prompt.strip():
        return []
    text = prompt.strip()
    lowered = text.lower()
    if (
        REPO_SUMMARY_NONLIVE_SUBJECT_RE.search(text)
        and REPO_SUMMARY_INTENT_RE.search(text)
    ):
        return []
    if not LIVE_TRIGGER_RE.search(text) or not LIVE_OBJECT_RE.search(text):
        return []
    if (LIVE_PUBLIC_DEST_RE.search(text) or WEB_EXPLICIT_RE.search(text)) and \
            not LIVE_LOCAL_HINT_RE.search(text):
        return []

    checks: list[str] = []

    def add(name: str) -> None:
        if name not in checks:
            checks.append(name)

    # Explicit health words always route to a health check.
    if re.search(r"\b(health|healthy|healthcheck)\b", text, re.I):
        add("health")
    if re.search(r"\b(gpu|nvidia|temperature|temp|temps|power draw|utilization|utilisation|vram)\b", text, re.I):
        add("gpu")
    if re.search(r"\b(power cap|power limit)\b", text, re.I):
        add("power")
    if re.search(r"\b(docker|container|containers|open webui|webui)\b", text, re.I):
        add("docker")
    if "vllm" in lowered:
        add("vllm")
    if "ollama" in lowered:
        add("ollama")
    if re.search(r"\b(disk|storage|filesystem|df|free space|space)\b", text, re.I):
        add("storage")
    if re.search(r"\b(bmc|ipmi)\b", text, re.I):
        add("bmc")
    if re.search(r"\b(ups)\b", text, re.I):
        add("ups")

    # Project-context fallback: if no specific check fired, a project-context
    # token like "stack" / "nodehome" / "homelab" / "the node" stands in for
    # a "give me a quick health overview" intent. This is the non-explicit
    # cousin of the explicit health trigger above and intentionally does not
    # fire when a more specific check has already routed.
    if not checks and re.search(r"\b(stack|nodehome|homelab|the node)\b", text, re.I):
        add("health")

    if not checks and re.search(r"\b(running|up|down|service|services)\b", text, re.I):
        add("docker")
    return checks[:LIVE_AUTO_LIMIT]


def _short_error(exc: Exception) -> str:
    msg = str(exc).strip().splitlines()[0] if str(exc).strip() else exc.__class__.__name__
    return msg[:60] + "..." if len(msg) > 60 else msg


def _trunc(text: str, n: int) -> str:
    text = text.strip()
    if len(text) <= n:
        return text
    return text[: n - 1] + "..."


def auto_route_turn(
    config: Config,
    session: dict[str, Any],
    prompt: str,
) -> str | None:
    """Auto-route AI History and repo file context for a chat turn.

    Returns a one-line disclosure string if anything was routed (including
    skips/errors), or None if nothing fired. Never raises; routing failures
    are logged to audit and reported in the disclosure line so the chat
    turn always proceeds.
    """
    parts: list[str] = []

    history_mode = session.get("history_mode", DEFAULT_HISTORY_MODE)
    if history_mode == "auto":
        query = detect_history_query(prompt)
        if query:
            try:
                content = fetch_history_context(config, query, force=True)
            except Exception as exc:
                audit_event(
                    config,
                    session,
                    "auto_route_history",
                    status="error",
                    query=query,
                    reason=_short_error(exc),
                )
                parts.append(f"history(error: {_short_error(exc)})")
            else:
                size = len(content)
                add_context(
                    session,
                    f"auto:/history {query}",
                    context_block("history_context", query, content),
                    source="auto-history",
                    provenance={"query": query, "chars": size},
                )
                audit_event(
                    config,
                    session,
                    "auto_route_history",
                    status="ok",
                    query=query,
                    chars=size,
                )
                parts.append(f'history({size} chars, "{_trunc(query, 48)}")')

    repo_mode = session.get("repo_mode", DEFAULT_REPO_MODE)
    if repo_mode == "auto":
        targets = detect_repo_targets(config, session, prompt)
        if targets:
            files_added: list[str] = []
            for path in targets:
                try:
                    text, truncated = read_text_path(path)
                except Exception as exc:
                    audit_event(
                        config,
                        session,
                        "auto_route_repo",
                        status="error",
                        path=str(path),
                        reason=_short_error(exc),
                    )
                    continue
                content = format_file_read(path, text, truncated)
                rel = display_path(config, session, path)
                add_context(
                    session,
                    f"auto:/read {rel}",
                    context_block("file_read", str(path), content),
                    source="auto-repo",
                    provenance={
                        "path": str(path),
                        "rel": rel,
                        "chars": len(text),
                        "truncated": truncated,
                    },
                )
                audit_event(
                    config,
                    session,
                    "auto_route_repo",
                    status="ok",
                    path=str(path),
                    chars=len(text),
                    truncated=truncated,
                )
                files_added.append(rel)
            if files_added:
                parts.append(f"repo(read {', '.join(files_added)})")

    web_mode = session.get("web_mode", DEFAULT_WEB_MODE)
    if web_mode == "auto":
        targets = detect_web_targets(prompt)
        if targets:
            timeout = max(1, min(int(config.timeout), WEB_AUTO_TIMEOUT))
            fetched: list[str] = []
            for url in targets.get("urls") or []:
                try:
                    content, content_type, truncated, text_chars = web_fetch_context(url, timeout)
                except Exception as exc:
                    audit_event(
                        config,
                        session,
                        "auto_route_web",
                        status="error",
                        action="fetch",
                        url=url,
                        reason=_short_error(exc),
                    )
                    parts.append(f"web(fetch error: {_short_error(exc)})")
                    continue
                add_context(
                    session,
                    f"auto:/web-fetch {url}",
                    context_block("web_fetch", url, content),
                    source="auto-web-fetch",
                    provenance={
                        "url": url,
                        "content_type": content_type or "",
                        "truncated": truncated,
                        "chars": text_chars,
                    },
                )
                audit_event(
                    config,
                    session,
                    "auto_route_web",
                    status="ok",
                    action="fetch",
                    url=url,
                    chars=text_chars,
                    truncated=truncated,
                )
                fetched.append(_trunc(url, 48))
            if fetched:
                parts.append(f"web(fetch {', '.join(fetched)})")

            query = targets.get("query")
            if query:
                try:
                    content, result_count = web_search_context(str(query), timeout)
                except Exception as exc:
                    audit_event(
                        config,
                        session,
                        "auto_route_web",
                        status="error",
                        action="search",
                        query=str(query),
                        reason=_short_error(exc),
                    )
                    parts.append(f"web(search error: {_short_error(exc)})")
                else:
                    add_context(
                        session,
                        f"auto:/web-search {query}",
                        context_block("web_search", str(query), content),
                        source="auto-web-search",
                        provenance={
                            "query": str(query),
                            "results": result_count,
                            "chars": len(content),
                        },
                    )
                    audit_event(
                        config,
                        session,
                        "auto_route_web",
                        status="ok",
                        action="search",
                        query=str(query),
                        results=result_count,
                        chars=len(content),
                    )
                    parts.append(f'web(search {result_count} results, "{_trunc(str(query), 48)}")')

    live_mode = session.get("live_mode", DEFAULT_LIVE_MODE)
    if live_mode == "auto":
        checks = detect_live_targets(prompt)
        if checks:
            results = run_live_checks(config, checks)
            block = live_context_block(results)
            add_context(
                session,
                f"auto:/live {','.join(checks)}",
                context_block("live_status", ",".join(checks), block),
                source="auto-live",
                provenance={
                    "checks": checks,
                    "target": config.live_ssh or "local",
                    "exit_codes": [row.get("exit_code") for row in results],
                    "chars": len(block),
                },
            )
            audit_event(
                config,
                session,
                "auto_route_live",
                status="ok",
                checks=checks,
                target=config.live_ssh or "local",
                exit_codes=[row.get("exit_code") for row in results],
                **output_digest(block),
            )
            parts.append(f"live({', '.join(checks)})")

    if not parts:
        return None
    return "[auto-routed: " + " | ".join(parts) + "]"


def workspace_path(config: Config, session: dict[str, Any]) -> pathlib.Path:
    return pathlib.Path(str(session.get("cwd") or config.workspace)).resolve()


def resolve_workspace_path(config: Config, session: dict[str, Any], raw: str = "") -> pathlib.Path:
    base = workspace_path(config, session)
    value = raw.strip() if raw else "."
    path = pathlib.Path(value)
    if not path.is_absolute():
        path = base / path
    return path.resolve()


def path_inside_workspace(config: Config, session: dict[str, Any], path: pathlib.Path) -> bool:
    base = os.path.normcase(os.path.abspath(str(workspace_path(config, session))))
    target = os.path.normcase(os.path.abspath(str(path.resolve())))
    try:
        return os.path.commonpath([base, target]) == base
    except ValueError:
        return False


def workspace_confine_reason(config: Config, session: dict[str, Any], path: pathlib.Path) -> str | None:
    if path_inside_workspace(config, session, path):
        return None
    return f"path outside nodechat workspace: {path}"


def path_safety_reason(config: Config, session: dict[str, Any], path: pathlib.Path) -> str | None:
    return workspace_confine_reason(config, session, path) or blocked_path_reason(path)


def display_path(config: Config, session: dict[str, Any], path: pathlib.Path) -> str:
    try:
        return path.relative_to(workspace_path(config, session)).as_posix()
    except ValueError:
        return str(path)


def blocked_path_reason(path: pathlib.Path) -> str | None:
    parts = {part.lower() for part in path.parts}
    blocked_parts = sorted(parts.intersection(BLOCKED_PATH_PARTS))
    if blocked_parts:
        return f"blocked private/generated path component: {blocked_parts[0]}"

    name = path.name.lower()
    if path.suffix.lower() in BLOCKED_FILE_EXTENSIONS:
        return f"blocked file type: {path.suffix.lower()}"
    safe_example = name.endswith((".env.example", ".env.sample", ".env.template"))
    if not safe_example and any(pattern in name for pattern in SECRET_NAME_PATTERNS):
        return "blocked likely secret/token file"
    return None


def is_text_candidate(path: pathlib.Path) -> bool:
    return path.suffix.lower() in TEXT_EXTENSIONS


def read_text_path(path: pathlib.Path, max_bytes: int = MAX_READ_BYTES) -> tuple[str, bool]:
    with path.open("rb") as handle:
        data = handle.read(max_bytes + 1)
    truncated = len(data) > max_bytes
    if truncated:
        data = data[:max_bytes]
    return data.decode("utf-8", errors="replace"), truncated


def format_file_read(path: pathlib.Path, text: str, truncated: bool) -> str:
    header = [
        f"path: {path}",
        f"bytes_read: {len(text.encode('utf-8', errors='replace'))}",
        f"truncated: {str(truncated).lower()}",
        "",
        "content:",
    ]
    return "\n".join(header + [text])


def command_pwd(config: Config, session: dict[str, Any]) -> None:
    print(str(workspace_path(config, session)))


def command_tree(config: Config, session: dict[str, Any], arg: str) -> None:
    root = resolve_workspace_path(config, session, arg)
    reason = path_safety_reason(config, session, root)
    if reason:
        print(f"tree refused: {reason}")
        return
    if not root.exists():
        print(f"tree failed: path does not exist: {root}")
        return
    if root.is_file():
        root = root.parent

    lines = [f"tree root: {root}", f"max_entries: {MAX_TREE_ENTRIES}", ""]
    count = 0
    for current, dirs, files in os.walk(root):
        current_path = pathlib.Path(current)
        rel = current_path.relative_to(root)
        depth = 0 if str(rel) == "." else len(rel.parts)
        if depth >= 2:
            dirs[:] = []
        dirs[:] = [
            d
            for d in sorted(dirs)
            if not (current_path / d).is_symlink()
            and path_safety_reason(config, session, current_path / d) is None
        ]
        files = [
            f
            for f in sorted(files)
            if not (current_path / f).is_symlink()
            and path_safety_reason(config, session, current_path / f) is None
        ]

        indent = "  " * depth
        label = "." if str(rel) == "." else rel.name
        lines.append(f"{indent}{label}/")
        count += 1
        if count >= MAX_TREE_ENTRIES:
            lines.append("...[truncated: entry cap reached]")
            break

        for filename in files:
            lines.append(f"{indent}  {filename}")
            count += 1
            if count >= MAX_TREE_ENTRIES:
                lines.append("...[truncated: entry cap reached]")
                break
        if count >= MAX_TREE_ENTRIES:
            break

    content = "\n".join(lines)
    add_context(
        session,
        f"/tree {arg}".strip(),
        context_block("tree", str(root), content),
        source="manual-tree",
        provenance={"command": "/tree", "root": str(root), "entries": count},
    )
    print(f"tree context added: {root} ({count} entries)")


def command_read(config: Config, session: dict[str, Any], arg: str) -> None:
    if not arg:
        print("usage: /read <path>")
        return
    path = resolve_workspace_path(config, session, arg)
    reason = path_safety_reason(config, session, path)
    if reason:
        print(f"read refused: {reason}")
        return
    if not path.exists():
        print(f"read failed: path does not exist: {path}")
        return
    if not path.is_file():
        print(f"read failed: not a file: {path}")
        return
    if not is_text_candidate(path):
        print(f"read refused: extension is not in text allow-list: {path.suffix or '[none]'}")
        return
    try:
        text, truncated = read_text_path(path)
    except Exception as exc:
        print(f"read failed: {exc}")
        return
    content = format_file_read(path, text, truncated)
    add_context(
        session,
        f"/read {arg}",
        context_block("file_read", str(path), content),
        source="manual-read",
        provenance={"command": "/read", "path": str(path), "chars": len(text), "truncated": truncated},
    )
    suffix = " (truncated)" if truncated else ""
    print(f"file context added: {path}{suffix}")


def search_text_files(config: Config, session: dict[str, Any], root: pathlib.Path, query: str) -> list[str]:
    query_l = query.lower()
    rows: list[str] = []
    for current, dirs, files in os.walk(root):
        current_path = pathlib.Path(current)
        dirs[:] = [
            d
            for d in sorted(dirs)
            if not (current_path / d).is_symlink()
            and path_safety_reason(config, session, current_path / d) is None
        ]
        for filename in sorted(files):
            path = current_path / filename
            if path.is_symlink() or path_safety_reason(config, session, path) or not is_text_candidate(path):
                continue
            try:
                stat = path.stat()
            except OSError:
                continue
            if stat.st_size > MAX_SEARCH_FILE_BYTES:
                continue
            rel = path.relative_to(root)
            if query_l in filename.lower():
                rows.append(f"{rel}: filename match")
            try:
                text, _ = read_text_path(path, MAX_SEARCH_FILE_BYTES)
            except Exception:
                continue
            for idx, line in enumerate(text.splitlines(), 1):
                if query_l in line.lower():
                    snippet = line.strip()
                    if len(snippet) > 220:
                        snippet = snippet[:220] + "..."
                    rows.append(f"{rel}:{idx}: {snippet}")
                    break
            if len(rows) >= MAX_SEARCH_RESULTS:
                return rows
    return rows


def parse_search_args(arg: str) -> tuple[str, str]:
    try:
        parts = shlex.split(arg)
    except ValueError:
        parts = arg.split()
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], parts[1]


def command_search_files(config: Config, session: dict[str, Any], arg: str) -> None:
    query, raw_root = parse_search_args(arg)
    if not query:
        print('usage: /search-files <query> [path]; quote multi-word queries')
        return
    root = resolve_workspace_path(config, session, raw_root)
    reason = path_safety_reason(config, session, root)
    if reason:
        print(f"search refused: {reason}")
        return
    if not root.exists():
        print(f"search failed: path does not exist: {root}")
        return
    if root.is_file():
        root = root.parent
    rows = search_text_files(config, session, root, query)
    lines = [
        f"query: {query}",
        f"root: {root}",
        f"max_results: {MAX_SEARCH_RESULTS}",
        "",
    ]
    lines.extend(rows or ["No matches found."])
    add_context(
        session,
        f"/search-files {arg}",
        context_block("file_search", query, "\n".join(lines)),
        source="manual-search",
        provenance={"command": "/search-files", "query": query, "root": str(root), "matches": len(rows)},
    )
    print(f"file search context added: {query} ({len(rows)} matches)")


def command_git_status(config: Config, session: dict[str, Any]) -> None:
    root = workspace_path(config, session)
    try:
        result = subprocess.run(
            ["git", "status", "--short", "--branch"],
            cwd=str(root),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=10,
            check=False,
        )
    except Exception as exc:
        print(f"git status failed: {exc}")
        return
    output = result.stdout.strip() or "(clean output)"
    content = "\n".join([f"cwd: {root}", f"exit_code: {result.returncode}", "", output])
    add_context(
        session,
        "/git-status",
        context_block("git_status", str(root), content),
        source="manual-git-status",
        provenance={"command": "/git-status", "root": str(root), "exit_code": result.returncode},
    )
    print(output)
    print("git status context added")


class TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.skip = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "svg", "noscript"}:
            self.skip += 1
        if tag in {"p", "div", "br", "li", "h1", "h2", "h3", "tr"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "svg", "noscript"} and self.skip:
            self.skip -= 1
        if tag in {"p", "div", "li", "h1", "h2", "h3", "tr"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self.skip:
            value = data.strip()
            if value:
                self.parts.append(value)
                self.parts.append(" ")

    def text(self) -> str:
        raw = html.unescape("".join(self.parts))
        lines = [re.sub(r"\s+", " ", line).strip() for line in raw.splitlines()]
        return "\n".join(line for line in lines if line)


class LinkExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_link = False
        self.current_href = ""
        self.current_text: list[str] = []
        self.links: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        attrs_dict = {key: value or "" for key, value in attrs}
        href = attrs_dict.get("href", "")
        if not href:
            return
        self.in_link = True
        self.current_href = href
        self.current_text = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self.in_link:
            title = html.unescape(" ".join(self.current_text)).strip()
            if title and self.current_href:
                self.links.append((title, self.current_href))
            self.in_link = False
            self.current_href = ""
            self.current_text = []

    def handle_data(self, data: str) -> None:
        if self.in_link:
            value = data.strip()
            if value:
                self.current_text.append(value)


def fetch_raw_url(url: str, timeout: int, max_bytes: int = MAX_WEB_BYTES) -> tuple[str, str, bool]:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise RuntimeError("only http/https URLs are supported")
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "nodechat/0.2 (+https://nodehome.local)"},
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=timeout) as res:
        content_type = res.headers.get("Content-Type", "")
        data = res.read(max_bytes + 1)
    truncated = len(data) > max_bytes
    if truncated:
        data = data[:max_bytes]
    text = data.decode("utf-8", errors="replace")
    return content_type, text, truncated


def fetch_url(url: str, timeout: int, max_bytes: int = MAX_WEB_BYTES) -> tuple[str, str, bool]:
    content_type, text, truncated = fetch_raw_url(url, timeout, max_bytes)
    if "html" in content_type.lower() or "<html" in text[:500].lower():
        parser = TextExtractor()
        parser.feed(text)
        text = parser.text()
    return content_type, text, truncated


def web_fetch_context(url: str, timeout: int) -> tuple[str, str, bool, int]:
    content_type, text, truncated = fetch_url(url, timeout)
    lines = [
        f"url: {url}",
        f"content_type: {content_type or '[unknown]'}",
        f"truncated: {str(truncated).lower()}",
        "",
        text,
    ]
    return "\n".join(lines), content_type, truncated, len(text)


def command_web_fetch(config: Config, session: dict[str, Any], arg: str) -> None:
    url = arg.strip()
    if not url:
        print("usage: /web-fetch <url>")
        return
    try:
        content, content_type, truncated, text_chars = web_fetch_context(url, config.timeout)
    except Exception as exc:
        print(f"web fetch failed: {exc}")
        return
    add_context(
        session,
        f"/web-fetch {url}",
        context_block("web_fetch", url, content),
        source="manual-web-fetch",
        provenance={
            "command": "/web-fetch",
            "url": url,
            "content_type": content_type or "",
            "truncated": truncated,
            "chars": text_chars,
        },
    )
    suffix = " (truncated)" if truncated else ""
    print(f"web context added: {url}{suffix}")


def normalize_search_url(href: str) -> str:
    if href.startswith("//"):
        href = "https:" + href
    parsed = urllib.parse.urlparse(href)
    if "duckduckgo.com" in parsed.netloc and parsed.path.startswith("/l/"):
        query = urllib.parse.parse_qs(parsed.query)
        target = query.get("uddg", [""])[0]
        if target:
            return urllib.parse.unquote(target)
    return href


def web_search_context(query: str, timeout: int) -> tuple[str, int]:
    url = "https://duckduckgo.com/html/?" + urllib.parse.urlencode({"q": query})
    _, body, _ = fetch_raw_url(url, timeout)

    parser = LinkExtractor()
    parser.feed(body)
    rows: list[str] = []
    seen: set[str] = set()
    for title, href in parser.links:
        clean_url = normalize_search_url(href)
        if not clean_url.startswith(("http://", "https://")):
            continue
        if clean_url in seen:
            continue
        seen.add(clean_url)
        rows.append(f"- {title}\n  {clean_url}")
        if len(rows) >= 10:
            break

    lines = [
        f"query: {query}",
        "source: DuckDuckGo HTML search",
        "note: search results are leads, not proof; fetch/open a result for source text.",
        "",
    ]
    lines.extend(rows or ["No parseable search results found."])
    return "\n".join(lines), len(rows)


def command_web_search(config: Config, session: dict[str, Any], arg: str) -> None:
    query = arg.strip()
    if not query:
        print("usage: /web-search <query>")
        return
    try:
        content, result_count = web_search_context(query, config.timeout)
    except Exception as exc:
        print(f"web search failed: {exc}")
        return
    add_context(
        session,
        f"/web-search {query}",
        context_block("web_search", query, content),
        source="manual-web-search",
        provenance={
            "command": "/web-search",
            "query": query,
            "results": result_count,
            "chars": len(content),
        },
    )
    print(f"web search context added: {query} ({result_count} results)")


LIVE_CHECKS: dict[str, dict[str, Any]] = {
    "health": {
        "description": "repo healthcheck.sh summary",
        "local": ["bash", "scripts/healthcheck.sh"],
        "remote": "./scripts/healthcheck.sh",
        "needs_root": True,
    },
    "gpu": {
        "description": "GPU temperature/utilization/VRAM/power snapshot",
        "local": [
            "nvidia-smi",
            "--query-gpu=index,name,temperature.gpu,utilization.gpu,memory.used,memory.total,power.draw,power.limit,pstate",
            "--format=csv",
        ],
        "remote": "nvidia-smi --query-gpu=index,name,temperature.gpu,utilization.gpu,memory.used,memory.total,power.draw,power.limit,pstate --format=csv",
    },
    "power": {
        "description": "GPU0/GPU1 configured power limits",
        "local": [
            "nvidia-smi",
            "-i",
            "0,1",
            "--query-gpu=index,power.limit",
            "--format=csv",
        ],
        "remote": "nvidia-smi -i 0,1 --query-gpu=index,power.limit --format=csv",
    },
    "docker": {
        "description": "Docker container status",
        "local": ["docker", "ps", "--format", "table {{.Names}}\t{{.Status}}\t{{.Ports}}"],
        "remote": "docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'",
    },
    "vllm": {
        "description": "vLLM container state",
        "local": [
            "docker",
            "inspect",
            "vllm-server",
            "--format",
            "status={{.State.Status}} health={{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}} started={{.State.StartedAt}}",
        ],
        "remote": "docker inspect vllm-server --format 'status={{.State.Status}} health={{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}} started={{.State.StartedAt}}'",
    },
    "ollama": {
        "description": "Ollama systemd service status",
        "local": ["systemctl", "status", "ollama", "--no-pager", "--lines=8"],
        "remote": "systemctl status ollama --no-pager --lines=8",
    },
    "storage": {
        "description": "filesystem free space",
        "local": ["df", "-h"],
        "remote": "df -h",
    },
    "bmc": {
        "description": "BMC LAN channel summary",
        "local": ["ipmitool", "lan", "print", "1"],
        "remote": "ipmitool lan print 1",
    },
    "ups": {
        "description": "UPS daemon status if installed",
        "local": ["upsc", "ups"],
        "remote": "upsc ups",
    },
}


def _remote_cd_prefix(path: str) -> str:
    root = (path or "~/nodehome").strip()
    if root == "~/nodehome":
        return "cd ~/nodehome"
    if re.fullmatch(r"~/[A-Za-z0-9_./-]+", root):
        return "cd " + root
    return "cd " + shlex.quote(root)


def _format_argv(parts: list[str]) -> str:
    return " ".join(shlex.quote(part) for part in parts)


# ---------------------------------------------------------------------------
# Live-node operator: extended diagnostics + queueable mutations.
#
# All entries are exact-string keys (after lowercase + whitespace collapse).
# No arbitrary container names, no arbitrary journalctl units, no --follow,
# no shell composition. The runner uses the same SSH / local plumbing as the
# fixed LIVE_CHECKS reads.
# ---------------------------------------------------------------------------

# Read-only diagnostics. Run immediately under /live, no approval.
LIVE_DIAG_OPS: dict[str, dict[str, Any]] = {
    "ps": {
        "description": "All Docker containers (running and stopped)",
        "argv": ["docker", "ps", "-a"],
    },
    "logs vllm": {
        "description": "Last 200 lines of vllm-server container logs",
        "argv": ["docker", "logs", "--tail", "200", "vllm-server"],
    },
    "logs vllm-server": {  # alias
        "description": "Last 200 lines of vllm-server container logs",
        "argv": ["docker", "logs", "--tail", "200", "vllm-server"],
    },
    "logs open-webui": {
        "description": "Last 200 lines of open-webui container logs",
        "argv": ["docker", "logs", "--tail", "200", "open-webui"],
    },
    "logs webui": {  # alias
        "description": "Last 200 lines of open-webui container logs",
        "argv": ["docker", "logs", "--tail", "200", "open-webui"],
    },
    "logs ollama": {  # aliased to journalctl since ollama is systemd-managed
        "description": "Last 200 ollama systemd journal entries (alias of /live journal ollama)",
        "argv": ["journalctl", "-u", "ollama", "--no-pager", "-n", "200"],
    },
    "journal ollama": {
        "description": "Last 200 ollama systemd journal entries",
        "argv": ["journalctl", "-u", "ollama", "--no-pager", "-n", "200"],
    },
    "inspect vllm": {
        "description": "docker inspect vllm-server (full)",
        "argv": ["docker", "inspect", "vllm-server"],
    },
    "inspect vllm-server": {  # alias
        "description": "docker inspect vllm-server (full)",
        "argv": ["docker", "inspect", "vllm-server"],
    },
    "inspect open-webui": {
        "description": "docker inspect open-webui (full)",
        "argv": ["docker", "inspect", "open-webui"],
    },
    "inspect webui": {  # alias
        "description": "docker inspect open-webui (full)",
        "argv": ["docker", "inspect", "open-webui"],
    },
}

# Queueable mutations. Caught by /live but routed to /approve before exec.
LIVE_MUTATION_OPS: dict[str, dict[str, Any]] = {
    "restart vllm-server": {
        "description": "Restart the vllm-server Docker container",
        "argv": ["docker", "restart", "vllm-server"],
        "approval_reason": "approved live-mutation: docker restart vllm-server",
    },
    "restart vllm": {  # alias
        "description": "Restart the vllm-server Docker container",
        "argv": ["docker", "restart", "vllm-server"],
        "approval_reason": "approved live-mutation: docker restart vllm-server",
    },
    "restart open-webui": {
        "description": "Restart the open-webui Docker container",
        "argv": ["docker", "restart", "open-webui"],
        "approval_reason": "approved live-mutation: docker restart open-webui",
    },
    "restart webui": {  # alias
        "description": "Restart the open-webui Docker container",
        "argv": ["docker", "restart", "open-webui"],
        "approval_reason": "approved live-mutation: docker restart open-webui",
    },
    "restart ollama": {
        "description": "Restart the ollama systemd service",
        "argv": ["sudo", "-n", "/bin/systemctl", "restart", "ollama"],
        "approval_reason": "approved live-mutation: sudo -n /bin/systemctl restart ollama",
    },
}


def _live_op_key(arg: str) -> str:
    """Normalize /live op argument: lowercase, collapse internal whitespace."""
    return re.sub(r"\s+", " ", (arg or "").strip().lower())


def _live_argv_for_op(config: Config, local_argv: list[str]) -> tuple[list[str], str]:
    """Wrap argv for SSH if `live_ssh` is set; otherwise return local argv."""
    if config.live_ssh:
        remote = " ".join(shlex.quote(part) for part in local_argv)
        return ["ssh", "-o", "BatchMode=yes", config.live_ssh, remote], "ssh:" + config.live_ssh
    return list(local_argv), "local"


def _run_live_argv(
    config: Config,
    label: str,
    target: str,
    argv: list[str],
) -> dict[str, Any]:
    """Execute argv (already SSH-wrapped if needed) with timeout + capture."""
    display = " ".join(argv) if target.startswith("ssh:") else _format_argv(argv)
    resolved = shutil.which(argv[0])
    if not resolved:
        return {
            "check": label,
            "target": target,
            "command": display,
            "exit_code": 127,
            "executable": "",
            "output": f"executable not found: {argv[0]}",
        }
    run_argv = [resolved, *argv[1:]]
    try:
        result = subprocess.run(
            run_argv,
            cwd=str(pathlib.Path.cwd() if config.live_ssh else config.workspace),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=config.cmd_timeout,
            check=False,
        )
        return {
            "check": label,
            "target": target,
            "command": display,
            "exit_code": result.returncode,
            "executable": resolved,
            "output": result.stdout.strip(),
        }
    except subprocess.TimeoutExpired:
        return {
            "check": label,
            "target": target,
            "command": display,
            "exit_code": 124,
            "executable": resolved,
            "output": f"timed out after {config.cmd_timeout}s",
        }
    except Exception as exc:
        return {
            "check": label,
            "target": target,
            "command": display,
            "exit_code": "error",
            "executable": resolved,
            "output": str(exc),
        }


def run_live_op(config: Config, key: str, spec: dict[str, Any]) -> dict[str, Any]:
    """Run a /live diag or mutation op (already validated against an allowlist)."""
    argv, target = _live_argv_for_op(config, list(spec["argv"]))
    return _run_live_argv(config, key, target, argv)


def local_live_mutation_refusal_reason(config: Config, argv: list[str]) -> str | None:
    """Refuse local mutation approvals that cannot execute on this host."""
    if config.live_ssh:
        return None
    if not argv:
        return "empty live mutation argv"
    if os.name == "nt" and any(part.startswith("/") for part in argv):
        return (
            "local Windows session cannot run POSIX-path live mutation argv; "
            "run Nodechat on the homelab or set --live-ssh to target it"
        )
    resolved = shutil.which(argv[0])
    if not resolved:
        return (
            f"local executable not found: {argv[0]}; "
            "run Nodechat on the target host or set --live-ssh"
        )
    return None


def parse_live_arg(arg: str) -> tuple[list[str], str]:
    raw = (arg or "").strip()
    if not raw:
        return ["health"], ""
    parts = split_command_line(raw)
    if not parts:
        return ["health"], ""
    name = parts[0].lower()
    if name == "smart":
        device = parts[1] if len(parts) > 1 else ""
        return ["smart"], device
    names = []
    for part in parts:
        for chunk in part.split(","):
            value = chunk.strip().lower()
            if value:
                names.append(value)
    return names or ["all"], ""


def expand_live_checks(names: list[str]) -> list[str]:
    if any(name in {"all", "stack"} for name in names):
        return ["health", "gpu", "power", "docker", "vllm", "ollama", "storage"]
    out: list[str] = []
    aliases = {
        "containers": "docker",
        "disk": "storage",
        "filesystem": "storage",
        "gpus": "gpu",
        "healthcheck": "health",
        "open-webui": "docker",
        "openwebui": "docker",
        "webui": "docker",
    }
    for name in names:
        value = aliases.get(name, name)
        if value not in out:
            out.append(value)
    return out


def live_command_for_check(config: Config, check: str, extra: str = "") -> tuple[list[str], str]:
    if check == "smart":
        device = extra.strip()
        if not device or not SMART_DEVICE_RE.fullmatch(device):
            raise RuntimeError("usage: /live smart /dev/<device>")
        local = ["smartctl", "-a", device]
        remote = "smartctl -a " + shlex.quote(device)
    else:
        spec = LIVE_CHECKS.get(check)
        if not spec:
            raise RuntimeError(f"unknown live check: {check}")
        local = list(spec["local"])
        remote = str(spec["remote"])
        if spec.get("needs_root"):
            remote = _remote_cd_prefix(config.live_root) + " && " + remote

    if config.live_ssh:
        remote_command = remote
        return ["ssh", "-o", "BatchMode=yes", config.live_ssh, remote_command], "ssh:" + config.live_ssh
    return local, "local"


def run_live_check(config: Config, check: str, extra: str = "") -> dict[str, Any]:
    argv, target = live_command_for_check(config, check, extra)
    display = " ".join(argv) if target.startswith("ssh:") else _format_argv(argv)
    resolved = shutil.which(argv[0])
    if not resolved:
        return {
            "check": check,
            "target": target,
            "command": display,
            "exit_code": 127,
            "executable": "",
            "output": f"executable not found: {argv[0]}",
        }
    run_argv = [resolved, *argv[1:]]
    result = subprocess.run(
        run_argv,
        cwd=str(pathlib.Path.cwd() if config.live_ssh else config.workspace),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=config.cmd_timeout,
        check=False,
    )
    return {
        "check": check,
        "target": target,
        "command": display,
        "exit_code": result.returncode,
        "executable": resolved,
        "output": result.stdout.strip(),
    }


def live_context_block(results: list[dict[str, Any]]) -> str:
    lines = ["LIVE_NODE_STATUS", f"timestamp: {utc_now()}"]
    for result in results:
        output, truncated = truncate_live_output(
            str(result.get("check") or ""),
            str(result.get("command") or ""),
            str(result.get("output") or ""),
        )
        lines.extend(
            [
                "",
                f"check: {result.get('check', '')}",
                f"target: {result.get('target', '')}",
                f"command: {result.get('command', '')}",
                f"exit_code: {result.get('exit_code', '')}",
                f"truncated: {str(truncated).lower()}",
            ]
        )
        if result.get("executable"):
            lines.append(f"executable: {result.get('executable')}")
        lines.extend(["", output or "(no output)"])
    return "\n".join(lines).strip()


def run_live_checks(config: Config, checks: list[str], extra: str = "") -> list[dict[str, Any]]:
    results = []
    for check in checks:
        try:
            results.append(run_live_check(config, check, extra if check == "smart" else ""))
        except subprocess.TimeoutExpired:
            results.append(
                {
                    "check": check,
                    "target": config.live_ssh or "local",
                    "command": check,
                    "exit_code": 124,
                    "executable": "",
                    "output": f"live check timed out after {config.cmd_timeout}s",
                }
            )
        except Exception as exc:
            results.append(
                {
                    "check": check,
                    "target": config.live_ssh or "local",
                    "command": check,
                    "exit_code": "error",
                    "executable": "",
                    "output": str(exc),
                }
            )
    return results


def _live_output_preserve_tail(key: str, command: str) -> bool:
    """Chronological logs need the newest lines, which are at the tail."""
    key_l = (key or "").lower()
    command_l = (command or "").lower()
    return (
        key_l.startswith("journal ")
        or key_l.startswith("logs ")
        or "journalctl " in command_l
        or "docker logs " in command_l
    )


def truncate_live_output(key: str, command: str, output: str) -> tuple[str, bool]:
    if len(output) <= MAX_CMD_OUTPUT_CHARS:
        return output, False
    if _live_output_preserve_tail(key, command):
        prefix = LIVE_OUTPUT_TRUNCATED_HEAD + "\n"
        keep = max(0, MAX_CMD_OUTPUT_CHARS - len(prefix))
        return prefix + output[-keep:], True
    return output[:MAX_CMD_OUTPUT_CHARS] + "\n" + LIVE_OUTPUT_TRUNCATED_TAIL, True


def _live_diag_block(key: str, result: dict[str, Any]) -> str:
    """Format a single LIVE_DIAG result the same way live_context_block does."""
    output, truncated = truncate_live_output(
        key,
        str(result.get("command") or ""),
        str(result.get("output") or ""),
    )
    lines = [
        "LIVE_NODE_STATUS",
        f"timestamp: {utc_now()}",
        "",
        f"check: {key}",
        f"target: {result.get('target', '')}",
        f"command: {result.get('command', '')}",
        f"exit_code: {result.get('exit_code', '')}",
        f"truncated: {str(truncated).lower()}",
    ]
    if result.get("executable"):
        lines.append(f"executable: {result.get('executable')}")
    lines.extend(["", output or "(no output)"])
    return "\n".join(lines).strip()


def _handle_live_diag(
    config: Config,
    session: dict[str, Any],
    key: str,
    spec: dict[str, Any],
) -> None:
    """Run a read-only diagnostic op immediately (no approval)."""
    result = run_live_op(config, key, spec)
    block = _live_diag_block(key, result)
    add_context(
        session,
        f"/live {key}",
        context_block("live_status", key, block),
        source="manual-live",
        provenance={
            "command": "/live",
            "op": key,
            "kind": "diag",
            "target": result.get("target", ""),
            "exit_code": result.get("exit_code", ""),
            "executable": result.get("executable", ""),
            "chars": len(block),
        },
    )
    audit_event(
        config,
        session,
        "live_diag_executed",
        status="ok",
        op=key,
        target=result.get("target", ""),
        exit_code=result.get("exit_code", ""),
        executable=result.get("executable", ""),
        **output_digest(block),
    )
    print(block)
    print()
    print(f"live context added: {key}")


def _handle_live_mutation_queue(
    config: Config,
    session: dict[str, Any],
    key: str,
    spec: dict[str, Any],
) -> None:
    """Queue a mutation for /approve. Does not execute."""
    command_str = "/live " + key
    argv = list(spec["argv"])
    target = "ssh:" + config.live_ssh if config.live_ssh else "local"
    refusal = local_live_mutation_refusal_reason(config, argv)
    if refusal:
        cwd = workspace_path(config, session)
        block = "\n".join(
            [
                "LIVE_MUTATION_REFUSED",
                f"timestamp: {utc_now()}",
                f"cwd: {cwd}",
                "class: live-mutation",
                f"command: {command_str}",
                f"target: {target}",
                f"argv: {_format_argv(argv)}",
                f"reason: {refusal}",
            ]
        )
        audit_event(
            config,
            session,
            "live_mutation_refused",
            status="refused",
            op=key,
            target=target,
            argv=argv,
            reason=refusal,
        )
        add_context(
            session,
            command_str,
            block,
            source="manual-live-mutation",
            provenance={
                "command": "/live",
                "op": key,
                "kind": "mutation",
                "target": target,
                "status": "refused",
                "reason": refusal,
            },
        )
        print(block)
        return
    row = queue_approval(
        session,
        command=command_str,
        class_name="live-mutation",
        reason=str(spec.get("description", key)),
        approval_reason=str(spec.get("approval_reason", f"approved live-mutation: {key}")),
    )
    audit_event(
        config,
        session,
        "live_mutation_queued",
        status="pending",
        approval_id=row.get("id", ""),
        op=key,
        target=target,
        argv=argv,
    )
    cwd = workspace_path(config, session)
    block = approval_required_block(row, cwd)
    add_context(
        session,
        command_str,
        block,
        source="manual-live-mutation",
        provenance={
            "command": "/live",
            "op": key,
            "kind": "mutation",
            "target": config.live_ssh or "local",
            "status": "approval_queued",
            "approval_id": row.get("id", ""),
        },
    )
    print(block)
    print()
    print(f"approval queued: {row.get('id')} (live mutation)")


def command_live(config: Config, session: dict[str, Any], arg: str) -> None:
    # Phase 1: extended /live ops (diag + mutation). These keys are
    # multi-word and exact-string (after lowercase + whitespace collapse), so
    # they're matched before the comma/space-split fixed-check parsing path.
    key = _live_op_key(arg)
    if key in LIVE_MUTATION_OPS:
        _handle_live_mutation_queue(config, session, key, LIVE_MUTATION_OPS[key])
        return
    if key in LIVE_DIAG_OPS:
        _handle_live_diag(config, session, key, LIVE_DIAG_OPS[key])
        return

    # Phase 2: existing fixed-check flow (health/gpu/power/docker/vllm/ollama/
    # storage/bmc/ups/smart and comma/space-separated combos).
    raw_names, extra = parse_live_arg(arg)
    checks = expand_live_checks(raw_names)
    invalid = [name for name in checks if name != "smart" and name not in LIVE_CHECKS]
    if invalid:
        print(f"unknown live check(s): {', '.join(invalid)}")
        print(
            "usage: /live [all|health|gpu|power|docker|vllm|ollama|storage|bmc|ups|"
            "smart /dev/<device>|ps|logs <vllm|open-webui|ollama>|"
            "journal ollama|inspect <vllm|open-webui>|restart <vllm-server|open-webui>]"
        )
        return
    results = run_live_checks(config, checks, extra)
    block = live_context_block(results)
    add_context(
        session,
        f"/live {arg.strip() or 'health'}",
        context_block("live_status", ",".join(checks), block),
        source="manual-live",
        provenance={
            "command": "/live",
            "checks": checks,
            "target": config.live_ssh or "local",
            "exit_codes": [row.get("exit_code") for row in results],
            "chars": len(block),
        },
    )
    audit_event(
        config,
        session,
        "live_check_executed",
        status="ok",
        checks=checks,
        target=config.live_ssh or "local",
        exit_codes=[row.get("exit_code") for row in results],
        **output_digest(block),
    )
    print(block)
    print()
    print(f"live context added: {', '.join(checks)}")


def parse_propose_args(arg: str) -> tuple[str, str]:
    if "::" not in arg:
        return "", ""
    raw_path, instruction = arg.split("::", 1)
    return raw_path.strip().strip('"'), instruction.strip()


def command_propose_edit(config: Config, session: dict[str, Any], arg: str) -> None:
    raw_path, instruction = parse_propose_args(arg)
    if not raw_path or not instruction:
        print("usage: /propose-edit <path> :: <instruction>")
        return

    path = resolve_workspace_path(config, session, raw_path)
    reason = path_safety_reason(config, session, path)
    if reason:
        print(f"propose-edit refused: {reason}")
        return
    if not path.exists():
        print(f"propose-edit failed: path does not exist: {path}")
        return
    if not path.is_file():
        print(f"propose-edit failed: not a file: {path}")
        return
    if not is_text_candidate(path):
        print(f"propose-edit refused: extension is not in text allow-list: {path.suffix or '[none]'}")
        return

    try:
        text, truncated = read_text_path(path)
    except Exception as exc:
        print(f"propose-edit failed: {exc}")
        return
    if truncated or len(text) > MAX_PROPOSE_FILE_CHARS:
        print(f"propose-edit refused: file too large for safe patch proposal: {path}")
        return

    prompt = "\n".join(
        [
            "Generate a patch proposal only. Do not claim the file was changed.",
            "Return plain unified diff text only. Do not wrap the diff in Markdown fences.",
            "Use the FILE_PATH exactly as provided in diff headers.",
            "If no safe change is possible, return NO_PROPOSED_CHANGE with one sentence explaining why.",
            "",
            f"FILE_PATH: {display_path(config, session, path)}",
            f"USER_INSTRUCTION: {instruction}",
            "",
            "CURRENT_FILE_CONTENT:",
            "```",
            text,
            "```",
        ]
    )

    print(f"proposing edit for: {path}")
    try:
        proposal = complete_tool_prompt(config, session, prompt)
    except Exception as exc:
        print(f"propose-edit failed: {exc}")
        return

    if not proposal:
        print("NO_PROPOSED_CHANGE")
        return
    proposal = strip_markdown_fences(proposal)

    session.setdefault("proposals", []).append(
        {
            "created_at": utc_now(),
            "path": str(path),
            "instruction": instruction,
            "proposal": proposal,
        }
    )
    add_context(
        session,
        f"/propose-edit {raw_path}",
        context_block(
            "proposed_edit",
            str(path),
            "\n".join(
                [
                    f"path: {path}",
                    f"instruction: {instruction}",
                    "",
                    proposal,
                ]
            ),
        ),
        source="manual-propose",
        provenance={"command": "/propose-edit", "path": str(path), "instruction": instruction},
    )
    print(proposal)
    print()
    print("proposal stored in session; no files were changed")


def strip_markdown_fences(text: str) -> str:
    value = text.strip()
    lines = value.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    lines = [line for line in lines if line.strip() != "```"]
    return "\n".join(lines).strip()


def select_proposal(session: dict[str, Any], selector: str) -> tuple[int, dict[str, Any] | None]:
    proposals = session.get("proposals", [])
    if not proposals:
        return -1, None
    value = selector.strip().lower()
    if not value or value == "latest":
        return len(proposals) - 1, proposals[-1]
    try:
        index = int(value) - 1
    except ValueError:
        return -1, None
    if index < 0 or index >= len(proposals):
        return -1, None
    return index, proposals[index]


def normalize_diff_path(value: str) -> str:
    path = value.strip().split("\t", 1)[0].strip()
    if path in {"", "/dev/null"}:
        return ""
    if path.startswith(("a/", "b/")):
        path = path[2:]
    return path.replace("\\", "/")


def diff_declared_new_path(patch: str) -> str:
    for line in patch.splitlines():
        if line.startswith("+++ "):
            return normalize_diff_path(line[4:])
    return ""


def declared_path_matches(config: Config, session: dict[str, Any], path: pathlib.Path, declared: str) -> bool:
    if not declared:
        return True
    expected = display_path(config, session, path)
    declared_l = declared.lower()
    expected_l = expected.lower()
    if declared_l == expected_l:
        return True
    if path.as_posix().lower().endswith(declared_l):
        return True
    return PurePosixPath(declared).name.lower() == path.name.lower() and declared_l.endswith(expected_l)


def same_patch_line(actual: str, expected: str) -> bool:
    return actual == expected or actual.rstrip("\r\n") == expected.rstrip("\r\n")


def parse_unified_hunks(patch: str) -> list[tuple[int, list[str]]]:
    patch_lines = patch.splitlines(keepends=True)
    hunks: list[tuple[int, list[str]]] = []
    idx = 0
    while idx < len(patch_lines):
        line = patch_lines[idx].rstrip("\r\n")
        match = HUNK_RE.match(line)
        if not match:
            idx += 1
            continue
        old_start = int(match.group("old_start"))
        idx += 1
        hunk_lines: list[str] = []
        while idx < len(patch_lines):
            hunk_raw = patch_lines[idx]
            hunk_line = hunk_raw.rstrip("\r\n")
            if HUNK_RE.match(hunk_line) or hunk_line.startswith(("diff --git ", "--- ", "+++ ")):
                break
            if hunk_line.startswith("\\ No newline"):
                idx += 1
                continue
            if hunk_line.strip().startswith("```") or hunk_line.strip() == "":
                break
            if not hunk_raw or hunk_raw[0] not in {" ", "-", "+"}:
                raise RuntimeError(f"unsupported patch line in hunk: {hunk_line[:80]}")
            hunk_lines.append(hunk_raw)
            idx += 1
        hunks.append((old_start, hunk_lines))
    if not hunks:
        raise RuntimeError("no unified-diff hunks found")
    return hunks


def split_hunk_lines(hunk_lines: list[str]) -> tuple[list[str], list[str]]:
    old_block: list[str] = []
    new_block: list[str] = []
    for hunk_raw in hunk_lines:
        prefix = hunk_raw[0]
        content = hunk_raw[1:]
        if prefix == " ":
            old_block.append(content)
            new_block.append(content)
        elif prefix == "-":
            old_block.append(content)
        elif prefix == "+":
            new_block.append(content)
    return old_block, new_block


def block_matches(lines: list[str], start: int, block: list[str]) -> bool:
    if start < 0 or start + len(block) > len(lines):
        return False
    for offset, expected in enumerate(block):
        if not same_patch_line(lines[start + offset], expected):
            return False
    return True


def find_hunk_start(lines: list[str], old_block: list[str], preferred: int, minimum: int) -> int:
    if not old_block:
        return max(minimum, min(preferred, len(lines)))
    matches = [
        start
        for start in range(minimum, len(lines) - len(old_block) + 1)
        if block_matches(lines, start, old_block)
    ]
    if not matches:
        return -1
    if preferred >= minimum and preferred in matches:
        return preferred
    if len(matches) == 1:
        return matches[0]
    raise RuntimeError("hunk context appears multiple times; refusing ambiguous apply")


def apply_unified_diff_text(original: str, patch: str) -> str:
    original_lines = original.splitlines(keepends=True)
    output: list[str] = []
    pos = 0
    for old_start, hunk_lines in parse_unified_hunks(patch):
        old_block, new_block = split_hunk_lines(hunk_lines)
        preferred = old_start - 1
        start = find_hunk_start(original_lines, old_block, preferred, pos)
        if start < 0:
            raise RuntimeError(f"hunk context not found near original line {old_start}")
        output.extend(original_lines[pos:start])
        output.extend(new_block)
        pos = start + len(old_block)
    output.extend(original_lines[pos:])
    return "".join(output)


def parse_apply_args(arg: str) -> tuple[str, str]:
    parts = arg.split()
    selector = "latest"
    mode = "preview"
    for part in parts:
        lowered = part.lower()
        if lowered in {"--confirm", "confirm"}:
            mode = "confirm"
        elif lowered in {"--check", "check"}:
            mode = "check"
        elif not lowered.startswith("--"):
            selector = part
    return selector, mode


def parse_undo_apply_args(arg: str) -> tuple[str, str]:
    parts = arg.split()
    selector = "latest"
    mode = "confirm"
    for part in parts:
        lowered = part.lower()
        if lowered in {"--check", "check"}:
            mode = "check"
        elif lowered in {"--confirm", "confirm"}:
            mode = "confirm"
        elif not lowered.startswith("--"):
            selector = part
    return selector, mode


def select_applied_proposal(session: dict[str, Any], selector: str) -> tuple[int, dict[str, Any] | None]:
    proposals = session.get("proposals", [])
    if not proposals:
        return -1, None
    value = (selector or "latest").strip().lower()
    if not value or value == "latest":
        for idx in range(len(proposals) - 1, -1, -1):
            proposal = proposals[idx]
            if proposal.get("applied_at") and proposal.get("backup_path") and not proposal.get("undone_at"):
                return idx, proposal
        return -1, None
    try:
        index = int(value) - 1
    except ValueError:
        return -1, None
    if index < 0 or index >= len(proposals):
        return -1, None
    return index, proposals[index]


def path_under(base: pathlib.Path, target: pathlib.Path) -> bool:
    try:
        return os.path.commonpath(
            [
                os.path.normcase(os.path.abspath(str(base.resolve()))),
                os.path.normcase(os.path.abspath(str(target.resolve()))),
            ]
        ) == os.path.normcase(os.path.abspath(str(base.resolve())))
    except ValueError:
        return False


def command_apply(config: Config, session: dict[str, Any], arg: str) -> None:
    selector, mode = parse_apply_args(arg)
    index, proposal = select_proposal(session, selector)
    if proposal is None:
        print("No matching proposal. Use /diff to inspect stored proposals.")
        return

    path = pathlib.Path(str(proposal.get("path") or "")).resolve()
    reason = path_safety_reason(config, session, path)
    if reason:
        print(f"apply refused: {reason}")
        return
    if not path.exists() or not path.is_file():
        print(f"apply refused: target file is missing or not a file: {path}")
        return
    if not is_text_candidate(path):
        print(f"apply refused: extension is not in text allow-list: {path.suffix or '[none]'}")
        return

    patch = strip_markdown_fences(str(proposal.get("proposal") or ""))
    declared = diff_declared_new_path(patch)
    if not declared_path_matches(config, session, path, declared):
        print(f"apply refused: proposal targets {declared!r}, expected {display_path(config, session, path)!r}")
        return

    try:
        original, truncated = read_text_path(path)
    except Exception as exc:
        print(f"apply failed: {exc}")
        return
    if truncated:
        print(f"apply refused: file exceeds read cap: {path}")
        return
    try:
        updated = apply_unified_diff_text(original, patch)
    except Exception as exc:
        print(f"apply check failed: {exc}")
        return

    if updated == original:
        print("apply check OK: patch makes no changes")
        return

    if mode == "preview":
        print(f"proposal {index + 1} targets: {path}")
        print("apply check OK; no files changed")
        print(f"To write this change, run: /apply {index + 1} --confirm")
        return

    if mode == "check":
        audit_event(
            config,
            session,
            "apply_checked",
            proposal_index=index + 1,
            path=str(path),
            status="ok",
        )
        print(f"apply check OK: proposal {index + 1} can be applied to {path}")
        return

    backup_dir = ensure_backup_dir(config, session)
    backup = backup_dir / f"{path.name}.{dt.datetime.now().strftime('%Y%m%d-%H%M%S')}.bak"
    with backup.open("w", encoding="utf-8", newline="") as handle:
        handle.write(original)
    with path.open("w", encoding="utf-8", newline="") as handle:
        handle.write(updated)
    proposal["applied_at"] = utc_now()
    proposal["backup_path"] = str(backup)
    proposal["backup_sha256"] = text_sha256(original)
    proposal["applied_sha256"] = text_sha256(updated)
    add_context(
        session,
        f"/apply {index + 1}",
        context_block(
            "applied_edit",
            str(path),
            "\n".join(
                [
                    f"path: {path}",
                    f"backup: {backup}",
                    f"proposal_index: {index + 1}",
                    "status: applied",
                ]
            ),
        ),
        source="manual-apply",
        provenance={
            "command": "/apply --confirm",
            "path": str(path),
            "backup_path": str(backup),
            "proposal_index": index + 1,
        },
    )
    audit_event(
        config,
        session,
        "apply_confirmed",
        proposal_index=index + 1,
        path=str(path),
        backup_path=str(backup),
        backup_sha256=proposal["backup_sha256"],
        applied_sha256=proposal["applied_sha256"],
        original_chars=len(original),
        updated_chars=len(updated),
        status="applied",
    )
    print(f"applied proposal {index + 1}: {path}")
    print(f"backup: {backup}")


def command_undo_apply(config: Config, session: dict[str, Any], arg: str) -> None:
    selector, mode = parse_undo_apply_args(arg)
    index, proposal = select_applied_proposal(session, selector)
    if proposal is None:
        print("No applied proposal available to undo.")
        return
    if not proposal.get("applied_at") or not proposal.get("backup_path"):
        print(f"undo refused: proposal {index + 1} has not been applied")
        return
    if proposal.get("undone_at"):
        print(f"undo refused: proposal {index + 1} was already undone at {proposal.get('undone_at')}")
        return

    path = pathlib.Path(str(proposal.get("path") or "")).resolve()
    reason = path_safety_reason(config, session, path)
    if reason:
        print(f"undo refused: {reason}")
        return
    if not path.exists() or not path.is_file():
        print(f"undo refused: target file is missing or not a file: {path}")
        return
    if not is_text_candidate(path):
        print(f"undo refused: extension is not in text allow-list: {path.suffix or '[none]'}")
        return

    backup = pathlib.Path(str(proposal.get("backup_path") or "")).resolve()
    backup_root = (config.session_root / "backups").resolve()
    if not path_under(backup_root, backup):
        print(f"undo refused: backup path is outside nodechat backups: {backup}")
        return
    if not backup.exists() or not backup.is_file():
        print(f"undo refused: backup file is missing: {backup}")
        return

    patch = strip_markdown_fences(str(proposal.get("proposal") or ""))
    declared = diff_declared_new_path(patch)
    if not declared_path_matches(config, session, path, declared):
        print(f"undo refused: proposal targets {declared!r}, expected {display_path(config, session, path)!r}")
        return

    try:
        current, current_truncated = read_text_path(path)
        original, original_truncated = read_text_path(backup)
    except Exception as exc:
        print(f"undo failed: {exc}")
        return
    if current_truncated:
        print(f"undo refused: current file exceeds read cap: {path}")
        return
    if original_truncated:
        print(f"undo refused: backup file exceeds read cap: {backup}")
        return
    original = original.replace("\r\r\n", "\r\n")

    applied_sha256 = str(proposal.get("applied_sha256") or "")
    if applied_sha256:
        current_matches = text_sha256(current) == applied_sha256
    else:
        try:
            expected_current = apply_unified_diff_text(original, patch)
        except Exception as exc:
            print(f"undo check failed: could not reconstruct applied content: {exc}")
            return
        current_matches = current == expected_current

    if not current_matches:
        audit_event(
            config,
            session,
            "undo_apply_refused",
            proposal_index=index + 1,
            path=str(path),
            backup_path=str(backup),
            expected_sha256=applied_sha256,
            current_sha256=text_sha256(current),
            status="current_mismatch",
        )
        print("undo refused: target file no longer matches the applied proposal")
        print("No files changed. Inspect the file or restore the backup manually if needed.")
        return

    if mode == "check":
        audit_event(
            config,
            session,
            "undo_apply_checked",
            proposal_index=index + 1,
            path=str(path),
            backup_path=str(backup),
            status="ok",
        )
        print(f"undo check OK: proposal {index + 1} can be restored from {backup}")
        return

    backup_dir = ensure_backup_dir(config, session)
    undo_backup = backup_dir / f"{path.name}.{dt.datetime.now().strftime('%Y%m%d-%H%M%S')}.undo-current.bak"
    with undo_backup.open("w", encoding="utf-8", newline="") as handle:
        handle.write(current)
    with path.open("w", encoding="utf-8", newline="") as handle:
        handle.write(original)

    proposal["undone_at"] = utc_now()
    proposal["undo_backup_path"] = str(undo_backup)
    add_context(
        session,
        f"/undo-apply {index + 1}",
        context_block(
            "undone_edit",
            str(path),
            "\n".join(
                [
                    f"path: {path}",
                    f"restored_from: {backup}",
                    f"undo_backup: {undo_backup}",
                    f"proposal_index: {index + 1}",
                    "status: undone",
                ]
            ),
        ),
        source="manual-undo-apply",
        provenance={
            "command": "/undo-apply",
            "path": str(path),
            "restored_from": str(backup),
            "undo_backup_path": str(undo_backup),
            "proposal_index": index + 1,
        },
    )
    audit_event(
        config,
        session,
        "undo_apply_confirmed",
        proposal_index=index + 1,
        path=str(path),
        backup_path=str(backup),
        undo_backup_path=str(undo_backup),
        restored_chars=len(original),
        status="undone",
    )
    print(f"undid proposal {index + 1}: {path}")
    print(f"restored from: {backup}")
    print(f"undo safety backup: {undo_backup}")


def split_command_line(command: str) -> list[str]:
    try:
        parts = shlex.split(command, posix=False)
    except ValueError:
        return []
    cleaned = []
    for part in parts:
        value = part.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        if value:
            cleaned.append(value)
    return cleaned


def command_path_blocked(config: Config, session: dict[str, Any], parts: list[str]) -> str | None:
    base = workspace_path(config, session)
    for part in parts[1:]:
        if part.startswith("-"):
            continue
        if any(ch in part for ch in {"*", "?", "[", "]"}):
            continue
        candidate = pathlib.Path(part)
        if not candidate.is_absolute():
            candidate = base / candidate
        try:
            resolved = candidate.resolve()
        except OSError:
            continue
        if resolved.exists() or candidate.is_absolute():
            reason = path_safety_reason(config, session, resolved)
            if reason:
                return reason
    return None


def classify_command(config: Config, session: dict[str, Any], command: str) -> tuple[str, str, list[str]]:
    parts = split_command_line(command)
    if not parts:
        return "unknown", "could not parse command", []

    exe = parts[0].lower()
    sub = parts[1].lower() if len(parts) > 1 else ""
    blocked_path = command_path_blocked(config, session, parts)
    if blocked_path:
        return "refused", blocked_path, parts

    if exe in {"python", "python3"} and parts[1:] in (["--version"], ["-V"]):
        return "read-only", "allowed version command", parts
    if exe == "py" and parts[1:] in (["-3", "--version"], ["-3", "-V"], ["--version"], ["-V"]):
        return "read-only", "allowed version command", parts
    if exe in {"git", "node", "npm", "pnpm", "rg", "sqlite3"} and parts[1:] in (["--version"], ["-v"], ["-V"]):
        return "read-only", "allowed version command", parts

    destructive = {"del", "erase", "format", "rd", "rmdir", "rm", "remove-item", "diskpart"}
    network = {"curl", "wget", "ssh", "scp", "git-fetch", "git-pull", "git-push", "git-clone"}
    privileged = {"runas", "sudo", "systemctl", "service", "sc"}
    write = {"copy", "cp", "mkdir", "move", "mv", "new-item", "set-content", "tee"}

    if exe in destructive:
        return "destructive", "destructive command refused in Phase 5A", parts
    if exe in privileged:
        return "privileged", "privileged command refused in Phase 5A", parts
    if exe in write:
        return "write", "write command refused in Phase 5A", parts

    if exe == "git":
        if sub in {"fetch", "pull", "push", "clone"}:
            return "network", "git network command refused in Phase 5A", parts
        if sub in {"add", "am", "apply", "checkout", "clean", "commit", "merge", "rebase", "reset", "restore", "switch"}:
            return "write", "git write/destructive command refused in Phase 5A", parts
        if any(arg.lower().startswith("--output") or arg.lower() == "--ext-diff" for arg in parts[2:]):
            return "write", "git output/external-diff flag refused in Phase 5A", parts
        if sub in {"", "branch", "diff", "log", "ls-files", "remote", "rev-parse", "show", "status", "tag"}:
            return "read-only", "allowed git read-only command", parts
        return "unknown", f"git subcommand not allowlisted: {sub}", parts

    if exe == "rg":
        if any(arg.lower().startswith("--pre") for arg in parts[1:]):
            return "refused", "rg --pre can execute external preprocessors", parts
        if any(arg.lower() in {"--hidden", "--no-ignore", "--no-ignore-vcs", "-u", "-uu", "-uuu"} for arg in parts[1:]):
            return "refused", "rg hidden/no-ignore traversal refused in Phase 5A", parts
        return "read-only", "allowed ripgrep read-only command", parts

    if exe in {"dir", "ls", "pwd", "type", "cat"}:
        return "read-only", "allowed internal read-only command", parts

    if exe in {"npm", "pnpm", "pip", "pip3"}:
        return "network", "package-manager command refused in Phase 5A", parts
    if exe in network:
        return "network", "network command refused in Phase 5A", parts

    return "unknown", "command is not in the Phase 5A read-only allowlist", parts


def approvable_command_reason(class_name: str, parts: list[str]) -> str | None:
    if not parts:
        return None
    exe = parts[0].lower()
    sub = parts[1].lower() if len(parts) > 1 else ""
    lowered = [part.lower() for part in parts]
    if exe != "git":
        return None
    if sub == "fetch" and lowered in (
        ["git", "fetch"],
        ["git", "fetch", "origin"],
        ["git", "fetch", "--all"],
        ["git", "fetch", "--prune"],
        ["git", "fetch", "--prune", "origin"],
    ):
        return "approved git fetch/fetch-prune network update"
    if sub == "pull" and lowered == ["git", "pull", "--ff-only"]:
        return "approved fast-forward-only git pull"
    if sub == "push" and lowered == ["git", "push"]:
        return "approved default-upstream git push"
    return None


def approval_display_reason(reason: str) -> str:
    return reason.replace(" refused in Phase 5A", " requires approval")


def next_approval_id(session: dict[str, Any]) -> str:
    max_seen = 0
    for row in session.get("approvals", []):
        value = str(row.get("id", ""))
        if value.startswith("a") and value[1:].isdigit():
            max_seen = max(max_seen, int(value[1:]))
    return f"a{max_seen + 1}"


def queue_approval(
    session: dict[str, Any],
    command: str,
    class_name: str,
    reason: str,
    approval_reason: str,
) -> dict[str, Any]:
    row = {
        "id": next_approval_id(session),
        "created_at": utc_now(),
        "status": "pending",
        "command": command,
        "class": class_name,
        "reason": reason,
        "approval_reason": approval_reason,
    }
    approvals = session.setdefault("approvals", [])
    approvals.append(row)
    if len(approvals) > MAX_APPROVALS:
        del approvals[:-MAX_APPROVALS]
    return row


def approval_required_block(row: dict[str, Any], cwd: pathlib.Path) -> str:
    return "\n".join(
        [
            "APPROVAL_REQUIRED",
            f"timestamp: {utc_now()}",
            f"id: {row.get('id', '')}",
            f"cwd: {cwd}",
            f"class: {row.get('class', '')}",
            f"command: {row.get('command', '')}",
            f"reason: {row.get('reason', '')}",
            f"approval_scope: {row.get('approval_reason', '')}",
            "",
            f"Run /approve {row.get('id', '')} to execute, or /reject {row.get('id', '')} to cancel.",
        ]
    ).strip()


def select_approval(session: dict[str, Any], selector: str) -> tuple[int, dict[str, Any] | None]:
    approvals = session.get("approvals", [])
    if not approvals:
        return -1, None
    value = (selector or "latest").strip().lower()
    if value == "latest":
        for idx in range(len(approvals) - 1, -1, -1):
            if approvals[idx].get("status") == "pending":
                return idx, approvals[idx]
        return len(approvals) - 1, approvals[-1]
    if value.isdigit():
        index = int(value) - 1
        if 0 <= index < len(approvals):
            return index, approvals[index]
    for idx, row in enumerate(approvals):
        if str(row.get("id", "")).lower() == value:
            return idx, row
    return -1, None


def git_worktree_clean(config: Config, session: dict[str, Any]) -> tuple[bool, str]:
    git_exe = shutil.which("git")
    if not git_exe:
        return False, "git executable not found"
    result = subprocess.run(
        [git_exe, "status", "--porcelain"],
        cwd=str(workspace_path(config, session)),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=config.cmd_timeout,
        check=False,
    )
    if result.returncode != 0:
        return False, result.stdout.strip() or f"git status exited {result.returncode}"
    if result.stdout.strip():
        return False, "working tree is not clean; refusing approved git pull"
    return True, ""


def run_approved_command(
    config: Config,
    session: dict[str, Any],
    parts: list[str],
    approval_reason: str,
) -> tuple[int | str, str, str, bool]:
    exe = parts[0].lower() if parts else ""
    sub = parts[1].lower() if len(parts) > 1 else ""
    if exe == "git" and sub in {"pull", "push"}:
        clean, reason = git_worktree_clean(config, session)
        if not clean:
            return "blocked", reason, shutil.which("git") or "", False

    resolved_exe = shutil.which(parts[0])
    if not resolved_exe:
        return 127, f"executable not found: {parts[0]}", "", True
    argv = [resolved_exe, *parts[1:]]
    result = subprocess.run(
        argv,
        cwd=str(workspace_path(config, session)),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=config.cmd_timeout,
        check=False,
    )
    return result.returncode, result.stdout.strip(), resolved_exe, True


def internal_dir(config: Config, session: dict[str, Any], parts: list[str]) -> tuple[int, str]:
    raw = parts[1] if len(parts) > 1 else "."
    path = resolve_workspace_path(config, session, raw)
    reason = path_safety_reason(config, session, path)
    if reason:
        return 1, f"refused: {reason}"
    if not path.exists():
        return 1, f"path does not exist: {path}"
    if path.is_file():
        return 0, str(path)
    rows = []
    for child in sorted(path.iterdir(), key=lambda item: (item.is_file(), item.name.lower()))[:MAX_TREE_ENTRIES]:
        if child.is_symlink() or path_safety_reason(config, session, child):
            continue
        suffix = "/" if child.is_dir() else ""
        rows.append(f"{child.name}{suffix}")
    return 0, "\n".join(rows)


def internal_type(config: Config, session: dict[str, Any], parts: list[str]) -> tuple[int, str]:
    if len(parts) < 2:
        return 1, "usage: type <path>"
    path = resolve_workspace_path(config, session, parts[1])
    reason = path_safety_reason(config, session, path)
    if reason:
        return 1, f"refused: {reason}"
    if not path.exists() or not path.is_file():
        return 1, f"not a file: {path}"
    if not is_text_candidate(path):
        return 1, f"not an allowed text file type: {path.suffix or '[none]'}"
    text, truncated = read_text_path(path, MAX_READ_BYTES)
    if truncated:
        text += "\n...[truncated]"
    return 0, text


def run_readonly_command(config: Config, session: dict[str, Any], parts: list[str]) -> tuple[int, str, str]:
    exe = parts[0].lower()
    if exe in {"dir", "ls"}:
        code, output = internal_dir(config, session, parts)
        return code, output, f"internal:{exe}"
    if exe == "pwd":
        return 0, str(workspace_path(config, session)), "internal:pwd"
    if exe in {"type", "cat"}:
        code, output = internal_type(config, session, parts)
        return code, output, f"internal:{exe}"

    argv = parts
    if exe == "git" and len(parts) > 1 and parts[1].lower() in {"diff", "log", "show"}:
        argv = ["git", "--no-pager", *parts[1:]]
        if parts[1].lower() == "diff" and "--no-ext-diff" not in parts:
            argv = ["git", "--no-pager", "diff", "--no-ext-diff", *parts[2:]]

    resolved_exe = shutil.which(argv[0])
    if not resolved_exe:
        return 127, f"executable not found: {argv[0]}", ""
    argv = [resolved_exe, *argv[1:]]

    result = subprocess.run(
        argv,
        cwd=str(workspace_path(config, session)),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=config.cmd_timeout,
        check=False,
    )
    return result.returncode, result.stdout.strip(), resolved_exe


def command_output_block(
    *,
    command: str,
    cwd: pathlib.Path,
    class_name: str,
    exit_code: int | str,
    output: str,
    reason: str = "",
    executable: str = "",
    approval_id: str = "",
) -> str:
    text = output.strip()
    truncated = False
    if len(text) > MAX_CMD_OUTPUT_CHARS:
        text = text[:MAX_CMD_OUTPUT_CHARS] + "\n...[truncated for nodechat command output cap]"
        truncated = True
    lines = [
        "COMMAND_OUTPUT",
        f"timestamp: {utc_now()}",
        f"cwd: {cwd}",
        f"class: {class_name}",
        f"command: {command}",
        f"exit_code: {exit_code}",
        f"truncated: {str(truncated).lower()}",
    ]
    if executable:
        lines.append(f"executable: {executable}")
    if approval_id:
        lines.append(f"approval_id: {approval_id}")
    if reason:
        lines.append(f"reason: {reason}")
    lines.extend(["", text or "(no output)"])
    return "\n".join(lines).strip()


def record_command(
    session: dict[str, Any],
    command: str,
    class_name: str,
    exit_code: int | str,
    output: str,
    reason: str = "",
    executable: str = "",
    approval_id: str = "",
) -> None:
    session.setdefault("commands", []).append(
        {
            "created_at": utc_now(),
            "command": command,
            "class": class_name,
            "exit_code": exit_code,
            "reason": reason,
            "executable": executable,
            "approval_id": approval_id,
            "output": output[:MAX_CMD_OUTPUT_CHARS],
        }
    )


def command_cmd(config: Config, session: dict[str, Any], arg: str) -> None:
    command = arg.strip()
    if not command:
        print("usage: /cmd <read-only command>")
        return
    class_name, reason, parts = classify_command(config, session, command)
    cwd = workspace_path(config, session)
    if class_name != "read-only":
        approval_reason = approvable_command_reason(class_name, parts)
        if approval_reason:
            row = queue_approval(session, command, class_name, approval_display_reason(reason), approval_reason)
            audit_event(
                config,
                session,
                "approval_queued",
                approval_id=row.get("id", ""),
                command=command,
                class_name=class_name,
                reason=row.get("reason", ""),
                approval_scope=approval_reason,
                status="pending",
            )
            block = approval_required_block(row, cwd)
            add_context(
                session,
                f"/cmd {command}",
                block,
                source="manual-cmd",
                provenance={
                    "command": "/cmd",
                    "subcommand": command,
                    "class": class_name,
                    "status": "approval_queued",
                    "approval_id": row.get("id", ""),
                },
            )
            print(block)
            print()
            print(f"approval queued: {row['id']}")
            return
        output = f"COMMAND_REFUSED\nclass: {class_name}\nreason: {reason}\ncommand: {command}"
        block = command_output_block(
            command=command,
            cwd=cwd,
            class_name=class_name,
            exit_code="refused",
            output=output,
            reason=reason,
            executable="not-run",
        )
        record_command(session, command, class_name, "refused", output, reason, "not-run")
        audit_event(
            config,
            session,
            "command_refused",
            command=command,
            class_name=class_name,
            exit_code="refused",
            executable="not-run",
            reason=reason,
            **output_digest(output),
        )
        add_context(
            session,
            f"/cmd {command}",
            block,
            source="manual-cmd",
            provenance={
                "command": "/cmd",
                "subcommand": command,
                "class": class_name,
                "status": "refused",
                "exit_code": "refused",
            },
        )
        print(block)
        print()
        print("refused command context added")
        return
    try:
        exit_code, output, executable = run_readonly_command(config, session, parts)
    except subprocess.TimeoutExpired:
        exit_code, output, executable = 124, f"command timed out after {config.cmd_timeout}s", ""
    except FileNotFoundError as exc:
        exit_code, output, executable = 127, str(exc), ""
    except Exception as exc:
        exit_code, output, executable = 1, str(exc), ""

    block = command_output_block(
        command=command,
        cwd=cwd,
        class_name=class_name,
        exit_code=exit_code,
        output=output,
        reason=reason,
        executable=executable,
    )
    record_command(session, command, class_name, exit_code, output, reason, executable)
    audit_event(
        config,
        session,
        "command_executed",
        command=command,
        class_name=class_name,
        exit_code=exit_code,
        executable=executable,
        reason=reason,
        **output_digest(output),
    )
    add_context(
        session,
        f"/cmd {command}",
        block,
        source="manual-cmd",
        provenance={
            "command": "/cmd",
            "subcommand": command,
            "class": class_name,
            "status": "executed",
            "exit_code": exit_code,
            "executable": executable,
        },
    )
    print(block)
    print()
    print("command output context added")


def command_approvals(session: dict[str, Any]) -> None:
    approvals = session.get("approvals", [])
    if not approvals:
        print("No approval requests in this session.")
        return
    for idx, row in enumerate(approvals, 1):
        print(
            "{idx}. {id} | {status} | {class_name} | {command}".format(
                idx=idx,
                id=row.get("id", ""),
                status=row.get("status", ""),
                class_name=row.get("class", ""),
                command=row.get("command", ""),
            )
        )
        if row.get("approval_reason"):
            print(f"   scope: {row.get('approval_reason')}")
        if row.get("exit_code") is not None:
            print(f"   exit_code: {row.get('exit_code')}")


def command_audit(config: Config, arg: str) -> None:
    raw = (arg or "").strip()
    limit = 20
    if raw:
        try:
            limit = max(1, min(200, int(raw)))
        except ValueError:
            print("usage: /audit [limit]")
            return
    rows = read_recent_audit(config, limit)
    if not rows:
        print(f"No audit events found at {audit_log_path(config)}")
        return
    print(f"audit: {audit_log_path(config)}")
    for row in rows:
        pieces = [
            str(row.get("created_at", "")),
            str(row.get("event_type", "")),
        ]
        if row.get("session_id"):
            pieces.append(f"session={row.get('session_id')}")
        if row.get("approval_id"):
            pieces.append(f"approval={row.get('approval_id')}")
        if row.get("exit_code") is not None:
            pieces.append(f"exit={row.get('exit_code')}")
        if row.get("command"):
            pieces.append(f"command={row.get('command')}")
        if row.get("path"):
            pieces.append(f"path={row.get('path')}")
        print(" | ".join(pieces))


def command_routing_mode(
    session: dict[str, Any],
    key: str,
    label: str,
    arg: str,
) -> None:
    defaults = {
        "history_mode": DEFAULT_HISTORY_MODE,
        "repo_mode": DEFAULT_REPO_MODE,
        "web_mode": DEFAULT_WEB_MODE,
        "live_mode": DEFAULT_LIVE_MODE,
        "model_mode": DEFAULT_MODEL_MODE,
    }
    default = defaults.get(key, "auto")
    raw = (arg or "").strip().lower()
    if not raw:
        current = session.get(key, default)
        print(f"{label}: {current}")
        return
    if raw not in ROUTING_MODES:
        print(f"{label}: invalid mode '{raw}', use one of {'|'.join(ROUTING_MODES)}")
        return
    session[key] = raw
    print(f"{label}: {raw}")


def command_model_mode(config: Config, session: dict[str, Any], arg: str) -> None:
    """Show or set model_mode.

    auto    -- per-turn dispatch picks fast by default and lifts to strong on
               long prompts, code markers, analysis verbs, history routing,
               or multi-file repo routing (only if vLLM is reachable).
    manual  -- always dispatch on the configured /profile.
    <profile> -- pin every turn to the named profile.

    Profile changes are still per-turn; session.profile remains the user's
    configured choice and is only changed by /profile or /model.
    """
    modes = valid_model_modes(config)
    raw = (arg or "").strip().lower()
    if not raw:
        current = session.get("model_mode", DEFAULT_MODEL_MODE)
        print(f"model-mode: {current}")
        return
    if raw not in modes:
        print(f"model-mode: invalid mode '{raw}', use one of {'|'.join(modes)}")
        return
    profile = load_model_profiles(config).get(raw)
    if profile_is_remote(profile) and not remote_models_enabled(session):
        print(f"model-mode refused: remote profile '{raw}' requires /remote-models enable")
        return
    session["model_mode"] = raw
    print(f"model-mode: {raw}")


def context_block_chars(block: dict[str, Any]) -> int:
    prov = block.get("provenance") or {}
    chars = prov.get("chars")
    if isinstance(chars, int):
        return chars
    return len(str(block.get("content") or ""))


def evidence_value(value: Any) -> str:
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(str(item) for item in value) + "]"
    if isinstance(value, dict):
        return json.dumps(value, sort_keys=True, ensure_ascii=False)
    return str(value)


def evidence_ref(block: dict[str, Any]) -> str:
    prov = block.get("provenance") or {}
    for key in (
        "path",
        "url",
        "query",
        "command",
        "checks",
        "target",
        "root",
        "approval_id",
    ):
        value = prov.get(key)
        if value not in ("", None, []):
            return f"{key}={_trunc(evidence_value(value), 100)}"
    query = str(block.get("query") or "").strip()
    return "query=" + _trunc(query, 100) if query else "ref=(none)"


def evidence_provenance_pairs(block: dict[str, Any]) -> list[str]:
    prov = block.get("provenance") or {}
    pairs = []
    for key, value in prov.items():
        if key == "chars" or value in ("", None, []):
            continue
        pairs.append(f"{key}={_trunc(evidence_value(value), 100)}")
    return pairs


def evidence_category(source: str) -> str:
    if source.startswith(("auto-repo", "manual-read", "manual-search", "manual-git-status")):
        return "repo"
    if source.startswith(("auto-history", "manual-history")):
        return "history"
    if source.startswith(("auto-web", "manual-web")):
        return "web"
    if source.startswith(("auto-live", "manual-live")):
        return "live"
    if source.startswith(("manual-cmd", "manual-approve")):
        return "cmd"
    return "other"


def evidence_state_summary(session: dict[str, Any], *, limit: int = 5) -> dict[str, Any]:
    blocks = list(session.get("context_blocks", [])[-max(1, limit) :])
    categories: dict[str, dict[str, Any]] = {}
    sources: list[dict[str, str]] = []
    for block in blocks:
        source = str(block.get("source") or "manual-legacy")
        category = evidence_category(source)
        ref = evidence_ref(block)
        sources.append({"category": category, "source": source, "ref": ref})
        row = categories.setdefault(category, {"count": 0, "sources": []})
        row["count"] += 1
        row["sources"].append(f"{source} {ref}")
    return {
        "block_count": len(blocks),
        "categories": categories,
        "sources": sources,
    }


def evidence_state_context(session: dict[str, Any], *, limit: int = 5) -> str:
    summary = evidence_state_summary(session, limit=limit)
    lines = [
        "NODECHAT_EVIDENCE_STATE",
        "scope: active loaded context blocks for this turn",
        "rule: project-specific claims must be supported by the loaded blocks below; if the needed evidence is absent, say Unknown - not loaded.",
    ]
    if not summary["block_count"]:
        lines.append("loaded_context: none")
        return "\n".join(lines)

    for category in ("repo", "history", "live", "web", "cmd", "other"):
        row = summary["categories"].get(category)
        if not row:
            continue
        lines.append(f"{category}: count={row['count']}; sources=[" + " | ".join(row["sources"]) + "]")
    return "\n".join(lines)


def split_force_answer_prompt(prompt: str) -> tuple[bool, str]:
    text = str(prompt or "")
    match = FORCE_ANSWER_PREFIX_RE.match(text)
    if not match:
        return False, text
    return True, text[match.end() :].lstrip()


def is_project_specific_prompt(prompt: str, dispatch: dict[str, Any]) -> bool:
    text = str(prompt or "")
    triggers = [str(item) for item in (dispatch.get("triggers") or [])]
    if any(
        item == "history-routing intent"
        or item.startswith("multi-file repo routing")
        for item in triggers
    ):
        return True
    if PROJECT_SPECIFIC_PROMPT_RE.search(text):
        return True
    if REPO_SUMMARY_SUBJECT_RE.search(text) and REPO_SUMMARY_INTENT_RE.search(text):
        return True
    return False


def suggested_context_command(config: Config, session: dict[str, Any], prompt: str) -> str:
    text = " ".join(str(prompt or "").strip().split())
    if detect_history_query(prompt):
        return "/history " + _trunc(text, 160)
    live_targets = detect_live_targets(prompt)
    if live_targets:
        return "/live " + ",".join(live_targets)
    if re.search(r"\b(current\s+state|status|where\s+do\s+we\s+stand|what\s+is\s+left|what'?s\s+left)\b", prompt, re.I):
        return "/read docs/CURRENT_STATE.md"
    if re.search(r"\b(runbook|docs?|documentation)\b", prompt, re.I):
        return '/search-files "' + _trunc(text, 120).replace('"', "'") + '" docs/runbooks'
    if re.search(r"\b(commit|diff)\b", prompt, re.I):
        return "/cmd git show <commit>"
    return '/search-files "' + _trunc(text, 120).replace('"', "'") + '"'


def answerability_gate_decision(
    config: Config,
    session: dict[str, Any],
    prompt: str,
    dispatch: dict[str, Any],
    evidence_state: dict[str, Any],
    *,
    force_answer: bool = False,
) -> dict[str, Any]:
    project_specific = is_project_specific_prompt(prompt, dispatch)
    suggested = suggested_context_command(config, session, prompt) if project_specific else ""
    override_status = "forced" if force_answer else "none"
    if force_answer:
        return {
            "action": "pass",
            "override_status": override_status,
            "project_specific": project_specific,
            "suggested_command": suggested,
            "message": "",
        }
    if project_specific and int(evidence_state.get("block_count") or 0) == 0:
        return {
            "action": "escalate",
            "override_status": override_status,
            "project_specific": project_specific,
            "suggested_command": suggested,
            "message": (
                "Unknown - not loaded. Auto-routing did not load evidence for that "
                "project-specific question.\n"
                f"Suggested next command: {suggested}\n"
                "Override only if you intentionally want an ungrounded answer: prefix "
                "`answer anyway:` or run one-shot with `--force-answer`."
            ),
        }
    return {
        "action": "pass",
        "override_status": override_status,
        "project_specific": project_specific,
        "suggested_command": suggested,
        "message": "",
    }


def command_evidence(session: dict[str, Any]) -> None:
    blocks = session.get("context_blocks", [])
    history_mode = session.get("history_mode", DEFAULT_HISTORY_MODE)
    repo_mode = session.get("repo_mode", DEFAULT_REPO_MODE)
    web_mode = session.get("web_mode", DEFAULT_WEB_MODE)
    live_mode = session.get("live_mode", DEFAULT_LIVE_MODE)
    print(f"history_mode={history_mode}  repo_mode={repo_mode}  web_mode={web_mode}  live_mode={live_mode}")
    if not blocks:
        print("No active context blocks.")
        return
    grouped: dict[str, list[tuple[int, dict[str, Any]]]] = {}
    for idx, block in enumerate(blocks, 1):
        source = str(block.get("source", "manual-legacy"))
        grouped.setdefault(source, []).append((idx, block))

    total_chars = sum(context_block_chars(block) for block in blocks)
    print(
        f"{len(blocks)} context block(s), "
        f"{len(grouped)} source group(s), total_chars={total_chars}"
    )
    print("Use /forget <index> to drop a block; indexes below are global.")

    for source in sorted(grouped):
        rows = grouped[source]
        source_chars = sum(context_block_chars(block) for _, block in rows)
        refs = [evidence_ref(block) for _, block in rows[:3]]
        print("")
        print(f"[{source}] blocks={len(rows)} chars={source_chars}")
        if refs:
            print("refs: " + " | ".join(refs))
        for idx, block in rows:
            created = block.get("created_at", "")
            chars = context_block_chars(block)
            prov_pairs = evidence_provenance_pairs(block)
            line = f"  {idx}. {created} | chars={chars}"
            if prov_pairs:
                line += " | " + ", ".join(prov_pairs)
            print(line)


def command_forget(session: dict[str, Any], arg: str) -> None:
    blocks = session.get("context_blocks", [])
    raw = (arg or "").strip().lower()
    if not raw:
        print("usage: /forget [n|latest|all]")
        return
    if not blocks:
        print("No active context blocks to forget.")
        return
    if raw == "all":
        n = len(blocks)
        session["context_blocks"] = []
        print(f"forgot {n} context block(s)")
        return
    if raw == "latest":
        target = len(blocks)
    else:
        try:
            target = int(raw)
        except ValueError:
            print(f"forget: invalid selector '{raw}'")
            return
    if target < 1 or target > len(blocks):
        print(f"forget: index {target} out of range (1..{len(blocks)})")
        return
    removed = blocks.pop(target - 1)
    print(f"forgot block {target} [{removed.get('source', 'manual-legacy')}]")


def command_reject(config: Config, session: dict[str, Any], arg: str) -> None:
    index, row = select_approval(session, arg)
    if row is None:
        print("No matching approval request.")
        return
    if row.get("status") != "pending":
        print(f"approval {row.get('id')} is already {row.get('status')}")
        return
    row["status"] = "rejected"
    row["rejected_at"] = utc_now()
    audit_event(
        config,
        session,
        "approval_rejected",
        approval_id=row.get("id", ""),
        command=row.get("command", ""),
        class_name=row.get("class", ""),
        status="rejected",
    )
    print(f"rejected approval {row.get('id')}: {row.get('command')}")


def _approve_live_mutation(config: Config, session: dict[str, Any], row: dict[str, Any]) -> None:
    """Execute a queued live-mutation approval through the live runner."""
    command = str(row.get("command") or "")
    op_key = command[len("/live "):].strip().lower() if command.startswith("/live ") else ""
    spec = LIVE_MUTATION_OPS.get(op_key)
    if not spec:
        print(f"approval {row.get('id')} no longer matches a known live mutation")
        return
    approval_reason = str(row.get("approval_reason") or spec.get("approval_reason", f"approved live-mutation: {op_key}"))
    result = run_live_op(config, op_key, spec)
    exit_code = result.get("exit_code", "")
    output = str(result.get("output") or "")
    executable = str(result.get("executable") or "")
    target = str(result.get("target") or (config.live_ssh or "local"))
    cwd = workspace_path(config, session)

    command_ran = isinstance(exit_code, int)
    row["status"] = "executed" if command_ran else "blocked"
    row["executed_at"] = utc_now()
    row["exit_code"] = exit_code
    row["executable"] = executable
    row["output"] = output[:MAX_CMD_OUTPUT_CHARS]
    row["approval_reason"] = approval_reason
    row["target"] = target
    event_type = "live_mutation_executed" if command_ran else "live_mutation_blocked"

    block = command_output_block(
        command=command,
        cwd=cwd,
        class_name="live-mutation",
        exit_code=exit_code,
        output=output,
        reason=approval_reason,
        executable=executable,
        approval_id=str(row.get("id", "")),
    )
    record_command(
        session,
        command,
        "live-mutation",
        exit_code,
        output,
        approval_reason,
        executable,
        str(row.get("id", "")),
    )
    audit_event(
        config,
        session,
        event_type,
        approval_id=row.get("id", ""),
        op=op_key,
        argv=list(spec["argv"]),
        target=target,
        exit_code=exit_code,
        executable=executable,
        approval_scope=approval_reason,
        status=row.get("status", ""),
        **output_digest(output),
    )
    add_context(
        session,
        f"/approve {row.get('id', '')}",
        block,
        source="manual-approve",
        provenance={
            "command": "/approve",
            "approval_id": row.get("id", ""),
            "subcommand": command,
            "class": "live-mutation",
            "op": op_key,
            "target": target,
            "status": row.get("status", ""),
            "exit_code": exit_code,
            "executable": executable,
        },
    )
    print(block)
    print()
    if command_ran:
        print(f"approved live mutation executed: {row.get('id')}")
    else:
        print(f"approved live mutation blocked: {row.get('id')}")


def command_approve(config: Config, session: dict[str, Any], arg: str) -> None:
    index, row = select_approval(session, arg)
    if row is None:
        print("No matching approval request.")
        return
    if row.get("status") != "pending":
        print(f"approval {row.get('id')} is already {row.get('status')}")
        return

    if str(row.get("class") or "") == "live-mutation":
        _approve_live_mutation(config, session, row)
        return

    command = str(row.get("command") or "")
    class_name, reason, parts = classify_command(config, session, command)
    approval_reason = approvable_command_reason(class_name, parts)
    if not approval_reason:
        print(f"approval {row.get('id')} no longer matches the approved command policy")
        return

    try:
        exit_code, output, executable, command_ran = run_approved_command(config, session, parts, approval_reason)
    except subprocess.TimeoutExpired:
        exit_code, output, executable, command_ran = 124, f"command timed out after {config.cmd_timeout}s", "", True
    except Exception as exc:
        exit_code, output, executable, command_ran = 1, str(exc), "", True

    row["status"] = "executed" if command_ran else "blocked"
    row["executed_at"] = utc_now()
    row["exit_code"] = exit_code
    row["executable"] = executable
    row["output"] = output[:MAX_CMD_OUTPUT_CHARS]
    row["approval_reason"] = approval_reason
    event_type = "approval_executed" if command_ran else "approval_blocked"

    block = command_output_block(
        command=command,
        cwd=workspace_path(config, session),
        class_name=class_name,
        exit_code=exit_code,
        output=output,
        reason=approval_reason,
        executable=executable,
        approval_id=str(row.get("id", "")),
    )
    record_command(
        session,
        command,
        class_name,
        exit_code,
        output,
        approval_reason,
        executable,
        str(row.get("id", "")),
    )
    audit_event(
        config,
        session,
        event_type,
        approval_id=row.get("id", ""),
        command=command,
        class_name=class_name,
        exit_code=exit_code,
        executable=executable,
        approval_scope=approval_reason,
        status=row.get("status", ""),
        **output_digest(output),
    )
    add_context(
        session,
        f"/approve {row.get('id', '')}",
        block,
        source="manual-approve",
        provenance={
            "command": "/approve",
            "approval_id": row.get("id", ""),
            "subcommand": command,
            "class": class_name,
            "status": row.get("status", ""),
            "exit_code": exit_code,
            "executable": executable,
        },
    )
    print(block)
    print()
    if command_ran:
        print(f"approved command executed: {row.get('id')}")
    else:
        print(f"approved command blocked: {row.get('id')}")


def command_diff(session: dict[str, Any], arg: str) -> None:
    proposals = session.get("proposals", [])
    if not proposals:
        print("No proposed diffs in this session.")
        return
    if arg.strip() == "all":
        selected = proposals
    else:
        selected = proposals[-1:]
    for idx, proposal in enumerate(selected, 1):
        print(f"proposal {idx}/{len(selected)} | {proposal.get('created_at', '')} | {proposal.get('path', '')}")
        print(f"instruction: {proposal.get('instruction', '')}")
        print(str(proposal.get("proposal") or "").strip())
        print()


def print_help() -> None:
    print(
        textwrap.dedent(
            """
            Commands
              /help                 show this help
              /exit                 save and exit
              /new                  start a fresh session
              /save                 save current session
              /sessions             list recent sessions
              /resume <id>          load a prior session by id prefix
              /profile [name]       list or switch model profile (fast|strong|deep)
              /model [name]         show or set model/profile
              /endpoint [url]       show or set OpenAI-compatible base URL
              /system [text]        show or replace system prompt
              /history <query>      fetch AI History context and inject it
              /pwd                  show nodechat workspace
              /tree [path]          add bounded directory tree context
              /read <path>          add bounded text-file context
              /search-files <query> [path]
                                    add bounded local file-search context
              /git-status           add read-only git status context
              /web-search <query>   add web search result context
              /web-fetch <url>      add fetched web page text context
              /web-open <url>       alias for /web-fetch
              /live [check]         add read-only live node status context
                                    fixed checks: health|gpu|power|docker|vllm|ollama|storage|bmc|ups
                                    diag ops: ps|logs <vllm|open-webui|ollama>|journal ollama|inspect <vllm|open-webui>
                                    mutations (queue for /approve): restart vllm-server|restart open-webui|restart ollama
              /propose-edit <path> :: <instruction>
                                    generate and store a patch proposal only
              /diff [all]           show latest or all stored patch proposals
              /apply [n|latest] [--check|--confirm]
                                    validate or apply a stored proposal with backup
              /undo-apply [n|latest] [--check]
                                    restore an applied proposal from its backup
              /cmd <command>        run allowlisted read-only command and inject output
              /approvals            list queued command approval requests
              /approve <id|latest>  execute a queued approved-scope command
              /reject <id|latest>   reject a queued command approval request
              /audit [limit]        show recent persistent audit events
              /history-mode [auto|manual|off]
                                    show or set AI History auto-routing mode (default auto)
              /repo-mode [auto|manual|off]
                                    show or set repo file auto-routing mode (default auto)
              /web-mode [auto|manual|off]
                                    show or set web auto-routing mode (default auto)
              /live-mode [auto|manual|off]
                                    show or set live-node auto-routing mode (default auto)
              /model-mode [auto|manual|fast|strong|deep|profile]
                                    show or set per-turn model dispatch mode (default auto)
              /remote-models [status|enable|disable]
                                    enable env-gated remote profiles for this session
              /costs                show estimated remote model cost for this session
              /evidence             group active context blocks by source with provenance
              /forget [n|latest|all] drop a context block (or all)
              /context              show active injected context blocks
              /clear-context        remove injected context blocks
              /status               check vLLM models and AI History health
              /paste                paste multi-line prompt, end with a single .

            Notes
              AI History, repo files, web context, and live node status auto-route on prompts that clearly call for them.
              Use /paste for multi-line input; direct multi-line terminal paste is split into separate turns.
              Ctrl-C interrupts a streaming answer and returns to the prompt.
              The disclosure line above the assistant reply names every routed source.
              /history-mode, /repo-mode, /web-mode, and /live-mode toggle auto-routing; manual slash commands always work.
              Web search results are leads, not proof; fetch/open source text before relying on a claim.
              Remote profiles are explicit-only and require /remote-models enable per session.
              /live fixed checks run immediately; service restarts queue for /approve.
              /propose-edit never writes files; it only prints/stores a proposal.
              /apply writes only with --confirm after diff validation.
              /undo-apply restores only if the file still matches the applied proposal.
              /cmd runs read-only commands immediately; selected git network commands queue for /approve.
              Destructive, privileged, package-manager, and unknown commands are refused.
            """
        ).strip()
    )


def print_sessions(config: Config) -> None:
    rows = list_sessions(config)
    if not rows:
        print("No saved nodechat sessions.")
        return
    for row in rows:
        print(f"{row['id']} | {row['updated_at']} | {row['model']}")
        if row["first_user"]:
            print(f"  {row['first_user']}")


def print_context(session: dict[str, Any]) -> None:
    blocks = session.get("context_blocks", [])
    if not blocks:
        print("No active context blocks.")
        return
    for idx, block in enumerate(blocks, 1):
        print(f"{idx}. {block.get('created_at', '')} | {block.get('query', '')}")
        content = str(block.get("content") or "")
        preview = content[:1200]
        print(preview)
        if len(content) > len(preview):
            print("... [truncated]")
        print()


def check_status(config: Config, session: dict[str, Any]) -> None:
    base_url = str(session.get("base_url") or config.base_url)
    active_profile_data = active_model_profile_data(config, session)
    if profile_is_remote(active_profile_data) and not remote_models_enabled(session):
        profile = active_model_profile(config, session) or "remote"
        print(f"model endpoint: remote profile disabled ({profile}); run /remote-models enable to probe")
        provider_kind = ""
    else:
        provider_kind = provider_kind_for_session(config, session)
    if provider_kind == "anthropic":
        profile = active_model_profile(config, session) or "anthropic"
        print(f"model endpoint: Anthropic profile configured ({profile}, {base_url}); /models probe skipped")
    elif provider_kind:
        try:
            models = get_json(endpoint(base_url, "models"), config.timeout, model_auth_headers(config, session))
            ids = [str(item.get("id", "")) for item in models.get("data", [])]
            print(f"vLLM/OpenAI endpoint: OK ({base_url})")
            if ids:
                print("models: " + ", ".join(ids[:8]))
        except Exception as exc:
            print(f"vLLM/OpenAI endpoint: FAIL ({exc})")

    try:
        health = get_json(endpoint(config.history_url, "health"), config.timeout, history_headers(config))
        total = health.get("total", "?")
        print(f"AI History endpoint: OK ({config.history_url}, total={total})")
    except Exception as exc:
        print(f"AI History endpoint: unavailable ({exc})")


def read_paste() -> str:
    print("Paste text. End with a single '.' on its own line.")
    lines = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        if line == ".":
            break
        lines.append(line)
    return "\n".join(lines).strip()


def _stdin_is_interactive() -> bool:
    try:
        return bool(sys.stdin.isatty())
    except Exception:
        return False


def _read_pending_posix_lines(max_lines: int, max_chars: int, quiet_seconds: float) -> tuple[list[str], bool]:
    try:
        import select
    except Exception:
        return [], False

    lines: list[str] = []
    chars = 0
    truncated = False
    while len(lines) < max_lines and chars < max_chars:
        try:
            ready, _, _ = select.select([sys.stdin], [], [], quiet_seconds)
        except Exception:
            break
        if not ready:
            break
        line = sys.stdin.readline()
        if line == "":
            break
        line = line.rstrip("\r\n")
        lines.append(line)
        chars += len(line) + 1
    if len(lines) >= max_lines or chars >= max_chars:
        truncated = True
    return lines, truncated


def _read_pending_windows_lines(max_lines: int, max_chars: int, quiet_seconds: float) -> tuple[list[str], bool]:
    try:
        import msvcrt
    except Exception:
        return [], False

    lines: list[str] = []
    current: list[str] = []
    chars = 0
    truncated = False
    deadline = time.monotonic() + quiet_seconds
    while len(lines) < max_lines and chars < max_chars:
        if not msvcrt.kbhit():
            if time.monotonic() >= deadline:
                break
            time.sleep(0.005)
            continue
        ch = msvcrt.getwch()
        deadline = time.monotonic() + quiet_seconds
        if ch in {"\r", "\n"}:
            lines.append("".join(current))
            current = []
            chars += 1
            continue
        current.append(ch)
        chars += 1
    if current and len(lines) < max_lines and chars <= max_chars:
        lines.append("".join(current))
    if len(lines) >= max_lines or chars >= max_chars:
        truncated = True
    return lines, truncated


def read_pending_terminal_lines(
    max_lines: int = MAX_DIRECT_PASTE_LINES,
    max_chars: int = MAX_DIRECT_PASTE_CHARS,
    quiet_seconds: float = DIRECT_PASTE_QUIET_SECONDS,
) -> tuple[list[str], bool]:
    """Best-effort non-blocking read of already-queued terminal lines."""
    if not _stdin_is_interactive():
        return [], False
    if os.name == "nt":
        return _read_pending_windows_lines(max_lines, max_chars, quiet_seconds)
    return _read_pending_posix_lines(max_lines, max_chars, quiet_seconds)


def merge_direct_paste_prompt(first_line: str) -> str:
    extra_lines, truncated = read_pending_terminal_lines()
    if not extra_lines:
        return first_line
    total_lines = len(extra_lines) + 1
    print(f"direct multi-line paste detected: combined {total_lines} lines into one prompt")
    if truncated:
        print("direct paste hit the input cap; use /paste for large multi-line prompts")
    return "\n".join([first_line, *extra_lines]).strip()


def discard_pending_terminal_input(reason: str = "interrupt") -> int:
    lines, truncated = read_pending_terminal_lines()
    if not lines:
        return 0
    print(f"discarded {len(lines)} queued input line(s) after {reason}; use /paste for multi-line text")
    if truncated:
        print("queued input drain hit the input cap; restart nodechat if prompts keep firing")
    return len(lines)


def command_profile(config: Config, session: dict[str, Any], arg: str) -> None:
    profiles = load_model_profiles(config)
    current = active_model_profile(config, session)
    if not arg:
        if not profiles:
            print(f"No profiles found. Optional config: {model_profiles_path(config)}")
            return
        print("profiles:")
        for name in sorted(profiles):
            profile = profiles[name]
            marker = "*" if name == current else " "
            provider = profile.get("provider") or "OpenAI-compatible"
            speed = profile.get("speed") or ""
            source = profile.get("source") or ""
            remote = "remote" if profile_is_remote(profile) else ""
            locked = "disabled" if profile_is_remote(profile) and not remote_models_enabled(session) else ""
            suffix = " | ".join(item for item in (provider, speed, source, remote, locked) if item)
            if suffix:
                suffix = " | " + suffix
            print(f"{marker} {name:<8} {profile['model']:<36} {profile['base_url']}{suffix}")
        print(f"profile config: {model_profiles_path(config)}")
        return

    name = arg.strip().lower()
    profile = profiles.get(name)
    if not profile:
        print(f"unknown profile: {arg}")
        print("available: " + ", ".join(sorted(profiles)))
        return
    if profile_is_remote(profile) and not remote_models_enabled(session):
        print(f"profile refused: remote profile '{name}' requires /remote-models enable")
        return
    apply_model_profile(session, profile)
    print(f"profile: {name}")
    print(f"model: {profile['model']}")
    print(f"endpoint: {profile['base_url']}")


def command_model(config: Config, session: dict[str, Any], arg: str) -> None:
    if not arg:
        profile = active_model_profile(config, session)
        if profile:
            print(f"profile: {profile}")
        print(str(session.get("model") or config.model))
        return

    profiles = load_model_profiles(config)
    name = arg.strip().lower()
    profile = profiles.get(name)
    if profile:
        if profile_is_remote(profile) and not remote_models_enabled(session):
            print(f"model refused: remote profile '{name}' requires /remote-models enable")
            return
        apply_model_profile(session, profile)
        print(f"profile: {name}")
        print(f"model: {profile['model']}")
        print(f"endpoint: {profile['base_url']}")
        return

    session["model"] = arg
    session["profile"] = ""
    print(f"model: {arg}")


def command_remote_models(config: Config, session: dict[str, Any], arg: str) -> None:
    raw = (arg or "status").strip().lower()
    profiles = {
        name: profile
        for name, profile in load_model_profiles(config).items()
        if profile_is_remote(profile)
    }
    if raw in {"status", ""}:
        print(f"remote-models: {'enabled' if remote_models_enabled(session) else 'disabled'}")
        if profiles:
            print("available remote profiles:")
            for name in sorted(profiles):
                profile = profiles[name]
                provider = profile.get("provider") or profile.get("provider_kind") or "remote"
                env_name = profile.get("api_key_env") or ""
                print(f"  {name}: {provider} | {profile['model']} | key_env={env_name}")
        else:
            print("available remote profiles: none")
            print("set NODECHAT_OPENAI_API_KEY + NODECHAT_OPENAI_MODEL or NODECHAT_ANTHROPIC_API_KEY + NODECHAT_ANTHROPIC_MODEL")
        return
    if raw == "enable":
        if not profiles:
            print("remote-models: no env-gated remote profiles available")
            print("set NODECHAT_OPENAI_API_KEY + NODECHAT_OPENAI_MODEL or NODECHAT_ANTHROPIC_API_KEY + NODECHAT_ANTHROPIC_MODEL")
            return
        session["remote_models_enabled"] = True
        print("remote-models: enabled for this session")
        print("remote dispatch is explicit only: /profile <remote>, /model <remote>, or /model-mode <remote>")
        return
    if raw == "disable":
        session["remote_models_enabled"] = False
        if str(session.get("model_mode") or "") in profiles:
            session["model_mode"] = DEFAULT_MODEL_MODE
        current_profile = profiles.get(active_model_profile(config, session))
        if profile_is_remote(current_profile):
            local_profile = load_model_profiles(config).get("strong")
            if local_profile:
                apply_model_profile(session, local_profile)
            else:
                session["profile"] = ""
                session["model"] = config.model
                session["base_url"] = str(config.base_url).rstrip("/")
        print("remote-models: disabled")
        return
    print("usage: /remote-models [status|enable|disable]")


def command_costs(session: dict[str, Any]) -> None:
    costs = session.get("costs") if isinstance(session.get("costs"), dict) else {}
    remote_turns = int(costs.get("remote_turns") or 0)
    input_tokens = int(costs.get("remote_input_tokens") or 0)
    output_tokens = int(costs.get("remote_output_tokens") or 0)
    estimated = float(costs.get("remote_estimated_usd") or 0.0)
    print("remote cost estimate for this session:")
    print(f"turns: {remote_turns}")
    print(f"input_tokens_est: {input_tokens}")
    print(f"output_tokens_est: {output_tokens}")
    print(f"estimated_usd: {estimated:.6f}")
    print("note: token counts are char/4 estimates unless provider usage accounting is added later")


def handle_command(
    line: str,
    config: Config,
    session: dict[str, Any],
) -> tuple[str, dict[str, Any], str | None]:
    raw = line[1:].strip()
    command, _, arg = raw.partition(" ")
    command = command.lower()
    arg = arg.strip()

    if command in {"exit", "quit", "q"}:
        save_session(config, session)
        return "exit", session, None

    if command in {"help", "h", "?"}:
        print_help()
        return "handled", session, None

    if command == "new":
        save_session(config, session)
        session = make_session(config)
        print(f"new session: {session['id']}")
        return "handled", session, None

    if command == "save":
        path = save_session(config, session)
        print(f"saved: {path}")
        return "handled", session, None

    if command == "sessions":
        print_sessions(config)
        return "handled", session, None

    if command == "resume":
        if not arg:
            print("usage: /resume <session-id-prefix>")
            return "handled", session, None
        path = find_session(config, arg)
        session = load_json(path)
        print(f"resumed: {session.get('id', path.stem)}")
        return "handled", session, None

    if command == "model":
        command_model(config, session, arg)
        return "handled", session, None

    if command == "profile":
        command_profile(config, session, arg)
        return "handled", session, None

    if command in {"remote-models", "remotemodels"}:
        command_remote_models(config, session, arg)
        return "handled", session, None

    if command in {"costs", "cost"}:
        command_costs(session)
        return "handled", session, None

    if command == "endpoint":
        if not arg:
            print(str(session.get("base_url") or config.base_url))
            return "handled", session, None
        session["base_url"] = arg.rstrip("/")
        session["profile"] = infer_model_profile(config, session["base_url"], str(session.get("model") or config.model))
        print(f"endpoint: {session['base_url']}")
        return "handled", session, None

    if command == "system":
        if not arg:
            print(str(session.get("system") or ""))
            return "handled", session, None
        session["system"] = arg
        print("system prompt replaced")
        return "handled", session, None

    if command == "history":
        if not arg:
            print("usage: /history <query>")
            return "handled", session, None
        try:
            context = fetch_history_context(config, arg, force=True)
        except Exception as exc:
            print(f"history lookup failed: {exc}")
            return "handled", session, None
        add_context(
            session,
            arg,
            context,
            source="manual-history",
            provenance={"command": "/history", "query": arg, "chars": len(context)},
        )
        print(f"history context added: {arg}")
        return "handled", session, None

    if command == "pwd":
        command_pwd(config, session)
        return "handled", session, None

    if command == "tree":
        command_tree(config, session, arg)
        return "handled", session, None

    if command == "read":
        command_read(config, session, arg)
        return "handled", session, None

    if command in {"search-files", "searchfiles"}:
        command_search_files(config, session, arg)
        return "handled", session, None

    if command in {"git-status", "gitstatus"}:
        command_git_status(config, session)
        return "handled", session, None

    if command in {"web-fetch", "web-open", "webfetch", "webopen"}:
        command_web_fetch(config, session, arg)
        return "handled", session, None

    if command in {"web-search", "websearch"}:
        command_web_search(config, session, arg)
        return "handled", session, None

    if command == "live":
        command_live(config, session, arg)
        return "handled", session, None

    if command in {"propose-edit", "propose"}:
        command_propose_edit(config, session, arg)
        return "handled", session, None

    if command == "diff":
        command_diff(session, arg)
        return "handled", session, None

    if command == "apply":
        command_apply(config, session, arg)
        return "handled", session, None

    if command in {"undo-apply", "undoapply"}:
        command_undo_apply(config, session, arg)
        return "handled", session, None

    if command == "cmd":
        command_cmd(config, session, arg)
        return "handled", session, None

    if command == "approvals":
        command_approvals(session)
        return "handled", session, None

    if command == "approve":
        command_approve(config, session, arg)
        return "handled", session, None

    if command == "reject":
        command_reject(config, session, arg)
        return "handled", session, None

    if command == "audit":
        command_audit(config, arg)
        return "handled", session, None

    if command in {"history-mode", "historymode"}:
        command_routing_mode(session, "history_mode", "history-mode", arg)
        return "handled", session, None

    if command in {"repo-mode", "repomode"}:
        command_routing_mode(session, "repo_mode", "repo-mode", arg)
        return "handled", session, None

    if command in {"web-mode", "webmode"}:
        command_routing_mode(session, "web_mode", "web-mode", arg)
        return "handled", session, None

    if command in {"live-mode", "livemode"}:
        command_routing_mode(session, "live_mode", "live-mode", arg)
        return "handled", session, None

    if command in {"model-mode", "modelmode"}:
        command_model_mode(config, session, arg)
        return "handled", session, None

    if command == "evidence":
        command_evidence(session)
        return "handled", session, None

    if command == "forget":
        command_forget(session, arg)
        return "handled", session, None

    if command == "context":
        print_context(session)
        return "handled", session, None

    if command in {"clear-context", "clearcontext"}:
        session["context_blocks"] = []
        print("context cleared")
        return "handled", session, None

    if command == "status":
        check_status(config, session)
        return "handled", session, None

    if command == "paste":
        text = read_paste()
        if not text:
            print("paste cancelled: no text")
            return "handled", session, None
        return "prompt", session, text

    print(f"unknown command: /{command}")
    print("use /help")
    return "handled", session, None


def prompt_label(session: dict[str, Any]) -> str:
    sid = str(session.get("id", "session"))
    short = sid[-6:] if len(sid) >= 6 else sid
    return f"nodechat:{short}> "


def send_user_prompt(config: Config, session: dict[str, Any], prompt: str, *, force_answer: bool = False) -> str:
    if not str(prompt or "").strip():
        print("empty prompt ignored")
        return "ignored"
    prefix_forced, clean_prompt = split_force_answer_prompt(prompt)
    force_answer = bool(force_answer or prefix_forced)
    prompt = clean_prompt
    if not str(prompt or "").strip():
        print("empty prompt ignored")
        return "ignored"

    # Per-turn dispatch resolves which (profile, model, endpoint) answers this
    # turn. Configured session profile/model/base_url stay unchanged; we only
    # override them inside a try/finally for the duration of the chat call so
    # any inspection after the turn (status, audit replay, save_session) sees
    # the user's configured state.
    dispatch = pick_turn_dispatch(config, session, prompt)
    routed_disclosure = auto_route_turn(config, session, prompt)
    generation_policy = resolve_generation_policy(config, session, dispatch)
    evidence_state = evidence_state_summary(session, limit=5)
    gate = answerability_gate_decision(
        config,
        session,
        prompt,
        dispatch,
        evidence_state,
        force_answer=force_answer,
    )
    turn_config = replace(
        config,
        temperature=float(generation_policy["temperature"]),
        max_tokens=int(generation_policy["max_tokens"]),
    )
    print(dispatch_disclosure(dispatch, routed_disclosure))

    audit_event(
        turn_config,
        session,
        "gate_decision_audit",
        route_signal=dispatch.get("triggers"),
        evidence_state=evidence_state,
        project_specific=gate.get("project_specific"),
        action=gate.get("action"),
        override_status=gate.get("override_status"),
        suggested_command=gate.get("suggested_command"),
        mode=dispatch.get("mode"),
        profile=dispatch.get("profile"),
    )

    if gate.get("action") == "escalate":
        message = str(gate.get("message") or "Unknown - not loaded.")
        session.setdefault("messages", []).append({"role": "user", "content": prompt})
        print()
        print("assistant:")
        print(message)
        session.setdefault("messages", []).append({"role": "assistant", "content": message})
        save_session(config, session)
        return "gated"

    if dispatch.get("auto_routed") or dispatch.get("fallback"):
        audit_event(
            config,
            session,
            "auto_route_model",
            status="ok" if dispatch.get("auto_routed") else "fallback",
            mode=dispatch.get("mode"),
            from_profile=dispatch.get("configured_profile"),
            to_profile=dispatch.get("profile"),
            rationale=dispatch.get("rationale"),
            triggers=dispatch.get("triggers"),
            vllm_available=dispatch.get("vllm_available"),
            vllm_probe_ms=dispatch.get("vllm_probe_ms"),
        )

    session.setdefault("messages", []).append({"role": "user", "content": prompt})
    api_messages = build_api_messages(turn_config, session)
    prompt_chars = sum(len(str(message.get("content") or "")) for message in api_messages)
    print()
    print("assistant:")

    saved_profile = session.get("profile")
    saved_model = session.get("model")
    saved_base_url = session.get("base_url")
    saved_force_answer = session.get("_force_answer_override")
    session["profile"] = dispatch.get("profile") or saved_profile or ""
    session["model"] = dispatch.get("model") or saved_model
    session["base_url"] = dispatch.get("base_url") or saved_base_url
    if force_answer:
        session["_force_answer_override"] = True
    started = time.perf_counter()
    try:
        try:
            content = stream_chat(turn_config, session) if turn_config.stream else complete_chat(turn_config, session)
        except KeyboardInterrupt:
            cost_estimate = remote_cost_estimate(turn_config, dispatch, prompt_chars, 0)
            audit_event(
                turn_config,
                session,
                "model_dispatched",
                status="interrupted",
                mode=dispatch.get("mode"),
                profile=dispatch.get("profile"),
                endpoint=dispatch.get("base_url"),
                model=dispatch.get("model"),
                auto_routed=bool(dispatch.get("auto_routed")),
                fallback=bool(dispatch.get("fallback")),
                remote=cost_estimate.get("remote"),
                provider_kind=cost_estimate.get("provider_kind"),
                generation_policy=generation_policy.get("name"),
                temperature=generation_policy.get("temperature"),
                max_tokens=generation_policy.get("max_tokens"),
                generation_reasons=generation_policy.get("reasons"),
                evidence_state=evidence_state,
                prompt_chars=prompt_chars,
                response_chars=0,
                estimated_input_tokens=cost_estimate.get("estimated_input_tokens"),
                estimated_output_tokens=cost_estimate.get("estimated_output_tokens"),
                estimated_cost_usd=cost_estimate.get("estimated_cost_usd"),
                latency_ms=int((time.perf_counter() - started) * 1000),
                reason="keyboard interrupt",
            )
            print()
            print("CHAT_INTERRUPTED")
            session["profile"] = saved_profile if saved_profile is not None else ""
            session["model"] = saved_model
            session["base_url"] = saved_base_url
            if saved_force_answer is None:
                session.pop("_force_answer_override", None)
            else:
                session["_force_answer_override"] = saved_force_answer
            save_session(config, session)
            return "interrupted"
        except Exception as exc:
            cost_estimate = remote_cost_estimate(turn_config, dispatch, prompt_chars, 0)
            audit_event(
                turn_config,
                session,
                "model_dispatched",
                status="error",
                mode=dispatch.get("mode"),
                profile=dispatch.get("profile"),
                endpoint=dispatch.get("base_url"),
                model=dispatch.get("model"),
                auto_routed=bool(dispatch.get("auto_routed")),
                fallback=bool(dispatch.get("fallback")),
                remote=cost_estimate.get("remote"),
                provider_kind=cost_estimate.get("provider_kind"),
                generation_policy=generation_policy.get("name"),
                temperature=generation_policy.get("temperature"),
                max_tokens=generation_policy.get("max_tokens"),
                generation_reasons=generation_policy.get("reasons"),
                evidence_state=evidence_state,
                prompt_chars=prompt_chars,
                response_chars=0,
                estimated_input_tokens=cost_estimate.get("estimated_input_tokens"),
                estimated_output_tokens=cost_estimate.get("estimated_output_tokens"),
                estimated_cost_usd=cost_estimate.get("estimated_cost_usd"),
                latency_ms=int((time.perf_counter() - started) * 1000),
                reason=_short_error(exc),
            )
            print(f"CHAT_ERROR: {exc}")
            session["profile"] = saved_profile if saved_profile is not None else ""
            session["model"] = saved_model
            session["base_url"] = saved_base_url
            if saved_force_answer is None:
                session.pop("_force_answer_override", None)
            else:
                session["_force_answer_override"] = saved_force_answer
            save_session(config, session)
            return "error"
        cost_estimate = remote_cost_estimate(turn_config, dispatch, prompt_chars, len(content))
        record_remote_cost(session, cost_estimate)
        audit_event(
            turn_config,
            session,
            "model_dispatched",
            status="ok",
            mode=dispatch.get("mode"),
            profile=dispatch.get("profile"),
            endpoint=dispatch.get("base_url"),
            model=dispatch.get("model"),
            auto_routed=bool(dispatch.get("auto_routed")),
            fallback=bool(dispatch.get("fallback")),
            remote=cost_estimate.get("remote"),
            provider_kind=cost_estimate.get("provider_kind"),
            generation_policy=generation_policy.get("name"),
            temperature=generation_policy.get("temperature"),
            max_tokens=generation_policy.get("max_tokens"),
            generation_reasons=generation_policy.get("reasons"),
            evidence_state=evidence_state,
            prompt_chars=prompt_chars,
            response_chars=len(content),
            estimated_input_tokens=cost_estimate.get("estimated_input_tokens"),
            estimated_output_tokens=cost_estimate.get("estimated_output_tokens"),
            estimated_cost_usd=cost_estimate.get("estimated_cost_usd"),
            latency_ms=int((time.perf_counter() - started) * 1000),
        )
    finally:
        session["profile"] = saved_profile if saved_profile is not None else ""
        session["model"] = saved_model
        session["base_url"] = saved_base_url
        if saved_force_answer is None:
            session.pop("_force_answer_override", None)
        else:
            session["_force_answer_override"] = saved_force_answer
    session.setdefault("messages", []).append({"role": "assistant", "content": content})
    save_session(config, session)
    return "ok"


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Terminal chat for Nodehome local vLLM.")
    parser.add_argument(
        "--base-url",
        default=os.environ.get("NODECHAT_BASE_URL", DEFAULT_BASE_URL),
        help="OpenAI-compatible base URL, e.g. http://192.168.1.198:8000/v1",
    )
    parser.add_argument(
        "--model",
        default=os.environ.get("NODECHAT_MODEL", DEFAULT_MODEL),
        help="model id exposed by the OpenAI-compatible endpoint",
    )
    parser.add_argument(
        "--api-key",
        default=os.environ.get("NODECHAT_API_KEY", ""),
        help="optional bearer token/API key for the model endpoint",
    )
    parser.add_argument("--no-stream", action="store_true", help="disable streaming responses")
    parser.add_argument("--temperature", type=float, default=float(os.environ.get("NODECHAT_TEMPERATURE", "0.2")))
    parser.add_argument("--max-tokens", type=int, default=int(os.environ.get("NODECHAT_MAX_TOKENS", "0")))
    parser.add_argument("--timeout", type=int, default=int(os.environ.get("NODECHAT_TIMEOUT", "120")))
    parser.add_argument("--max-history-messages", type=int, default=int(os.environ.get("NODECHAT_MAX_HISTORY_MESSAGES", "30")))
    parser.add_argument(
        "--session-root",
        default=os.environ.get("NODECHAT_SESSION_ROOT", str(DEFAULT_SESSION_ROOT)),
        help="directory for saved nodechat sessions",
    )
    parser.add_argument(
        "--workspace",
        default=os.environ.get("NODECHAT_WORKSPACE", str(DEFAULT_WORKSPACE)),
        help="default workspace for read-only local context commands",
    )
    parser.add_argument("--resume", help="resume session by id prefix or path")
    parser.add_argument("--list-sessions", action="store_true", help="list saved sessions and exit")
    parser.add_argument("--once", help="send one prompt and exit")
    parser.add_argument("--force-answer", action="store_true", help="bypass the answerability gate for --once prompts")
    parser.add_argument(
        "--history-url",
        default=os.environ.get("NODECHAT_HISTORY_URL", DEFAULT_HISTORY_URL),
        help="AI History KB base URL",
    )
    parser.add_argument(
        "--history-token",
        default=os.environ.get("NODECHAT_HISTORY_TOKEN", os.environ.get("AI_HISTORY_TOKEN", "")),
        help="optional AI History bearer token",
    )
    parser.add_argument("--history-limit", type=int, default=int(os.environ.get("NODECHAT_HISTORY_LIMIT", "8")))
    parser.add_argument("--cmd-timeout", type=int, default=int(os.environ.get("NODECHAT_CMD_TIMEOUT", "20")))
    parser.add_argument(
        "--live-ssh",
        default=os.environ.get("NODECHAT_LIVE_SSH", ""),
        help="optional SSH target for live-node checks, e.g. bmoore_77@192.168.1.198",
    )
    parser.add_argument(
        "--live-root",
        default=os.environ.get("NODECHAT_LIVE_ROOT", "~/nodehome"),
        help="repo path on the live node for checks that need the nodehome repo",
    )
    return parser.parse_args(argv)


def config_from_args(args: argparse.Namespace) -> Config:
    return Config(
        base_url=str(args.base_url).rstrip("/"),
        model=str(args.model),
        api_key=str(args.api_key or ""),
        stream=not bool(args.no_stream),
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


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    config = config_from_args(args)

    if args.list_sessions:
        print_sessions(config)
        return 0

    if args.resume:
        try:
            session = load_json(find_session(config, args.resume))
        except Exception as exc:
            print(f"could not resume session: {exc}", file=sys.stderr)
            return 1
    else:
        session = make_session(config)

    session.setdefault("base_url", config.base_url)
    session.setdefault("model", config.model)
    session.setdefault(
        "profile",
        infer_model_profile(config, str(session.get("base_url") or config.base_url), str(session.get("model") or config.model)),
    )
    session.setdefault("cwd", str(config.workspace))
    session.setdefault("system", DEFAULT_SYSTEM_PROMPT)
    session.setdefault("messages", [])
    session.setdefault("context_blocks", [])
    session.setdefault("proposals", [])
    session.setdefault("commands", [])
    session.setdefault("history_mode", DEFAULT_HISTORY_MODE)
    session.setdefault("repo_mode", DEFAULT_REPO_MODE)
    session.setdefault("web_mode", DEFAULT_WEB_MODE)
    session.setdefault("live_mode", DEFAULT_LIVE_MODE)
    session.setdefault("model_mode", DEFAULT_MODEL_MODE)
    session.setdefault("remote_models_enabled", False)
    session.setdefault("costs", {})

    print("Nodechat local terminal client")
    print(f"session: {session['id']}")
    if active_model_profile(config, session):
        print(f"profile: {active_model_profile(config, session)}")
    print(f"model: {session.get('model')}")
    print(f"endpoint: {session.get('base_url')}")
    print("use /help for commands")

    if args.once:
        line = str(args.once).strip()
        if line.startswith("/"):
            action, session, prompt = handle_command(line, config, session)
            save_session(config, session)
            if action == "prompt" and prompt:
                send_user_prompt(config, session, prompt, force_answer=bool(args.force_answer))
        else:
            send_user_prompt(config, session, str(args.once), force_answer=bool(args.force_answer))
        return 0

    while True:
        try:
            line = input("\n" + prompt_label(session))
        except (EOFError, KeyboardInterrupt):
            print()
            save_session(config, session)
            return 0

        line = line.strip()
        if not line:
            continue

        if line.startswith("/"):
            action, session, prompt = handle_command(line, config, session)
            save_session(config, session)
            if action == "exit":
                return 0
            if action == "prompt" and prompt:
                status = send_user_prompt(config, session, prompt)
                if status == "interrupted":
                    discard_pending_terminal_input()
            continue

        prompt = merge_direct_paste_prompt(line)
        status = send_user_prompt(config, session, prompt)
        if status == "interrupted":
            discard_pending_terminal_input()


if __name__ == "__main__":
    raise SystemExit(main())
