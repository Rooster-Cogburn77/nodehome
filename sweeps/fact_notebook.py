#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import re
import sqlite3
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from sweeps.send_digest_email import _parse_digest


ROOT = Path(__file__).resolve().parent.parent
NOTEBOOK_DIR = ROOT / "docs" / "sweeps" / "notebook"
DEFAULT_DB = NOTEBOOK_DIR / "facts.sqlite"
MOJIBAKE_MARKERS = ("â", "ð", "Ã", "œ", "€", "ā")
CHANGE_TYPES = {
    "release",
    "feature",
    "deprecation",
    "bugfix",
    "benchmark",
    "architecture",
    "compatibility",
    "breaking_change",
}
STACK_RELEVANCE = {"high", "medium", "low", "none"}
SEED_ASSUMPTIONS = (
    {
        "id": "vllm-3gpu-tensor-parallel-model-dependent",
        "entity": "vLLM",
        "claim_text": "Tensor parallelism with 3 GPUs is model-dependent and needs validation against the selected model.",
        "source": "sovereign-node-build-plan",
    },
    {
        "id": "llamacpp-backend-tensor-parallel-experimental",
        "entity": "llama.cpp",
        "claim_text": "Backend-agnostic tensor parallelism is experimental and should be watched before relying on it.",
        "source": "sweep-2026-04-10",
    },
    {
        "id": "ollama-gemma4-ampere-fa-compat",
        "entity": "Ollama",
        "claim_text": "Gemma4 on Ampere GPUs may need flash-attention compatibility checks or FA disable behavior.",
        "source": "sweep-2026-04-10",
    },
    {
        "id": "vllm-cpu-kv-offload-useful",
        "entity": "vLLM",
        "claim_text": "CPU KV cache offload may help exceed 72GB VRAM constraints by trading CPU/RAM for context or model capacity.",
        "source": "sweep-2026-04-11",
    },
    {
        "id": "hardware-3x-blower-airflow",
        "entity": "RTX 3090",
        "claim_text": "3x blower RTX 3090 airflow depends primarily on GPU exhaust path and chassis intake/exhaust support.",
        "source": "sovereign-node-build-plan",
    },
    {
        "id": "ollama-target-install-v0205",
        "entity": "Ollama",
        "claim_text": "Ollama v0.20.5 is the current target install version for Sovereign Node.",
        "source": "sweep-2026-04-10",
    },
    {
        "id": "llamacpp-split-mode-tensor-experimental",
        "entity": "llama.cpp",
        "claim_text": "llama.cpp split-mode tensor is marked experimental and directly affects 3-card serving assumptions.",
        "source": "sweep-2026-04-10",
    },
)


def digest_path(profile: str, run_date: date) -> Path:
    suffix = "" if profile == "core" else f".{profile}"
    return ROOT / "docs" / "sweeps" / "daily" / f"{run_date.isoformat()}{suffix}.md"


def repair_text(value: str) -> str:
    if not value:
        return ""
    replacements = {
        "â€”": "—",
        "â€“": "–",
        "â€™": "’",
        "â€œ": "“",
        "â€": "”",
        "â€˜": "‘",
        "ðŸ¡": "🐡",
        "ðŸŸ": "🐟",
        "â€œtrueâ€": "“true”",
        " ā€” ": " — ",
    }
    for bad, good in replacements.items():
        value = value.replace(bad, good)
    if not any(marker in value for marker in MOJIBAKE_MARKERS):
        return value
    try:
        repaired = value.encode("latin-1", errors="ignore").decode("utf-8", errors="ignore")
    except Exception:  # noqa: BLE001
        return value
    return repaired or value


