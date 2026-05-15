#!/usr/bin/env python3
"""Terminal chat client for the local Nodehome model stack.

This is intentionally a terminal copilot, not an autonomous shell agent. It
talks to an OpenAI-compatible local endpoint such as vLLM, persists sessions,
and can explicitly pull context from the private AI History KB.
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import os
import pathlib
import re
import shlex
import shutil
import subprocess
import sys
import textwrap
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import PurePosixPath
from typing import Any


DEFAULT_MODEL = "Qwen/Qwen2.5-32B-Instruct-AWQ"
DEFAULT_BASE_URL = "http://127.0.0.1:8000/v1"
DEFAULT_HISTORY_URL = "http://127.0.0.1:8765"
DEFAULT_SESSION_ROOT = pathlib.Path.home() / ".nodehome" / "nodechat"
DEFAULT_WORKSPACE = pathlib.Path(os.environ.get("NODECHAT_WORKSPACE", pathlib.Path.cwd()))
MAX_CONTEXT_CHARS = 9000
MAX_READ_BYTES = 160000
MAX_WEB_BYTES = 512000
MAX_TREE_ENTRIES = 180
MAX_SEARCH_RESULTS = 40
MAX_SEARCH_FILE_BYTES = 220000
MAX_PROPOSE_FILE_CHARS = 30000
MAX_PROPOSAL_TOKENS = 2400
MAX_CMD_OUTPUT_CHARS = 20000
MAX_APPROVALS = 50
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

DEFAULT_SYSTEM_PROMPT = """\
You are Nodechat, a local terminal copilot for the Nodehome homelab.

Be direct, factual, and pragmatic. Separate observed facts from inference.
Your current serving model and endpoint are provided in a NODECHAT_RUNTIME
system message. If asked what model you are, answer from that runtime message.
Do not claim to be custom-built or model-less.
When private AI History context is provided, treat it as local project memory
with provenance, not as general world knowledge. Do not claim to have searched
private history unless a HISTORY_CONTEXT block is present in this conversation.

You only have access to context explicitly injected by slash commands such as
/history, /read, /tree, /search-files, /git-status, /web-fetch, /web-search,
and /cmd or approved command output from /approve.
Do not claim broad filesystem, shell, or internet access. If the needed context
was not injected, say what slash command would retrieve it.
Patch proposals created by /propose-edit are proposals only. Do not claim they
were applied unless the user explicitly applies them outside Nodechat.
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


def ensure_session_dir(config: Config) -> pathlib.Path:
    path = config.session_root / "sessions"
    path.mkdir(parents=True, exist_ok=True)
    return path


def ensure_backup_dir(config: Config, session: dict[str, Any]) -> pathlib.Path:
    path = config.session_root / "backups" / safe_filename(str(session.get("id", "session")))
    path.mkdir(parents=True, exist_ok=True)
    return path


def make_session(config: Config) -> dict[str, Any]:
    sid = session_id()
    return {
        "id": sid,
        "created_at": utc_now(),
        "updated_at": utc_now(),
        "cwd": str(config.workspace),
        "base_url": config.base_url,
        "model": config.model,
        "system": DEFAULT_SYSTEM_PROMPT,
        "messages": [],
        "context_blocks": [],
        "approvals": [],
    }


def session_path(config: Config, session: dict[str, Any]) -> pathlib.Path:
    return ensure_session_dir(config) / f"{safe_filename(session['id'])}.json"


