#!/usr/bin/env python3
"""Unified AI history knowledge-base helper.

This is a stdlib-only utility intended to run on the homelab node. It treats
Claude desktop, Codex, and Claude Code exports as one searchable private
history resource while preserving source provenance on every result.
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import sqlite3
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any


DEFAULT_SNAPSHOT = os.environ.get("AI_HISTORY_SNAPSHOT", "2026-05-14")
DEFAULT_ROOT = pathlib.Path(
    os.environ.get(
        "AI_HISTORY_ROOT",
        str(pathlib.Path.home() / "node-private/chat-exports"),
    )
)
DEFAULT_DB = pathlib.Path(
    os.environ.get(
        "AI_HISTORY_DB",
        str(DEFAULT_ROOT / f"unified/index/ai-history-{DEFAULT_SNAPSHOT}.sqlite"),
    )
)
DEFAULT_TOKEN = os.environ.get("AI_HISTORY_TOKEN")

SOURCE_CHOICES = ("claude-desktop", "codex", "claude-code")

TRIGGERS = (
    "previous",
    "prior",
    "earlier",
    "before",
    "last time",
    "where were we",
    "what did we",
    "decision",
    "handover",
    "session",
    "current state",
    "nodehome",
    "local_ai",
    "gpu",
    "gpu2",
    "vllm",
    "ollama",
    "open webui",
    "power cap",
    "pigtail",
    "super flower",
    "walmart",
    "jellyfin",
    "sweep",
    "claude",
    "codex",
)

STOP_WORDS = {
    "what",
    "when",
    "where",
    "which",
    "about",
    "did",
    "does",
    "was",
    "were",
    "the",
    "and",
    "for",
    "with",
    "that",
    "this",
    "have",
    "has",
    "our",
    "we",
    "you",
    "decide",
    "decided",
    "say",
    "said",
    "tell",
    "me",
}


def source_db_path(root: pathlib.Path, source_system: str, snapshot: str) -> pathlib.Path:
    if source_system == "claude-desktop":
        return root / f"claude/index/claude-{snapshot}.sqlite"
    if source_system == "codex":
        return root / f"codex/index/codex-{snapshot}.sqlite"
    if source_system == "claude-code":
        return root / f"claude-code/index/claude-code-{snapshot}.sqlite"
    raise ValueError(f"unknown source system: {source_system}")


def extracted_path(root: pathlib.Path, source_system: str, snapshot: str) -> pathlib.Path:
    if source_system == "claude-desktop":
        return root / f"claude/extracted/{snapshot}"
    if source_system == "codex":
        return root / f"codex/extracted/{snapshot}"
    if source_system == "claude-code":
        return root / f"claude-code/extracted/{snapshot}"
    raise ValueError(f"unknown source system: {source_system}")


def read_jsonl(path: pathlib.Path):
    with path.open(encoding="utf-8", errors="replace") as handle:
        for line_no, line in enumerate(handle, 1):
            line = line.strip()
            if not line:
                continue
            try:
                yield line_no, json.loads(line)
            except json.JSONDecodeError:
                continue


def flatten_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, list):
        return "\n".join(part for part in (flatten_text(item) for item in value) if part)
    if isinstance(value, dict):
        for key in ("text", "content", "output", "summary_text", "display"):
            if key in value:
                text = flatten_text(value.get(key))
                if text:
                    return text
        if value.get("type") in {"input_text", "output_text"}:
            return flatten_text(value.get("text"))
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def is_indexable_text(text: str) -> bool:
    if len(text.strip()) < 3:
        return False
    noise_markers = (
        "base64,",
        "image_url",
        "input_image",
        "encrypted_content",
    )
    return not any(marker in text for marker in noise_markers)


def connect(db_path: pathlib.Path) -> sqlite3.Connection:
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    return con


def should_search(query: str) -> tuple[bool, str]:
    q = query.lower()
    for trigger in TRIGGERS:
        if trigger in q:
            return True, f"matched trigger: {trigger}"
    if re.search(r"\b(we|our|us)\b", q):
        return True, "matched personal/project pronoun"
    return False, "no project-history trigger"


def normalize_query(query: str) -> str:
    query = query.strip()
    if '"' in query or " OR " in query or " AND " in query:
        return query

    terms = []
    for term in re.findall(r"[A-Za-z0-9_+-]{3,}", query.lower()):
        if term not in STOP_WORDS:
            terms.append(term)

    return " OR ".join(terms[:8]) if terms else query


def add_item(
    cur: sqlite3.Cursor,
    source_system: str,
    source_path: str,
    line_no: int | None,
    item_ref: str,
    title: str,
    kind: str,
    role: str,
    ts: str,
    text: str,
) -> int:
    text = str(text or "").strip()
    if len(text) < 3:
        return 0

    cur.execute(
        """
        INSERT INTO kb_items (
          source_system, source_path, line_no, item_ref, title, kind, role, ts, text
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (source_system, source_path, line_no, item_ref, title, kind, role, ts, text),
    )
    rowid = cur.lastrowid
    cur.execute(
        """
        INSERT INTO kb_fts (rowid, source_system, title, kind, role, text)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (rowid, source_system, title, kind, role, text),
    )
    return 1


def add_source_item(
    cur: sqlite3.Cursor,
    table: str,
    values: dict[str, Any],
) -> int:
    text = str(values.get("text") or "").strip()
    if not is_indexable_text(text):
        return 0

    columns = list(values.keys())
    placeholders = ", ".join("?" for _ in columns)
    cur.execute(
        f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})",
        [values[column] for column in columns],
    )
    return 1


def init_schema(cur: sqlite3.Cursor) -> None:
    cur.executescript(
        """
        PRAGMA journal_mode=WAL;
        DROP TABLE IF EXISTS kb_items;
        DROP TABLE IF EXISTS kb_fts;

        CREATE TABLE kb_items (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          source_system TEXT NOT NULL,
          source_path TEXT,
          line_no INTEGER,
          item_ref TEXT,
          title TEXT,
          kind TEXT,
          role TEXT,
          ts TEXT,
          text TEXT
        );

        CREATE INDEX idx_kb_items_source ON kb_items(source_system);
        CREATE INDEX idx_kb_items_kind ON kb_items(kind);
        CREATE INDEX idx_kb_items_title ON kb_items(title);

        CREATE VIRTUAL TABLE kb_fts USING fts5(
          source_system,
          title,
          kind,
          role,
          text
        );
        """
    )


def index_claude_desktop(root: pathlib.Path, snapshot: str) -> dict[str, Any]:
    source_root = extracted_path(root, "claude-desktop", snapshot)
    db_path = source_db_path(root, "claude-desktop", snapshot)
    conversations_json = source_root / "conversations.json"
    if not conversations_json.exists():
        return {"source": "claude-desktop", "ok": False, "error": f"missing {conversations_json}"}

    data = json.loads(conversations_json.read_text(encoding="utf-8"))
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    cur.executescript(
        """
        DROP TABLE IF EXISTS conversations;
        DROP TABLE IF EXISTS messages;
        DROP TABLE IF EXISTS messages_fts;

        CREATE TABLE conversations (
          uuid TEXT PRIMARY KEY,
          name TEXT,
          summary TEXT,
          created_at TEXT,
          updated_at TEXT
        );

        CREATE TABLE messages (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          conversation_uuid TEXT,
          message_index INTEGER,
          sender TEXT,
          text TEXT,
          created_at TEXT
        );

        CREATE VIRTUAL TABLE messages_fts USING fts5(name, sender, text);
        """
    )

    message_count = 0
    for conversation in data:
        uuid = str(conversation.get("uuid") or "")
        name = str(conversation.get("name") or conversation.get("summary") or uuid)
        cur.execute(
            """
            INSERT INTO conversations (uuid, name, summary, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                uuid,
                name,
                conversation.get("summary") or "",
                conversation.get("created_at") or "",
                conversation.get("updated_at") or "",
            ),
        )
        for message_index, message in enumerate(conversation.get("chat_messages") or [], 1):
            text = flatten_text(message.get("text") or message.get("content"))
            if not is_indexable_text(text):
                continue
            sender = str(message.get("sender") or message.get("role") or "")
            created_at = str(message.get("created_at") or message.get("updated_at") or "")
            cur.execute(
                """
                INSERT INTO messages (
                  conversation_uuid, message_index, sender, text, created_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (uuid, message_index, sender, text, created_at),
            )
            rowid = cur.lastrowid
            cur.execute(
                "INSERT INTO messages_fts (rowid, name, sender, text) VALUES (?, ?, ?, ?)",
                (rowid, name, sender, text),
            )
            message_count += 1

    con.commit()
    con.close()
    return {
        "source": "claude-desktop",
        "ok": True,
        "db": str(db_path),
        "conversations": len(data),
        "messages": message_count,
    }


def codex_item_text(item: dict[str, Any]) -> tuple[str, str, str]:
    item_type = str(item.get("type") or "")
    role = str(item.get("role") or "")

    if item_type == "message":
        if role != "assistant":
            return "session_context", role, ""
        text = flatten_text(item.get("content"))
        return "assistant_message", role, text

    if item_type in {"function_call", "tool_call"}:
        name = item.get("name") or item.get("call_id") or item_type
        text = "\n".join(
            part
            for part in (
                str(name),
                flatten_text(item.get("arguments")),
            )
            if part
        )
        return "tool_call", "tool", text

    if item_type in {"function_call_output", "tool_output"}:
        return "tool_output", "tool", flatten_text(item.get("output"))

    if item_type == "reasoning":
        return "assistant_message", "assistant", flatten_text(item.get("summary"))

    explicit_text = (
        flatten_text(item.get("text"))
        or flatten_text(item.get("content"))
        or flatten_text(item.get("message"))
        or flatten_text(item.get("output"))
    )
    return item_type or "record", role, explicit_text


def index_codex(root: pathlib.Path, snapshot: str) -> dict[str, Any]:
    source_root = extracted_path(root, "codex", snapshot)
    db_path = source_db_path(root, "codex", snapshot)
    if not source_root.exists():
        return {"source": "codex", "ok": False, "error": f"missing {source_root}"}

    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    cur.executescript(
        """
        DROP TABLE IF EXISTS codex_items;
        DROP TABLE IF EXISTS codex_items_fts;

        CREATE TABLE codex_items (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          source_path TEXT,
          line_no INTEGER,
          kind TEXT,
          role TEXT,
          ts TEXT,
          text TEXT
        );

        CREATE VIRTUAL TABLE codex_items_fts USING fts5(kind, role, text);
        """
    )

    counts: dict[str, int] = {}

    history = source_root / "history.jsonl"
    if history.exists():
        for line_no, record in read_jsonl(history):
            text = flatten_text(record.get("text"))
            n = add_source_item(
                cur,
                "codex_items",
                {
                    "source_path": "history.jsonl",
                    "line_no": line_no,
                    "kind": "history_prompt",
                    "role": "user",
                    "ts": str(record.get("ts") or ""),
                    "text": text,
                },
            )
            if n:
                counts["history_prompt"] = counts.get("history_prompt", 0) + 1

    sessions_root = source_root / "sessions"
    for path in sorted(sessions_root.rglob("*.jsonl")) if sessions_root.exists() else []:
        rel = path.relative_to(source_root).as_posix()
        for line_no, record in read_jsonl(path):
            ts = str(record.get("timestamp") or record.get("ts") or "")
            record_type = str(record.get("type") or "")
            if record_type == "event_msg":
                continue
            item = None
            for key in ("payload", "item", "message"):
                if isinstance(record.get(key), dict):
                    item = record[key]
                    break
            if item is None:
                item = record
            kind, role, text = codex_item_text(item)
            if record_type == "response_item" and kind == "record":
                kind = "assistant_message"
            n = add_source_item(
                cur,
                "codex_items",
                {
                    "source_path": rel,
                    "line_no": line_no,
                    "kind": kind,
                    "role": role,
                    "ts": ts,
                    "text": text,
                },
            )
            if n:
                counts[kind] = counts.get(kind, 0) + 1

    cur.execute(
        """
        INSERT INTO codex_items_fts (rowid, kind, role, text)
        SELECT id, kind, role, text FROM codex_items
        """
    )
    con.commit()
    total = cur.execute("SELECT COUNT(*) FROM codex_items").fetchone()[0]
    con.close()
    return {"source": "codex", "ok": True, "db": str(db_path), "items": total, **counts}


def claude_code_record_text(record: dict[str, Any]) -> str:
    message = record.get("message")
    if isinstance(message, dict):
        text = flatten_text(message.get("content"))
        if text:
            return text
    if isinstance(message, str):
        return message

    parts = []
    for key in ("display", "pastedContents", "data", "toolUseResult"):
        text = flatten_text(record.get(key))
        if text:
            parts.append(text)
    return "\n".join(parts)


def index_claude_code(root: pathlib.Path, snapshot: str) -> dict[str, Any]:
    source_root = extracted_path(root, "claude-code", snapshot)
    db_path = source_db_path(root, "claude-code", snapshot)
    if not source_root.exists():
        return {"source": "claude-code", "ok": False, "error": f"missing {source_root}"}

    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    cur.executescript(
        """
        DROP TABLE IF EXISTS claude_code_items;
        DROP TABLE IF EXISTS claude_code_fts;

        CREATE TABLE claude_code_items (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          source_path TEXT,
          line_no INTEGER,
          session_id TEXT,
          kind TEXT,
          cwd TEXT,
          ts TEXT,
          text TEXT
        );

        CREATE VIRTUAL TABLE claude_code_fts USING fts5(kind, cwd, text);
        """
    )

    counts: dict[str, int] = {}
    files = sorted(source_root.rglob("*.jsonl"))
    for path in files:
        rel = path.relative_to(source_root).as_posix()
        for line_no, record in read_jsonl(path):
            kind = str(record.get("type") or "record")
            if kind not in {"user", "assistant", "record"}:
                continue
            text = claude_code_record_text(record)
            n = add_source_item(
                cur,
                "claude_code_items",
                {
                    "source_path": rel,
                    "line_no": line_no,
                    "session_id": str(record.get("sessionId") or record.get("session_id") or ""),
                    "kind": kind,
                    "cwd": str(record.get("cwd") or record.get("project") or ""),
                    "ts": str(record.get("timestamp") or ""),
                    "text": text,
                },
            )
            if n:
                counts[kind] = counts.get(kind, 0) + 1

    cur.execute(
        """
        INSERT INTO claude_code_fts (rowid, kind, cwd, text)
        SELECT id, kind, cwd, text FROM claude_code_items
        """
    )
    con.commit()
    total = cur.execute("SELECT COUNT(*) FROM claude_code_items").fetchone()[0]
    con.close()
    return {
        "source": "claude-code",
        "ok": True,
        "db": str(db_path),
        "files": len(files),
        "items": total,
        **counts,
    }


def index_sources(
    root: pathlib.Path,
    snapshot: str,
    sources: list[str],
) -> list[dict[str, Any]]:
    selected = list(SOURCE_CHOICES) if "all" in sources else sources
    results = []
    for source in selected:
        if source == "claude-desktop":
            results.append(index_claude_desktop(root, snapshot))
        elif source == "codex":
            results.append(index_codex(root, snapshot))
        elif source == "claude-code":
            results.append(index_claude_code(root, snapshot))
    return results


def rebuild_from_source_dbs(
    root: pathlib.Path,
    db_path: pathlib.Path,
    snapshot: str,
) -> dict[str, int]:
    """Rebuild unified DB from already-built source DBs.

    This intentionally does not parse raw exports. The raw-export parsers can
    evolve separately; this command composes the stable per-source indexes.
    """

    source_dbs = {
        source: source_db_path(root, source, snapshot) for source in SOURCE_CHOICES
    }

    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    init_schema(cur)

    counts: dict[str, int] = {}

    claude_db = source_dbs["claude-desktop"]
    if claude_db.exists():
        src = connect(claude_db)
        n = 0
        rows = src.execute(
            """
            SELECT c.name AS title,
                   m.conversation_uuid,
                   m.message_index,
                   m.sender,
                   m.text,
                   m.created_at
              FROM messages m
              JOIN conversations c ON c.uuid = m.conversation_uuid
            """
        )
        for row in rows:
            ref = f"{row['conversation_uuid']}:{row['message_index']}"
            n += add_item(
                cur,
                "claude-desktop",
                "conversations.json",
                row["message_index"],
                ref,
                row["title"] or "",
                "message",
                row["sender"] or "",
                row["created_at"] or "",
                row["text"] or "",
            )
        counts["claude-desktop"] = n
        src.close()

    codex_db = source_dbs["codex"]
    if codex_db.exists():
        src = connect(codex_db)
        n = 0
        rows = src.execute(
            "SELECT source_path, line_no, kind, role, ts, text FROM codex_items"
        )
        for row in rows:
            ref = f"{row['source_path']}:{row['line_no']}"
            n += add_item(
                cur,
                "codex",
                row["source_path"] or "",
                row["line_no"],
                ref,
                row["source_path"] or "",
                row["kind"] or "",
                row["role"] or "",
                row["ts"] or "",
                row["text"] or "",
            )
        counts["codex"] = n
        src.close()

    claude_code_db = source_dbs["claude-code"]
    if claude_code_db.exists():
        src = connect(claude_code_db)
        n = 0
        rows = src.execute(
            """
            SELECT source_path, line_no, session_id, kind, cwd, ts, text
              FROM claude_code_items
            """
        )
        for row in rows:
            ref = f"{row['session_id']}:{row['line_no']}"
            n += add_item(
                cur,
                "claude-code",
                row["source_path"] or "",
                row["line_no"],
                ref,
                row["cwd"] or "",
                row["kind"] or "",
                row["kind"] or "",
                row["ts"] or "",
                row["text"] or "",
            )
        counts["claude-code"] = n
        src.close()

    con.commit()
    cur.execute("INSERT INTO kb_fts(kb_fts) VALUES('optimize')")
    con.commit()
    counts["total"] = cur.execute("SELECT COUNT(*) FROM kb_items").fetchone()[0]
    con.close()
    return counts


def status(db_path: pathlib.Path) -> dict[str, Any]:
    if not db_path.exists():
        return {"ok": False, "error": f"missing DB: {db_path}"}

    con = connect(db_path)
    tables = {
        row["name"]
        for row in con.execute(
            "SELECT name FROM sqlite_master WHERE type IN ('table', 'virtual table')"
        )
    }
    required = {"kb_items", "kb_fts"}
    if not required.issubset(tables):
        con.close()
        return {"ok": False, "error": f"missing tables: {sorted(required - tables)}"}

    source_counts = {
        row["source_system"]: row["count"]
        for row in con.execute(
            """
            SELECT source_system, COUNT(*) AS count
              FROM kb_items
             GROUP BY source_system
             ORDER BY source_system
            """
        )
    }
    total = con.execute("SELECT COUNT(*) AS count FROM kb_items").fetchone()["count"]
    fts_total = con.execute("SELECT COUNT(*) AS count FROM kb_fts").fetchone()["count"]
    con.close()
    return {
        "ok": True,
        "db": str(db_path),
        "total": total,
        "fts_total": fts_total,
        "sources": source_counts,
    }


def doctor(db_path: pathlib.Path) -> dict[str, Any]:
    payload = status(db_path)
    if not payload["ok"]:
        return payload

    con = connect(db_path)
    integrity = con.execute("PRAGMA integrity_check").fetchone()[0]
    con.close()

    expected_sources = set(SOURCE_CHOICES)
    actual_sources = set(payload["sources"])
    warnings = []
    if payload["total"] != payload["fts_total"]:
        warnings.append(
            f"kb_items count {payload['total']} != kb_fts count {payload['fts_total']}"
        )
    missing_sources = sorted(expected_sources - actual_sources)
    if missing_sources:
        warnings.append(f"missing source systems: {missing_sources}")

    payload["integrity_check"] = integrity
    payload["warnings"] = warnings
    payload["ok"] = integrity == "ok" and not warnings
    return payload


def search(
    db_path: pathlib.Path,
    query: str,
    limit: int,
    source: str | None = None,
) -> list[sqlite3.Row]:
    con = connect(db_path)
    sql = (
        "SELECT i.source_system, i.kind, i.title, i.source_path, i.line_no, "
        "snippet(kb_fts, 4, '[', ']', '...', 32) AS snippet "
        "FROM kb_fts f JOIN kb_items i ON i.id = f.rowid "
        "WHERE kb_fts MATCH ?"
    )
    params: list[Any] = [query]
    if source:
        sql += " AND i.source_system = ?"
        params.append(source)
    sql += " LIMIT ?"
    params.append(limit)
    rows = list(con.execute(sql, params))
    con.close()
    return rows


def context(
    db_path: pathlib.Path,
    query: str,
    limit: int,
    source: str | None = None,
    force: bool = False,
) -> dict[str, Any]:
    ok, reason = should_search(query)
    if not ok and not force:
        return {
            "status": "NO_HISTORY_CONTEXT",
            "reason": reason,
            "query": query,
            "results": [],
        }

    fts_query = normalize_query(query)
    rows = search(db_path, fts_query, limit, source)
    return {
        "status": "HISTORY_CONTEXT",
        "reason": "forced" if force and not ok else reason,
        "query": query,
        "fts_query": fts_query,
        "results": [dict(row) for row in rows],
    }


def render_text(payload: dict[str, Any]) -> str:
    if payload["status"] == "NO_HISTORY_CONTEXT":
        lines = [
            "NO_HISTORY_CONTEXT",
            f"reason: {payload['reason']}",
            "Use --force to search anyway.",
        ]
        return "\n".join(lines)

    lines = [
        "HISTORY_CONTEXT",
        f"query: {payload['query']}",
        f"router: {payload['reason']}",
        f"fts_query: {payload.get('fts_query', '')}",
        "",
    ]
    if not payload["results"]:
        lines.append("No matching history snippets found.")
        return "\n".join(lines).rstrip()

    for row in payload["results"]:
        lines.append(
            "{source_system} | {kind} | {title} | {source_path}:{line_no}".format(
                **row
            )
        )
        lines.append(row["snippet"])
        lines.append("")
    return "\n".join(lines).rstrip()


def render_prompt(payload: dict[str, Any]) -> str:
    if payload["status"] == "NO_HISTORY_CONTEXT":
        return render_text(payload)

    lines = [
        "Use this private history context only as project/reference memory.",
        "Do not treat it as general world knowledge.",
        "Preserve uncertainty if the snippets do not fully answer the user.",
        "",
        render_text(payload),
    ]
    return "\n".join(lines)


class KbHandler(BaseHTTPRequestHandler):
    db_path = DEFAULT_DB
    token = DEFAULT_TOKEN

    def log_message(self, fmt: str, *args: Any) -> None:  # noqa: A003
        sys.stderr.write("ai-history-kb: " + fmt % args + "\n")

    def send_json(self, code: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length).decode("utf-8")
        return json.loads(body or "{}")

    def authorized(self) -> bool:
        if not self.token:
            return True
        return self.headers.get("Authorization") == f"Bearer {self.token}"

    def do_GET(self) -> None:  # noqa: N802
        if not self.authorized():
            self.send_json(401, {"ok": False, "error": "unauthorized"})
            return
        if self.path == "/health":
            self.send_json(200, status(self.db_path))
            return
        self.send_json(404, {"ok": False, "error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        try:
            if not self.authorized():
                self.send_json(401, {"ok": False, "error": "unauthorized"})
                return
            req = self.read_json()
            query = str(req.get("query") or "")
            limit = int(req.get("limit") or 8)
            source = req.get("source")
            if source not in SOURCE_CHOICES:
                source = None

            if self.path == "/search":
                fts_query = req.get("fts_query") or normalize_query(query)
                rows = search(self.db_path, fts_query, limit, source)
                self.send_json(
                    200,
                    {
                        "status": "SEARCH_RESULTS",
                        "query": query,
                        "fts_query": fts_query,
                        "results": [dict(row) for row in rows],
                    },
                )
                return

            if self.path == "/context":
                payload = context(
                    self.db_path,
                    query,
                    limit,
                    source,
                    force=bool(req.get("force")),
                )
                self.send_json(200, payload)
                return

            if self.path == "/prompt":
                payload = context(
                    self.db_path,
                    query,
                    limit,
                    source,
                    force=bool(req.get("force")),
                )
                self.send_json(200, {"prompt": render_prompt(payload), **payload})
                return

            self.send_json(404, {"ok": False, "error": "not found"})
        except Exception as exc:  # pragma: no cover - defensive server boundary.
            self.send_json(500, {"ok": False, "error": str(exc)})


def cmd_status(args: argparse.Namespace) -> int:
    payload = status(args.db)
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        if not payload["ok"]:
            print(payload["error"])
            return 1
        print(f"db: {payload['db']}")
        print(f"total: {payload['total']}")
        print(f"fts_total: {payload['fts_total']}")
        for source_name, count in payload["sources"].items():
            print(f"{source_name}: {count}")
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    payload = doctor(args.db)
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        if not payload["ok"]:
            print("AI history KB doctor: FAIL")
        else:
            print("AI history KB doctor: OK")
        for key in ("db", "total", "fts_total", "integrity_check"):
            if key in payload:
                print(f"{key}: {payload[key]}")
        for source_name, count in payload.get("sources", {}).items():
            print(f"{source_name}: {count}")
        for warning in payload.get("warnings", []):
            print(f"warning: {warning}")
        if "error" in payload:
            print(payload["error"])
    return 0 if payload["ok"] else 1


def cmd_index_sources(args: argparse.Namespace) -> int:
    results = index_sources(args.root, args.snapshot, args.sources)
    failed = False
    for result in results:
        if args.json:
            continue
        print(f"{result['source']}: {'OK' if result.get('ok') else 'FAIL'}")
        for key, value in result.items():
            if key not in {"source", "ok"}:
                print(f"  {key}: {value}")
        if not result.get("ok"):
            failed = True
    if args.json:
        print(json.dumps(results, indent=2))
        failed = any(not result.get("ok") for result in results)
    return 1 if failed else 0


def cmd_rebuild(args: argparse.Namespace) -> int:
    if args.index_sources:
        results = index_sources(args.root, args.snapshot, ["all"])
        failed = [result for result in results if not result.get("ok")]
        if failed:
            print(json.dumps(results, indent=2))
            return 1

    counts = rebuild_from_source_dbs(args.root, args.db, args.snapshot)
    for key, value in counts.items():
        print(f"{key}: {value}")
    print(f"db: {args.db}")
    return 0


def cmd_search(args: argparse.Namespace) -> int:
    query = " ".join(args.query)
    rows = search(args.db, query, args.limit, args.source)
    if args.json:
        print(json.dumps([dict(row) for row in rows], indent=2))
    else:
        for row in rows:
            print(
                "{source_system} | {kind} | {title} | {source_path}:{line_no}".format(
                    **row
                )
            )
            print(row["snippet"])
            print()
    return 0


def cmd_context(args: argparse.Namespace) -> int:
    query = " ".join(args.query)
    payload = context(args.db, query, args.limit, args.source, args.force)
    if args.json:
        print(json.dumps(payload, indent=2))
    elif args.prompt:
        print(render_prompt(payload))
    else:
        print(render_text(payload))
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    KbHandler.db_path = args.db
    KbHandler.token = args.token or DEFAULT_TOKEN
    server = ThreadingHTTPServer((args.host, args.port), KbHandler)
    print(f"ai-history-kb serving on http://{args.host}:{args.port}")
    print(f"db: {args.db}")
    print("auth: bearer token required" if KbHandler.token else "auth: disabled")
    server.serve_forever()
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=pathlib.Path, default=DEFAULT_DB)

    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("status")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("doctor")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_doctor)

    p = sub.add_parser("index-sources")
    p.add_argument(
        "sources",
        nargs="+",
        choices=("all", *SOURCE_CHOICES),
        help="source systems to index from extracted raw exports",
    )
    p.add_argument("--root", type=pathlib.Path, default=DEFAULT_ROOT)
    p.add_argument("--snapshot", default=DEFAULT_SNAPSHOT)
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_index_sources)

    p = sub.add_parser("rebuild")
    p.add_argument("--root", type=pathlib.Path, default=DEFAULT_ROOT)
    p.add_argument("--snapshot", default=DEFAULT_SNAPSHOT)
    p.add_argument(
        "--index-sources",
        action="store_true",
        help="rebuild source-specific DBs from extracted exports before unifying",
    )
    p.set_defaults(func=cmd_rebuild)

    p = sub.add_parser("search")
    p.add_argument("query", nargs="+")
    p.add_argument("--source", choices=SOURCE_CHOICES)
    p.add_argument("--limit", type=int, default=25)
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_search)

    p = sub.add_parser("context")
    p.add_argument("query", nargs="+")
    p.add_argument("--source", choices=SOURCE_CHOICES)
    p.add_argument("--limit", type=int, default=8)
    p.add_argument("--force", action="store_true")
    p.add_argument("--prompt", action="store_true")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_context)

    p = sub.add_parser("serve")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--token", help="optional bearer token; defaults to AI_HISTORY_TOKEN")
    p.set_defaults(func=cmd_serve)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