def normalize_text(value: str) -> str:
    value = repair_text(value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def normalize_claim(value: str) -> str:
    value = normalize_text(value).lower()
    value = re.sub(r"https?://\S+", "", value)
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return normalize_text(value)


def fact_id(claim: str, source_url: str, source_name: str) -> str:
    normalized = f"{normalize_claim(claim)}|{source_url.strip().lower()}|{source_name.strip().lower()}"
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def topic_for_item(lane: str, title: str, source: str) -> str:
    text = f"{title} {source}".lower()
    topics = (
        ("local-inference", ("ollama", "vllm", "llama.cpp", "ggml", "local", "serving")),
        ("multi-gpu", ("multi-gpu", "multi gpu", "tensor parallel", "pipeline parallel", "split-mode", "3090")),
        ("model-release", ("qwen", "llama", "gemma", "mistral", "deepseek", "phi", "model")),
        ("hardware", ("serve", "gpu", "10gbe", "switch", "nvme", "epyc", "supermicro", "rack")),
        ("workflow", ("agent", "mcp", "claude", "codex", "obsidian", "notebook", "research", "simon", "karpathy")),
        ("x-social", ("x email", "bluesky", "twitter", "x notifications", "x: @")),
    )
    for topic, needles in topics:
        if any(needle in text for needle in needles):
            return topic
    return lane


def claim_from_item(section: str, item: dict[str, Any]) -> str:
    title = normalize_text(item.get("title", ""))
    meta = item.get("meta", {})
    why = normalize_text(meta.get("Why it matters", ""))
    if why and len(why) < 180:
        return f"{title} — {why}"
    return title


def entity_for_item(title: str, source_name: str) -> str:
    text = f"{title} {source_name}".lower()
    entities = (
        ("llama.cpp", ("llama.cpp", "ggml")),
        ("Ollama", ("ollama",)),
        ("vLLM", ("vllm",)),
        ("RTX 3090", ("3090", "rtx 3090")),
        ("CUDA", ("cuda",)),
        ("Gemma", ("gemma", "gemma4")),
        ("Qwen", ("qwen",)),
        ("ServeTheHome", ("servethehome",)),
        ("Simon Willison", ("simon willison", "simonw")),
        ("Karpathy", ("karpathy",)),
        ("Hugging Face", ("hugging face",)),
    )
    for entity, needles in entities:
        if any(needle in text for needle in needles):
            return entity
    return source_name or "unknown"


def change_type_for_item(title: str) -> str:
    text = title.lower()
    if any(token in text for token in ("breaking", "remove ", "removed", "incompatible")):
        return "breaking_change"
    if any(token in text for token in ("deprecat", "obsolete")):
        return "deprecation"
    if any(token in text for token in ("fix", "repair", "bug", "regression", "where it doesn't work")):
        return "bugfix"
    if any(token in text for token in ("benchmark", "leaderboard", "perf", "throughput", "latency", "tokens/s")):
        return "benchmark"
    if any(
        token in text
        for token in ("tensor parallel", "pipeline parallel", "split-mode", "kv cache", "offload", "architecture", "ralph loop", "notebook")
    ):
        return "architecture"
    if any(token in text for token in ("compat", "support", "cuda", "vulkan", "hip", "older gpus", "gpu")):
        return "compatibility"
    if any(token in text for token in ("release", "released", "v0.", "v1.", "v2.", "v3.", "b8")):
        return "release"
    return "feature"


def stack_relevance_for_item(title: str, source_name: str, topic: str) -> str:
    text = f"{title} {source_name}".lower()
    high_terms = (
        "tensor parallel",
        "pipeline parallel",
        "multi-gpu",
        "split-mode",
        "cuda",
        "kv cache",
        "offload",
        "3090",
        "rtx 3090",
        "pcie",
        "blower",
        "10gbe",
        "gemma4",
    )
    medium_terms = ("ollama", "vllm", "llama.cpp", "ggml", "qwen", "gemma", "nvme", "switch", "server")
    if any(term in text for term in high_terms):
        return "high"
    if any(term in text for term in medium_terms) or topic in {"local-inference", "multi-gpu", "hardware"}:
        return "medium"
    if topic in {"workflow", "model-release"}:
        return "low"
    return "none"


def implication_for_item(title: str, source_name: str, topic: str, change_type: str, stack_relevance: str) -> str:
    text = f"{title} {source_name}".lower()
    if "tensor parallel" in text or "multi-gpu" in text or "split-mode" in text:
        return "May affect 3x3090 serving topology or split strategy."
    if "kv cache" in text or "offload" in text:
        return "May let the node trade CPU/RAM for larger context or larger served models."
    if "cuda" in text:
        return "May affect CUDA throughput or compatibility on RTX 3090."
    if "gemma4" in text or "older gpus" in text:
        return "Check compatibility with Ampere GPUs before upgrading."
    if "10gbe" in text:
        return "Potential rack/networking candidate for node-adjacent infrastructure."
    if stack_relevance == "high":
        return "Directly relevant to the Sovereign Node stack."
    if change_type == "release":
        return "Check release notes before changing local serving versions."
    if topic == "workflow":
        return "Potential workflow pattern for the sweep/wiki loop."
    return ""


def needs_followup_for_item(confidence: str, stack_relevance: str, change_type: str) -> int:
    if stack_relevance == "high":
        return 1
    if confidence == "social-primary":
        return 1
    if change_type in {"breaking_change", "deprecation"}:
        return 1
    return 0


def extract_facts(markdown: str, profile: str, run_date: date) -> list[dict[str, str]]:
    digest = _parse_digest(markdown)
    facts: list[dict[str, str]] = []
    for section in digest["sections"]:
        lane = section["name"].lower()
        for item in section["items"]:
            meta = item.get("meta", {})
            claim = claim_from_item(lane, item)
            if not claim:
                continue
            source_url = normalize_text(meta.get("Link", ""))
            source_name = normalize_text(meta.get("Source", ""))
            published = normalize_text(meta.get("Published", ""))
            topic = topic_for_item(lane, item.get("title", ""), source_name)
            confidence = normalize_text(meta.get("Confidence", "")) or "unknown"
            title = item.get("title", "")
            entity = entity_for_item(title, source_name)
            change_type = change_type_for_item(title)
            stack_relevance = stack_relevance_for_item(title, source_name, topic)
            implication = implication_for_item(title, source_name, topic, change_type, stack_relevance)
            needs_followup = str(needs_followup_for_item(confidence, stack_relevance, change_type))
            facts.append(
                {
                    "id": fact_id(claim, source_url, source_name),
                    "claim_text": claim,
                    "claim_norm": normalize_claim(claim),
                    "source_url": source_url,
                    "source_name": source_name,
                    "published_at": published,
                    "topic": topic,
                    "lane": lane,
                    "confidence": confidence,
                    "profile": profile,
                    "digest_date": run_date.isoformat(),
                    "entity": entity,
                    "change_type": change_type,
                    "implication": implication,
                    "stack_relevance": stack_relevance,
                    "needs_followup": needs_followup,
                }
            )
    return facts


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS facts (
            id TEXT PRIMARY KEY,
            claim_text TEXT NOT NULL,
            claim_norm TEXT NOT NULL,
            source_url TEXT NOT NULL,
            source_name TEXT NOT NULL,
            published_at TEXT NOT NULL,
            topic TEXT NOT NULL,
            lane TEXT NOT NULL,
            confidence TEXT NOT NULL,
            profile TEXT NOT NULL,
            first_seen TEXT NOT NULL,
            last_seen TEXT NOT NULL,
            seen_count INTEGER NOT NULL DEFAULT 1,
            entity TEXT,
            change_type TEXT CHECK (change_type IS NULL OR change_type IN ('release', 'feature', 'deprecation', 'bugfix', 'benchmark', 'architecture', 'compatibility', 'breaking_change')),
            implication TEXT,
            stack_relevance TEXT CHECK (stack_relevance IS NULL OR stack_relevance IN ('high', 'medium', 'low', 'none')),
            needs_followup INTEGER CHECK (needs_followup IS NULL OR needs_followup IN (0, 1))
        );

        CREATE INDEX IF NOT EXISTS idx_facts_topic ON facts(topic);
        CREATE INDEX IF NOT EXISTS idx_facts_lane ON facts(lane);
        CREATE INDEX IF NOT EXISTS idx_facts_source ON facts(source_name);
        CREATE INDEX IF NOT EXISTS idx_facts_last_seen ON facts(last_seen);

        CREATE TABLE IF NOT EXISTS ingests (
            digest_path TEXT PRIMARY KEY,
            profile TEXT NOT NULL,
            digest_date TEXT NOT NULL,
            ingested_at TEXT NOT NULL,
            fact_count INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS fact_actions (
            fact_id TEXT PRIMARY KEY,
            status TEXT NOT NULL CHECK (status IN ('open', 'reviewing', 'done', 'ignored')),
            note TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (fact_id) REFERENCES facts(id)
        );

        CREATE INDEX IF NOT EXISTS idx_fact_actions_status ON fact_actions(status);

        CREATE TABLE IF NOT EXISTS assumptions (
            id TEXT PRIMARY KEY,
            entity TEXT NOT NULL,
            claim_text TEXT NOT NULL,
            status TEXT NOT NULL CHECK (status IN ('active', 'revised', 'retired')),
            source TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_assumptions_entity ON assumptions(entity);
        CREATE INDEX IF NOT EXISTS idx_assumptions_status ON assumptions(status);
        """
    )
    existing_columns = {row[1] for row in conn.execute("PRAGMA table_info(facts)").fetchall()}
    migrations = {
        "entity": "ALTER TABLE facts ADD COLUMN entity TEXT",
        "change_type": (
            "ALTER TABLE facts ADD COLUMN change_type TEXT "
            "CHECK (change_type IS NULL OR change_type IN ('release', 'feature', 'deprecation', "
            "'bugfix', 'benchmark', 'architecture', 'compatibility', 'breaking_change'))"
        ),
        "implication": "ALTER TABLE facts ADD COLUMN implication TEXT",
        "stack_relevance": (
            "ALTER TABLE facts ADD COLUMN stack_relevance TEXT "
            "CHECK (stack_relevance IS NULL OR stack_relevance IN ('high', 'medium', 'low', 'none'))"
        ),
        "needs_followup": "ALTER TABLE facts ADD COLUMN needs_followup INTEGER CHECK (needs_followup IS NULL OR needs_followup IN (0, 1))",
    }
    for column, sql in migrations.items():
        if column not in existing_columns:
            conn.execute(sql)
    conn.executescript(
        """
        CREATE INDEX IF NOT EXISTS idx_facts_entity ON facts(entity);
        CREATE INDEX IF NOT EXISTS idx_facts_change_type ON facts(change_type);
        CREATE INDEX IF NOT EXISTS idx_facts_stack_relevance ON facts(stack_relevance);
        """
    )
    seed_assumptions(conn)
    conn.commit()


def seed_assumptions(conn: sqlite3.Connection) -> None:
    now = datetime.now(UTC).isoformat()
    for assumption in SEED_ASSUMPTIONS:
        conn.execute(
            """
            INSERT INTO assumptions (id, entity, claim_text, status, source, created_at, updated_at)
            VALUES (?, ?, ?, 'active', ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                entity = excluded.entity,
                claim_text = excluded.claim_text,
                source = excluded.source,
                updated_at = excluded.updated_at
            """,
            (
                assumption["id"],
                assumption["entity"],
                assumption["claim_text"],
                assumption["source"],
                now,
                now,
            ),
        )


def upsert_facts(conn: sqlite3.Connection, facts: list[dict[str, str]], seen_at: str) -> tuple[int, int]:
    inserted = 0
    updated = 0
    for fact in facts:
        cur = conn.execute("SELECT seen_count FROM facts WHERE id = ?", (fact["id"],))
        row = cur.fetchone()
        if row:
            conn.execute(
                """
                UPDATE facts
                SET claim_text = ?, published_at = ?, topic = ?, lane = ?, confidence = ?,
                    profile = ?, entity = ?, change_type = ?, implication = ?, stack_relevance = ?,
                    needs_followup = ?, last_seen = ?, seen_count = seen_count + 1
                WHERE id = ?
                """,
                (
                    fact["claim_text"],
                    fact["published_at"],
                    fact["topic"],
                    fact["lane"],
                    fact["confidence"],
                    fact["profile"],
                    fact["entity"],
                    fact["change_type"],
                    fact["implication"],
                    fact["stack_relevance"],
                    int(fact["needs_followup"]),
                    seen_at,
                    fact["id"],
                ),
            )
            updated += 1
        else:
            conn.execute(
                """
                INSERT INTO facts (
                    id, claim_text, claim_norm, source_url, source_name, published_at,
                    topic, lane, confidence, profile, first_seen, last_seen, seen_count,
                    entity, change_type, implication, stack_relevance, needs_followup
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?, ?)
                """,
                (
                    fact["id"],
                    fact["claim_text"],
                    fact["claim_norm"],
                    fact["source_url"],
                    fact["source_name"],
                    fact["published_at"],
                    fact["topic"],
                    fact["lane"],
                    fact["confidence"],
                    fact["profile"],
                    seen_at,
                    seen_at,
                    fact["entity"],
                    fact["change_type"],
                    fact["implication"],
                    fact["stack_relevance"],
                    int(fact["needs_followup"]),
                ),
            )
            inserted += 1
    conn.commit()
    return inserted, updated


def record_ingest(conn: sqlite3.Connection, path: Path, profile: str, run_date: date, seen_at: str, fact_count: int) -> None:
    conn.execute(
        """
        INSERT INTO ingests (digest_path, profile, digest_date, ingested_at, fact_count)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(digest_path) DO UPDATE SET
            ingested_at = excluded.ingested_at,
            fact_count = excluded.fact_count
        """,
        (str(path), profile, run_date.isoformat(), seen_at, fact_count),
    )
    conn.commit()


def print_recent(conn: sqlite3.Connection, limit: int) -> None:
    rows = conn.execute(
        """
        SELECT topic, source_name, claim_text
        FROM facts
        ORDER BY last_seen DESC, source_name ASC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    for topic, source_name, claim_text in rows:
        print(f"[{topic}] {source_name}: {claim_text}")


def print_query(conn: sqlite3.Connection, topic: str, source: str, limit: int) -> None:
    where = []
    params: list[str | int] = []
    if topic:
        where.append("topic = ?")
        params.append(topic)
    if source:
        where.append("source_name LIKE ?")
        params.append(f"%{source}%")
    sql = "SELECT topic, source_name, claim_text FROM facts"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY last_seen DESC, source_name ASC LIMIT ?"
    params.append(limit)
    rows = conn.execute(sql, params).fetchall()
    for row_topic, source_name, claim_text in rows:
        print(f"[{row_topic}] {source_name}: {claim_text}")


def followup_reason(row: sqlite3.Row) -> str:
    reasons = []
    if row["needs_followup"]:
        reasons.append("needs_followup")
    if row["stack_relevance"] == "high":
        reasons.append("stack:high")
    if row["change_type"] in {"breaking_change", "deprecation", "architecture"}:
        reasons.append(f"change:{row['change_type']}")
    if row["confidence"] == "social-primary":
        reasons.append("social-primary")
    return ", ".join(reasons) or "review"


def followup_rows(conn: sqlite3.Connection, profile: str = "all", limit: int = 20) -> list[sqlite3.Row]:
    conn.row_factory = sqlite3.Row
    profile_clause = ""
    params: list[str | int] = []
    if profile != "all":
        profile_clause = "AND profile = ?"
        params.append(profile)
    params.append(limit)
    return conn.execute(
        f"""
        SELECT
            facts.id,
            entity,
            change_type,
            stack_relevance,
            needs_followup,
            confidence,
            topic,
            source_name,
            source_url,
            claim_text,
            implication,
            seen_count,
            last_seen,
            COALESCE(fact_actions.status, 'open') AS action_status,
            COALESCE(fact_actions.note, '') AS action_note
        FROM facts
        LEFT JOIN fact_actions ON fact_actions.fact_id = facts.id
        WHERE (
            needs_followup = 1
            OR stack_relevance = 'high'
            OR change_type IN ('breaking_change', 'deprecation', 'architecture')
        )
        AND COALESCE(fact_actions.status, 'open') NOT IN ('done', 'ignored')
        {profile_clause}
        ORDER BY
            COALESCE(entity, 'unknown') ASC,
            CASE stack_relevance WHEN 'high' THEN 0 WHEN 'medium' THEN 1 WHEN 'low' THEN 2 ELSE 3 END,
            CASE change_type WHEN 'breaking_change' THEN 0 WHEN 'deprecation' THEN 1 WHEN 'architecture' THEN 2 ELSE 3 END,
            seen_count DESC,
            last_seen DESC
        LIMIT ?
        """,
        params,
    ).fetchall()


def print_followup(conn: sqlite3.Connection, profile: str, limit: int) -> None:
    current_entity = None
    for row in followup_rows(conn, profile, limit):
        entity = row["entity"] or "unknown"
        if entity != current_entity:
            print(f"\n[{entity}]")
            current_entity = entity
        detail = f"{row['id']} / {row['change_type']} / stack:{row['stack_relevance']} / {followup_reason(row)}"
        print(f"- {detail}: {row['claim_text']}")
        if row["implication"]:
            print(f"  Implication: {row['implication']}")
        if row["source_url"]:
            print(f"  Source: {row['source_url']}")


def mark_action(conn: sqlite3.Connection, fact_id: str, status: str, note: str) -> None:
    now = datetime.now(UTC).isoformat()
    if status == "open" and note.lower() == "reset":
        note = ""
    cur = conn.execute("SELECT id FROM facts WHERE id = ?", (fact_id,))
    row = cur.fetchone()
    if row:
        fact_id = row[0]
    else:
        rows = conn.execute("SELECT id FROM facts WHERE id LIKE ? ORDER BY id", (f"{fact_id}%",)).fetchall()
        if not rows:
            raise RuntimeError(f"Unknown fact_id: {fact_id}")
        if len(rows) > 1:
            matches = ", ".join(row[0] for row in rows[:5])
            raise RuntimeError(f"Ambiguous fact_id prefix: {fact_id}. Matches: {matches}")
        fact_id = rows[0][0]
    if not fact_id:
        raise RuntimeError(f"Unknown fact_id: {fact_id}")
    conn.execute(
        """
        INSERT INTO fact_actions (fact_id, status, note, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(fact_id) DO UPDATE SET
            status = excluded.status,
            note = excluded.note,
            updated_at = excluded.updated_at
        """,
        (fact_id, status, note, now, now),
    )
    conn.commit()


def print_actions(conn: sqlite3.Connection, limit: int) -> None:
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT fact_actions.fact_id, fact_actions.status, fact_actions.note, fact_actions.updated_at,
               facts.entity, facts.change_type, facts.stack_relevance, facts.claim_text
        FROM fact_actions
        JOIN facts ON facts.id = fact_actions.fact_id
        ORDER BY fact_actions.updated_at DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    for row in rows:
        print(
            f"- {row['fact_id']} [{row['status']}] "
            f"{row['entity'] or 'unknown'} / {row['change_type']} / stack:{row['stack_relevance']}: "
            f"{row['claim_text']}"
        )
        if row["note"]:
            print(f"  Note: {row['note']}")


def assumption_rows(conn: sqlite3.Connection, limit: int = 20) -> list[sqlite3.Row]:
    conn.row_factory = sqlite3.Row
    return conn.execute(
        """
        SELECT id, entity, claim_text, status, source, updated_at
        FROM assumptions
        ORDER BY entity ASC, id ASC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()


def print_assumptions(conn: sqlite3.Connection, limit: int) -> None:
    for row in assumption_rows(conn, limit):
        print(f"- {row['id']} [{row['status']}] {row['entity']}: {row['claim_text']}")
        if row["source"]:
            print(f"  Source: {row['source']}")


def assumption_pressure_rows(
    conn: sqlite3.Connection,
    profile: str = "all",
    limit: int = 20,
    start: str = "",
    end: str = "",
) -> list[sqlite3.Row]:
    conn.row_factory = sqlite3.Row
    where = [
        "assumptions.status = 'active'",
        "("
        "(facts.stack_relevance = 'high' AND facts.change_type IN ('architecture', 'compatibility', 'breaking_change', 'deprecation')) "
        "OR (assumptions.id = 'ollama-target-install-v0205' AND facts.change_type = 'release' "
        "AND facts.claim_text NOT LIKE 'v0.20.5%' AND facts.claim_text NOT LIKE 'v0.20.4%' "
        "AND facts.claim_text NOT LIKE 'v0.20.3%')"
        ")",
        "COALESCE(fact_actions.status, 'open') NOT IN ('done', 'ignored')",
    ]
    params: list[str | int] = []
    if profile != "all":
        where.append("facts.profile = ?")
        params.append(profile)
    if start and end:
        where.append("substr(facts.first_seen, 1, 10) BETWEEN ? AND ?")
        params.extend([start, end])
    params.append(limit)
    return conn.execute(
        f"""
        SELECT
            GROUP_CONCAT(assumptions.id, ', ') AS assumption_ids,
            GROUP_CONCAT(assumptions.claim_text, ' || ') AS assumption_claims,
            MIN(assumptions.entity) AS assumption_entity,
            facts.id AS fact_id,
            facts.claim_text AS fact_claim,
            facts.source_name,
            facts.source_url,
            facts.topic,
            facts.change_type,
            facts.stack_relevance,
            facts.implication,
            facts.seen_count,
            facts.last_seen,
            CASE
                WHEN facts.change_type = 'breaking_change' THEN 'act'
                WHEN facts.change_type = 'deprecation' THEN 'act'
                WHEN facts.change_type = 'architecture' AND facts.stack_relevance = 'high' THEN 'review'
                WHEN facts.change_type = 'compatibility' AND facts.stack_relevance = 'high' THEN 'review'
                ELSE 'watch'
            END AS severity,
            COALESCE(fact_actions.status, 'open') AS action_status
        FROM assumptions
        JOIN facts ON facts.entity = assumptions.entity
        LEFT JOIN fact_actions ON fact_actions.fact_id = facts.id
        WHERE {" AND ".join(where)}
        GROUP BY
            facts.id,
            facts.claim_text,
            facts.source_name,
            facts.source_url,
            facts.topic,
            facts.change_type,
            facts.stack_relevance,
            facts.implication,
            facts.seen_count,
            facts.last_seen,
            fact_actions.status
        ORDER BY
            CASE severity WHEN 'act' THEN 0 WHEN 'review' THEN 1 ELSE 2 END,
            CASE facts.change_type WHEN 'release' THEN 0 WHEN 'architecture' THEN 1 WHEN 'breaking_change' THEN 2 WHEN 'deprecation' THEN 3 WHEN 'compatibility' THEN 4 ELSE 5 END,
            facts.seen_count DESC,
            facts.last_seen DESC
        LIMIT ?
        """,
        params,
    ).fetchall()


def print_assumption_check(conn: sqlite3.Connection, profile: str, limit: int) -> None:
    for row in assumption_pressure_rows(conn, profile, limit):
        print(f"\n[{row['severity']}] {row['assumption_entity']} / pressures: {row['assumption_ids']}")
        detail = f"{row['fact_id']} / {row['change_type']} / stack:{row['stack_relevance']}"
        print(f"- {detail}: {row['fact_claim']}")
        for claim in row["assumption_claims"].split(" || "):
            print(f"  Assumption: {claim}")
        if row["implication"]:
            print(f"  Implication: {row['implication']}")
        if row["source_url"]:
            print(f"  Source: {row['source_url']}")


def print_stats(conn: sqlite3.Connection) -> None:
    total = conn.execute("SELECT COUNT(*) FROM facts").fetchone()[0]
    print(f"facts: {total}")
    print("topics:")
    for topic, count in conn.execute("SELECT topic, COUNT(*) FROM facts GROUP BY topic ORDER BY COUNT(*) DESC, topic"):
        print(f"- {topic}: {count}")
    print("stack relevance:")
    for relevance, count in conn.execute(
        "SELECT COALESCE(stack_relevance, 'unknown'), COUNT(*) FROM facts GROUP BY stack_relevance ORDER BY COUNT(*) DESC"
    ):
        print(f"- {relevance}: {count}")
    print("change types:")
    for change_type, count in conn.execute(
        "SELECT COALESCE(change_type, 'unknown'), COUNT(*) FROM facts GROUP BY change_type ORDER BY COUNT(*) DESC"
    ):
        print(f"- {change_type}: {count}")
    print("sources:")
    for source_name, count in conn.execute(
        "SELECT source_name, COUNT(*) FROM facts GROUP BY source_name ORDER BY COUNT(*) DESC, source_name LIMIT 12"
    ):
        print(f"- {source_name}: {count}")


def backfill(conn: sqlite3.Connection, profile: str, limit: int) -> tuple[int, int, int]:
    daily_dir = ROOT / "docs" / "sweeps" / "daily"
    paths = sorted(daily_dir.glob("*.md"))
    if profile != "all":
        suffix = "" if profile == "core" else f".{profile}"
        paths = [path for path in paths if path.stem.endswith(suffix)]
        if profile == "core":
            paths = [path for path in paths if "." not in path.stem]
    if limit:
        paths = paths[-limit:]

    total_inserted = 0
    total_updated = 0
    processed = 0
    for path in paths:
        name = path.stem
        parts = name.split(".", 1)
        run_date = date.fromisoformat(parts[0])
        path_profile = parts[1] if len(parts) > 1 else "core"
        facts = extract_facts(path.read_text(encoding="utf-8"), path_profile, run_date)
        seen_at = datetime.now(UTC).isoformat()
        inserted, updated = upsert_facts(conn, facts, seen_at)
        record_ingest(conn, path, path_profile, run_date, seen_at, len(facts))
        total_inserted += inserted
        total_updated += updated
        processed += 1
    return processed, total_inserted, total_updated


def repair_existing_text(conn: sqlite3.Connection) -> dict[str, int]:
    conn.row_factory = sqlite3.Row
    fact_rows = conn.execute(
        """
        SELECT id, claim_text, claim_norm, source_name, entity, implication
        FROM facts
        """
    ).fetchall()
    fact_updates = 0
    for row in fact_rows:
        claim_text = normalize_text(row["claim_text"])
        source_name = normalize_text(row["source_name"])
        entity = normalize_text(row["entity"])
        implication = normalize_text(row["implication"])
        claim_norm = normalize_claim(claim_text)
        if (
            claim_text != row["claim_text"]
            or claim_norm != row["claim_norm"]
            or source_name != row["source_name"]
            or entity != row["entity"]
            or implication != row["implication"]
        ):
            conn.execute(
                """
                UPDATE facts
                SET claim_text = ?, claim_norm = ?, source_name = ?, entity = ?, implication = ?
                WHERE id = ?
                """,
                (claim_text, claim_norm, source_name, entity, implication, row["id"]),
            )
            fact_updates += 1

    assumption_rows = conn.execute("SELECT id, entity, claim_text FROM assumptions").fetchall()
    assumption_updates = 0
    for row in assumption_rows:
        entity = normalize_text(row["entity"])
        claim_text = normalize_text(row["claim_text"])
        if entity != row["entity"] or claim_text != row["claim_text"]:
            conn.execute(
                "UPDATE assumptions SET entity = ?, claim_text = ? WHERE id = ?",
                (entity, claim_text, row["id"]),
            )
            assumption_updates += 1

    conn.commit()
    return {"facts": fact_updates, "assumptions": assumption_updates}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the sweep fact notebook from daily digest markdown.")
    parser.add_argument("--input", dest="input_path", help="Explicit digest markdown path.")
    parser.add_argument("--profile", choices=("core", "extended", "all"), default="core")
    parser.add_argument("--date", dest="run_date", help="Digest date in YYYY-MM-DD format.")
    parser.add_argument("--db", default=str(DEFAULT_DB), help="SQLite notebook path.")
    parser.add_argument("--dry-run", action="store_true", help="Extract facts without writing SQLite.")
    parser.add_argument("--recent", type=int, default=0, help="Print recent facts after ingest.")
    parser.add_argument("--backfill", action="store_true", help="Ingest existing daily digest markdown files.")
    parser.add_argument("--limit", type=int, default=0, help="Limit rows for query/backfill commands.")
    parser.add_argument("--topic", default="", help="Print facts for a topic.")
    parser.add_argument("--source", default="", help="Print facts matching a source name.")
    parser.add_argument("--stats", action="store_true", help="Print fact notebook counts.")
    parser.add_argument("--followup", action="store_true", help="Print actionable follow-up queue.")
    parser.add_argument("--mark", dest="mark_fact_id", help="Mark a fact action by fact_id.")
    parser.add_argument("--review", dest="review_fact_id", help="Mark a fact as reviewing by fact_id.")
    parser.add_argument("--done", dest="done_fact_id", help="Mark a fact as done by fact_id.")
    parser.add_argument("--ignore", dest="ignore_fact_id", help="Mark a fact as ignored by fact_id.")
    parser.add_argument("--status", choices=("open", "reviewing", "done", "ignored"), default="reviewing")
    parser.add_argument("--note", default="", help="Action note for --mark.")
    parser.add_argument("--actions", action="store_true", help="Print recent fact actions.")
    parser.add_argument("--assumptions", action="store_true", help="Print active seed assumptions.")
    parser.add_argument("--assumption-check", action="store_true", help="Print high-relevance facts pressuring active assumptions.")
    parser.add_argument("--pressure", action="store_true", help="Alias for --assumption-check.")
    parser.add_argument("--repair-text", action="store_true", help="Repair common mojibake in existing notebook rows.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    db_path = Path(args.db)
    if not db_path.is_absolute():
        db_path = ROOT / db_path
    conn = connect(db_path)
    init_db(conn)

    if args.backfill:
        processed, inserted, updated = backfill(conn, args.profile, args.limit)
        print({"digests": processed, "inserted": inserted, "updated": updated, "db": str(db_path)})
        conn.close()
        return 0

    if args.stats:
        print_stats(conn)
        conn.close()
        return 0

    if args.followup:
        print_followup(conn, args.profile, args.limit or 20)
        conn.close()
        return 0

    if args.mark_fact_id:
        mark_action(conn, args.mark_fact_id, args.status, args.note)
        print({"marked": args.mark_fact_id, "status": args.status})
        conn.close()
        return 0

    action_aliases = (
        (args.review_fact_id, "reviewing"),
        (args.done_fact_id, "done"),
        (args.ignore_fact_id, "ignored"),
    )
    for fact_id, status in action_aliases:
        if fact_id:
            mark_action(conn, fact_id, status, args.note)
            print({"marked": fact_id, "status": status})
            conn.close()
            return 0

    if args.actions:
        print_actions(conn, args.limit or 20)
        conn.close()
        return 0

    if args.assumptions:
        print_assumptions(conn, args.limit or 20)
        conn.close()
        return 0

    if args.assumption_check or args.pressure:
        print_assumption_check(conn, args.profile, args.limit or 20)
        conn.close()
        return 0

    if args.repair_text:
        result = repair_existing_text(conn)
        print({"repaired": result, "db": str(db_path)})
        conn.close()
        return 0

    if args.topic or args.source:
        print_query(conn, args.topic, args.source, args.limit or 20)
        conn.close()
        return 0

    run_date = date.fromisoformat(args.run_date) if args.run_date else date.today()
    path = Path(args.input_path) if args.input_path else digest_path(args.profile, run_date)
    if not path.is_absolute():
        path = ROOT / path
    if not path.exists():
        raise FileNotFoundError(path)

    markdown = path.read_text(encoding="utf-8")
    facts = extract_facts(markdown, args.profile, run_date)
    if args.dry_run:
        print({"facts": len(facts), "input": str(path)})
        for fact in facts[:10]:
            print(f"[{fact['topic']}] {fact['claim_text']}")
        conn.close()
        return 0

    seen_at = datetime.now(UTC).isoformat()
    inserted, updated = upsert_facts(conn, facts, seen_at)
    record_ingest(conn, path, args.profile, run_date, seen_at, len(facts))
    print({"facts": len(facts), "inserted": inserted, "updated": updated, "db": str(db_path)})
    if args.recent:
        print_recent(conn, args.recent)
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