def save_session(config: Config, session: dict[str, Any]) -> pathlib.Path:
    session["updated_at"] = utc_now()
    path = session_path(config, session)
    path.write_text(json.dumps(session, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


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

    for block in session.get("context_blocks", [])[-3:]:
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


def stream_chat(config: Config, session: dict[str, Any]) -> str:
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
        headers={"Content-Type": "application/json", **auth_headers(config.api_key)},
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


def complete_chat(config: Config, session: dict[str, Any]) -> str:
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
        auth_headers(config.api_key),
    )
    choices = data.get("choices") or []
    if not choices:
        raise RuntimeError(f"no choices returned: {data}")
    message = choices[0].get("message") or {}
    content = str(message.get("content") or "").strip()
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
    return "\n".join(
        [
            "NODECHAT_RUNTIME",
            f"model: {session.get('model') or config.model}",
            f"endpoint: {session.get('base_url') or config.base_url}",
            "interface: scripts/nodechat.py terminal client",
            f"workspace: {session.get('cwd') or config.workspace}",
            "tool_access: explicit read-only local context, explicit web fetch/search, read-only /cmd, and selected /approve command output",
            "no_access: no arbitrary shell, no file writes, no automatic browsing",
        ]
    )


def tool_messages(
    config: Config,
    session: dict[str, Any],
    prompt: str,
) -> list[dict[str, str]]:
    messages = [{"role": "system", "content": str(session.get("system") or DEFAULT_SYSTEM_PROMPT)}]
    messages.append({"role": "system", "content": runtime_context(config, session)})
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
        auth_headers(config.api_key),
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


def add_context(session: dict[str, Any], query: str, content: str) -> None:
    session.setdefault("context_blocks", []).append(
        {
            "created_at": utc_now(),
            "query": query,
            "content": content,
        }
    )


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
    add_context(session, f"/tree {arg}".strip(), context_block("tree", str(root), content))
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
    add_context(session, f"/read {arg}", context_block("file_read", str(path), content))
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
    add_context(session, f"/search-files {arg}", context_block("file_search", query, "\n".join(lines)))
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
    add_context(session, "/git-status", context_block("git_status", str(root), content))
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


def command_web_fetch(config: Config, session: dict[str, Any], arg: str) -> None:
    url = arg.strip()
    if not url:
        print("usage: /web-fetch <url>")
        return
    try:
        content_type, text, truncated = fetch_url(url, config.timeout)
    except Exception as exc:
        print(f"web fetch failed: {exc}")
        return
    lines = [
        f"url: {url}",
        f"content_type: {content_type or '[unknown]'}",
        f"truncated: {str(truncated).lower()}",
        "",
        text,
    ]
    add_context(session, f"/web-fetch {url}", context_block("web_fetch", url, "\n".join(lines)))
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


def command_web_search(config: Config, session: dict[str, Any], arg: str) -> None:
    query = arg.strip()
    if not query:
        print("usage: /web-search <query>")
        return
    url = "https://duckduckgo.com/html/?" + urllib.parse.urlencode({"q": query})
    try:
        _, body, _ = fetch_raw_url(url, config.timeout)
    except Exception as exc:
        print(f"web search failed: {exc}")
        return

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
    add_context(session, f"/web-search {query}", context_block("web_search", query, "\n".join(lines)))
    print(f"web search context added: {query} ({len(rows)} results)")


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
        print(f"apply check OK: proposal {index + 1} can be applied to {path}")
        return

    backup_dir = ensure_backup_dir(config, session)
    backup = backup_dir / f"{path.name}.{dt.datetime.now().strftime('%Y%m%d-%H%M%S')}.bak"
    backup.write_text(original, encoding="utf-8")
    with path.open("w", encoding="utf-8", newline="") as handle:
        handle.write(updated)
    proposal["applied_at"] = utc_now()
    proposal["backup_path"] = str(backup)
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
    )
    print(f"applied proposal {index + 1}: {path}")
    print(f"backup: {backup}")


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
) -> tuple[int, str, str]:
    exe = parts[0].lower() if parts else ""
    sub = parts[1].lower() if len(parts) > 1 else ""
    if exe == "git" and sub == "pull":
        clean, reason = git_worktree_clean(config, session)
        if not clean:
            return 1, reason, shutil.which("git") or ""

    resolved_exe = shutil.which(parts[0])
    if not resolved_exe:
        return 127, f"executable not found: {parts[0]}", ""
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
    return result.returncode, result.stdout.strip(), resolved_exe


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
            block = approval_required_block(row, cwd)
            add_context(session, f"/cmd {command}", block)
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
        add_context(session, f"/cmd {command}", block)
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
    add_context(session, f"/cmd {command}", block)
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


def command_reject(session: dict[str, Any], arg: str) -> None:
    index, row = select_approval(session, arg)
    if row is None:
        print("No matching approval request.")
        return
    if row.get("status") != "pending":
        print(f"approval {row.get('id')} is already {row.get('status')}")
        return
    row["status"] = "rejected"
    row["rejected_at"] = utc_now()
    print(f"rejected approval {row.get('id')}: {row.get('command')}")


