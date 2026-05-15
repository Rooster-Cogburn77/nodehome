#!/usr/bin/env python3
"""Terminal chat client for the local Nodehome model stack.

This is intentionally a terminal copilot, not an autonomous shell agent. It
talks to an OpenAI-compatible local endpoint such as vLLM, persists sessions,
and can explicitly pull context from the private AI History KB.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import pathlib
import sys
import textwrap
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


DEFAULT_MODEL = "Qwen/Qwen2.5-32B-Instruct-AWQ"
DEFAULT_BASE_URL = "http://127.0.0.1:8000/v1"
DEFAULT_HISTORY_URL = "http://127.0.0.1:8765"
DEFAULT_SESSION_ROOT = pathlib.Path.home() / ".nodehome" / "nodechat"

DEFAULT_SYSTEM_PROMPT = """\
You are Nodechat, a local terminal copilot for the Nodehome homelab.

Be direct, factual, and pragmatic. Separate observed facts from inference.
Your current serving model and endpoint are provided in a NODECHAT_RUNTIME
system message. If asked what model you are, answer from that runtime message.
Do not claim to be custom-built or model-less.
When private AI History context is provided, treat it as local project memory
with provenance, not as general world knowledge. Do not claim to have searched
private history unless a HISTORY_CONTEXT block is present in this conversation.

You do not have shell or filesystem tools in this interface. If the user needs
commands, give short commands that can be pasted safely.
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
    history_url: str
    history_token: str
    history_limit: int


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


def make_session(config: Config) -> dict[str, Any]:
    sid = session_id()
    return {
        "id": sid,
        "created_at": utc_now(),
        "updated_at": utc_now(),
        "cwd": str(pathlib.Path.cwd()),
        "base_url": config.base_url,
        "model": config.model,
        "system": DEFAULT_SYSTEM_PROMPT,
        "messages": [],
        "context_blocks": [],
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
            "content": "\n".join(
                [
                    "NODECHAT_RUNTIME",
                    f"model: {session.get('model') or config.model}",
                    f"endpoint: {session.get('base_url') or config.base_url}",
                    "interface: scripts/nodechat.py terminal client",
                    "tool_access: none; no shell or filesystem tools are available",
                ]
            ),
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
              /context              show active injected context blocks
              /clear-context        remove injected context blocks
              /status               check vLLM models and AI History health
              /paste                paste multi-line prompt, end with a single .

            Notes
              No shell/filesystem tools are available in nodechat v0.
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
        session.setdefault("context_blocks", []).append(
            {
                "created_at": utc_now(),
                "query": arg,
                "content": context,
            }
        )
        print(f"history context added: {arg}")
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
        history_url=str(args.history_url).rstrip("/"),
        history_token=str(args.history_token or ""),
        history_limit=int(args.history_limit),
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
    session.setdefault("system", DEFAULT_SYSTEM_PROMPT)
    session.setdefault("messages", [])
    session.setdefault("context_blocks", [])

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