def command_approve(config: Config, session: dict[str, Any], arg: str) -> None:
    index, row = select_approval(session, arg)
    if row is None:
        print("No matching approval request.")
        return
    if row.get("status") != "pending":
        print(f"approval {row.get('id')} is already {row.get('status')}")
        return

    command = str(row.get("command") or "")
    class_name, reason, parts = classify_command(config, session, command)
    approval_reason = approvable_command_reason(class_name, parts)
    if not approval_reason:
        print(f"approval {row.get('id')} no longer matches the approved command policy")
        return

    try:
        exit_code, output, executable = run_approved_command(config, session, parts, approval_reason)
    except subprocess.TimeoutExpired:
        exit_code, output, executable = 124, f"command timed out after {config.cmd_timeout}s", ""
    except Exception as exc:
        exit_code, output, executable = 1, str(exc), ""

    row["status"] = "executed"
    row["executed_at"] = utc_now()
    row["exit_code"] = exit_code
    row["executable"] = executable
    row["output"] = output[:MAX_CMD_OUTPUT_CHARS]
    row["approval_reason"] = approval_reason

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
    add_context(session, f"/approve {row.get('id', '')}", block)
    print(block)
    print()
    print(f"approved command executed: {row.get('id')}")


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
              /model [name]         show or set model
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
              /propose-edit <path> :: <instruction>
                                    generate and store a patch proposal only
              /diff [all]           show latest or all stored patch proposals
              /apply [n|latest] [--check|--confirm]
                                    validate or apply a stored proposal with backup
              /cmd <command>        run allowlisted read-only command and inject output
              /approvals            list queued command approval requests
              /approve <id|latest>  execute a queued approved-scope command
              /reject <id|latest>   reject a queued command approval request
              /context              show active injected context blocks
              /clear-context        remove injected context blocks
              /status               check vLLM models and AI History health
              /paste                paste multi-line prompt, end with a single .

            Notes
              Local tools are explicit, read-only, and context-injection only.
              Web tools run only when invoked; search results are leads, not proof.
              /propose-edit never writes files; it only prints/stores a proposal.
              /apply writes only with --confirm after diff validation.
              /cmd runs read-only commands immediately; selected git network commands queue for /approve.
              Destructive, privileged, package-manager, and unknown commands are refused.
              Use /history explicitly when you want private project memory.
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
    try:
        models = get_json(endpoint(base_url, "models"), config.timeout, auth_headers(config.api_key))
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
        if not arg:
            print(str(session.get("model") or config.model))
            return "handled", session, None
        session["model"] = arg
        print(f"model: {arg}")
        return "handled", session, None

    if command == "endpoint":
        if not arg:
            print(str(session.get("base_url") or config.base_url))
            return "handled", session, None
        session["base_url"] = arg.rstrip("/")
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
        add_context(session, arg, context)
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

    if command in {"propose-edit", "propose"}:
        command_propose_edit(config, session, arg)
        return "handled", session, None

    if command == "diff":
        command_diff(session, arg)
        return "handled", session, None

    if command == "apply":
        command_apply(config, session, arg)
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
        command_reject(session, arg)
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


def send_user_prompt(config: Config, session: dict[str, Any], prompt: str) -> None:
    session.setdefault("messages", []).append({"role": "user", "content": prompt})
    print()
    print("assistant:")
    try:
        content = stream_chat(config, session) if config.stream else complete_chat(config, session)
    except Exception as exc:
        print(f"CHAT_ERROR: {exc}")
        save_session(config, session)
        return
    session.setdefault("messages", []).append({"role": "assistant", "content": content})
    save_session(config, session)


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
    session.setdefault("cwd", str(config.workspace))
    session.setdefault("system", DEFAULT_SYSTEM_PROMPT)
    session.setdefault("messages", [])
    session.setdefault("context_blocks", [])
    session.setdefault("proposals", [])
    session.setdefault("commands", [])

    print("Nodechat local terminal client")
    print(f"session: {session['id']}")
    print(f"model: {session.get('model')}")
    print(f"endpoint: {session.get('base_url')}")
    print("use /help for commands")

    if args.once:
        send_user_prompt(config, session, str(args.once))
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
                send_user_prompt(config, session, prompt)
            continue

        send_user_prompt(config, session, line)


if __name__ == "__main__":
    raise SystemExit(main())
