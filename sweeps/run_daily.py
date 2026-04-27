#!/usr/bin/env python3
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import os
import random
import time
import re
import sys
import threading
import urllib.error
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from email.utils import parsedate_to_datetime
from html import unescape
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
SWEEPS_DIR = ROOT / "docs" / "sweeps"
DAILY_DIR = SWEEPS_DIR / "daily"
WEEKLY_DIR = SWEEPS_DIR / "weekly"
VALIDATION_DIR = SWEEPS_DIR / "validation"
HEALTH_DIR = SWEEPS_DIR / "health"
STATE_DIR = SWEEPS_DIR / "state"
INBOX_DIR = SWEEPS_DIR / "inbox"
DEGRADED_PATH = SWEEPS_DIR / "health" / "degraded_sources.json"
RAW_DIR = ROOT / "docs" / "wiki" / "raw"
MANIFEST_PATH = ROOT / "sweeps" / "sources.json"
USER_AGENT = "SovereignNodeSweep/0.1 (+local)"
OPENRSS_CONCURRENCY = 2
OPENRSS_DELAY_RANGE = (2.0, 5.0)
_openrss_semaphore = threading.Semaphore(OPENRSS_CONCURRENCY)
QUARANTINE_THRESHOLD = 3
QUARANTINE_COOLDOWN_HOURS = 12
MAX_ITEM_AGE_DAYS = 14
GITHUB_ACTIVITY_COLLAPSE_THRESHOLD = 3
LLAMACPP_COMMIT_KEYWORDS = (
    "cuda",
    "vulkan",
    "hip",
    "tensor parallel",
    "split-mode tensor",
    "multi-gpu",
    "quant",
    "qwen",
    "gemma",
    "reasoning",
    "fuse",
    "backend-agnostic",
)


def openrss_fallback_enabled() -> bool:
    raw = os.getenv("SWEEP_OPENRSS_FALLBACK_ENABLED", "").strip().lower()
    if raw in {"1", "true", "yes", "on"}:
        return True
    if raw in {"0", "false", "no", "off"}:
        return False
    return not bool(os.getenv("X_BEARER_TOKEN", "").strip())


@dataclass
class Source:
    id: str
    name: str
    lane: str
    kind: str
    url: str
    confidence: str
    profile: str = "core"
    timeout_seconds: int = 20
    retries: int = 2
    x_username: str = ""
    bluesky_handle: str = ""


def ensure_dirs() -> None:
    for directory in (DAILY_DIR, WEEKLY_DIR, VALIDATION_DIR, HEALTH_DIR, STATE_DIR, INBOX_DIR):
        directory.mkdir(parents=True, exist_ok=True)


def read_manifest() -> list[Source]:
    data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return [Source(**item) for item in data["sources"]]


def fetch_url(url: str, timeout_seconds: int) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        return response.read()


def fetch_url_with_retry(
    url: str,
    timeout_seconds: int,
    attempts: int = 2,
    delay_seconds: float = 1.5,
) -> bytes:
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            return fetch_url(url, timeout_seconds)
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            if attempt < attempts - 1:
                time.sleep(delay_seconds)
    assert last_error is not None
    raise last_error


def fetch_x_json(path: str, params: dict[str, str]) -> dict[str, Any]:
    token = os.getenv("X_BEARER_TOKEN", "").strip()
    if not token:
        raise RuntimeError("X_BEARER_TOKEN is not set")
    url = f"https://api.x.com{path}"
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "User-Agent": USER_AGENT,
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def username_from_source(source: Source) -> str:
    if source.x_username:
        return source.x_username.lstrip("@")
    match = re.search(r"x\.com/([^/?#]+)", source.url)
    if match:
        return match.group(1)
    return source.name.replace("X:", "").strip().lstrip("@")


def fetch_x_user_timeline(source: Source) -> list[dict[str, str]]:
    username = username_from_source(source)
    user = fetch_x_json(
        f"/2/users/by/username/{urllib.parse.quote(username)}",
        {"user.fields": "username,name"},
    )
    user_id = user.get("data", {}).get("id", "")
    if not user_id:
        raise RuntimeError(f"X user lookup returned no id for @{username}")

    timeline = fetch_x_json(
        f"/2/users/{user_id}/tweets",
        {
            "max_results": "20",
            "tweet.fields": "created_at,conversation_id,public_metrics,referenced_tweets",
        },
    )
    items = []
    for tweet in timeline.get("data", []):
        tweet_id = str(tweet.get("id", ""))
        text = normalize_text(tweet.get("text", ""))
        if not tweet_id or not text:
            continue
        items.append(
            {
                "id": tweet_id,
                "title": text,
                "link": f"https://x.com/{username}/status/{tweet_id}",
                "published": normalize_text(tweet.get("created_at", "")),
                "summary": text,
            }
        )
    return items


def bluesky_handle_from_source(source: Source) -> str:
    if source.bluesky_handle:
        return source.bluesky_handle
    return source.url.replace("at://", "").strip()


def fetch_bluesky_author_feed(source: Source) -> list[dict[str, str]]:
    handle = bluesky_handle_from_source(source)
    params = urllib.parse.urlencode({"actor": handle, "limit": "30", "filter": "posts_with_replies"})
    url = f"https://public.api.bsky.app/xrpc/app.bsky.feed.getAuthorFeed?{params}"
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=source.timeout_seconds) as response:
        data = json.loads(response.read().decode("utf-8"))

    items = []
    for row in data.get("feed", []):
        post = row.get("post", {})
        record = post.get("record", {})
        external = post.get("embed", {}).get("external", {})
        text = normalize_text(
            record.get("text", "")
            or external.get("title", "")
            or external.get("description", "")
            or record.get("bridgyOriginalText", "")
        )
        uri = post.get("uri", "")
        post_id = uri.rsplit("/", 1)[-1] if uri else ""
        if not text or not post_id:
            continue
        link = external.get("uri") or f"https://bsky.app/profile/{handle}/post/{post_id}"
        items.append(
            {
                "id": uri or f"{handle}:{post_id}",
                "title": text,
                "link": link,
                "published": normalize_text(record.get("createdAt", "")),
                "summary": text,
            }
        )
    return items


def resolve_url(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT}, method="HEAD")
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return response.geturl()
    except Exception:  # noqa: BLE001
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(request, timeout=15) as response:
            return response.geturl()


def normalize_text(value: str | None) -> str:
    if not value:
        return ""
    value = unescape(value)
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def _sanitize_xml(xml_bytes: bytes) -> bytes:
    """Strip bytes that are invalid in XML 1.0 (control chars except tab/newline/cr)."""
    return bytes(b for b in xml_bytes if b in (0x09, 0x0A, 0x0D) or 0x20 <= b)


def parse_feed(xml_bytes: bytes) -> list[dict[str, str]]:
    root = ET.fromstring(_sanitize_xml(xml_bytes))
    items: list[dict[str, str]] = []

    if root.tag.endswith("rss"):
        channel = root.find("channel")
        if channel is None:
            return items
        for item in channel.findall("item"):
            title = normalize_text(item.findtext("title"))
            link = normalize_text(item.findtext("link"))
            guid = normalize_text(item.findtext("guid")) or link or title
            published = normalize_text(item.findtext("pubDate"))
            summary = normalize_text(item.findtext("description"))
            items.append(
                {
                    "id": guid,
                    "title": title or "(untitled)",
                    "link": link,
                    "published": published,
                    "summary": summary,
                }
            )
        return items

    ns = {"atom": "http://www.w3.org/2005/Atom"}
    for entry in root.findall("atom:entry", ns):
        title = normalize_text(entry.findtext("atom:title", default="", namespaces=ns))
        entry_id = normalize_text(entry.findtext("atom:id", default="", namespaces=ns))
        published = normalize_text(
            entry.findtext("atom:updated", default="", namespaces=ns)
            or entry.findtext("atom:published", default="", namespaces=ns)
        )
        summary = normalize_text(
            entry.findtext("atom:summary", default="", namespaces=ns)
            or entry.findtext("atom:content", default="", namespaces=ns)
        )
        link = ""
        for link_node in entry.findall("atom:link", ns):
            href = link_node.attrib.get("href", "").strip()
            rel = link_node.attrib.get("rel", "alternate")
            if href and rel == "alternate":
                link = href
                break
            if href and not link:
                link = href
        items.append(
            {
                "id": entry_id or link or title,
                "title": title or "(untitled)",
                "link": link,
                "published": published,
                "summary": summary,
            }
        )
    return items


def parse_page(html_bytes: bytes, url: str) -> list[dict[str, str]]:
    html = html_bytes.decode("utf-8", errors="ignore")
    title_match = re.search(r"<title>(.*?)</title>", html, flags=re.IGNORECASE | re.DOTALL)
    title = normalize_text(title_match.group(1) if title_match else url)
    text = normalize_text(html)
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    snippet = text[:280]
    return [
        {
            "id": digest,
            "title": title,
            "link": url,
            "published": "",
            "summary": snippet,
        }
    ]


def read_local_jsonl(source: Source) -> list[dict[str, str]]:
    path = Path(source.url)
    if not path.is_absolute():
        path = ROOT / path
    if not path.exists():
        return []

    items: list[dict[str, str]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            raw = json.loads(line)
        except json.JSONDecodeError:
            continue
        item_id = normalize_text(str(raw.get("id", "")))
        title = normalize_text(str(raw.get("title", "")))
        link = normalize_text(str(raw.get("link", "")))
        if not item_id or not title:
            continue
        items.append(
            {
                "id": item_id,
                "title": title,
                "link": link,
                "published": normalize_text(str(raw.get("published", ""))),
                "summary": normalize_text(str(raw.get("summary", ""))) or title,
            }
        )
    return items


def fetch_page_title(url: str) -> str:
    try:
        body = fetch_url_with_retry(url, timeout_seconds=10, attempts=1)
    except Exception:  # noqa: BLE001
        return ""
    html = body.decode("utf-8", errors="ignore")
    title_match = re.search(r"<title>(.*?)</title>", html, flags=re.IGNORECASE | re.DOTALL)
    if not title_match:
        return ""
    return normalize_text(title_match.group(1))


def fetch_page_description(url: str) -> str:
    try:
        body = fetch_url_with_retry(url, timeout_seconds=10, attempts=1)
    except Exception:  # noqa: BLE001
        return ""
    html = body.decode("utf-8", errors="ignore")
    patterns = [
        r'<meta[^>]+name=["\']description["\'][^>]+content=["\'](.*?)["\']',
        r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\'](.*?)["\']',
    ]
    for pattern in patterns:
        match = re.search(pattern, html, flags=re.IGNORECASE | re.DOTALL)
        if match:
            return normalize_text(match.group(1))[:280]
    return ""


def fetch_source(source: Source) -> dict[str, Any]:
    is_openrss = "openrss.org" in source.url and source.kind != "x_user"
    if is_openrss:
        _openrss_semaphore.acquire()
        time.sleep(random.uniform(*OPENRSS_DELAY_RANGE))
    try:
        if source.kind == "x_user":
            items = fetch_x_user_timeline(source)
        elif source.kind == "bluesky":
            items = fetch_bluesky_author_feed(source)
        elif source.kind == "local_jsonl":
            items = read_local_jsonl(source)
        else:
            body = fetch_url_with_retry(source.url, timeout_seconds=source.timeout_seconds, attempts=source.retries)
            if source.kind == "feed":
                items = parse_feed(body)
            elif source.kind == "page":
                items = parse_page(body, source.url)
            else:
                raise ValueError(f"Unsupported source kind: {source.kind}")
        return {"ok": True, "items": items, "error": ""}
    except Exception as exc:  # noqa: BLE001
        if source.kind == "x_user" and source.url:
            if not openrss_fallback_enabled():
                return {
                    "ok": False,
                    "items": [],
                    "error": f"{exc}; OpenRSS fallback disabled",
                }
            fallback_is_openrss = "openrss.org" in source.url
            try:
                if fallback_is_openrss:
                    _openrss_semaphore.acquire()
                    time.sleep(random.uniform(*OPENRSS_DELAY_RANGE))
                body = fetch_url_with_retry(source.url, timeout_seconds=source.timeout_seconds, attempts=source.retries)
                if fallback_is_openrss:
                    items = parse_feed(body)
                    return {"ok": True, "items": items, "error": ""}
            except Exception as fallback_exc:  # noqa: BLE001
                return {"ok": False, "items": [], "error": f"{exc}; OpenRSS fallback failed: {fallback_exc}"}
            finally:
                if fallback_is_openrss:
                    _openrss_semaphore.release()
        return {"ok": False, "items": [], "error": str(exc)}
    finally:
        if is_openrss:
            _openrss_semaphore.release()

def load_state_items(source_id: str) -> list[dict[str, str]]:
    path = state_path(source_id)
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("items", [])


def load_state_saved_at(source_id: str) -> str:
    path = state_path(source_id)
    if not path.exists():
        return ""
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("saved_at", "")


def load_degraded_sources() -> dict[str, dict[str, Any]]:
    if not DEGRADED_PATH.exists():
        return {}
    return json.loads(DEGRADED_PATH.read_text(encoding="utf-8"))


def save_degraded_sources(data: dict[str, dict[str, Any]]) -> None:
    DEGRADED_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


def update_degraded_sources(
    current: dict[str, dict[str, Any]],
    source: Source,
    status: str,
    detail: str,
) -> dict[str, dict[str, Any]]:
    now = datetime.now(UTC).isoformat()
    entry = current.get(source.id, {"source": source.name, "failures": 0, "status": "ok", "last_detail": ""})
    if status in {"failed", "cached"}:
        entry["failures"] = int(entry.get("failures", 0)) + 1
        entry["status"] = "degraded"
        entry["last_detail"] = detail
        entry["last_seen"] = now
    else:
        entry["failures"] = 0
        entry["status"] = "ok"
        entry["last_detail"] = ""
        entry["last_seen"] = now
    current[source.id] = entry
    return current


def is_quarantined(entry: dict[str, Any]) -> bool:
    return int(entry.get("failures", 0)) >= QUARANTINE_THRESHOLD


def quarantine_active(entry: dict[str, Any]) -> bool:
    if not is_quarantined(entry):
        return False
    last_seen = entry.get("last_seen", "")
    if not last_seen:
        return True
    try:
        last_dt = datetime.fromisoformat(last_seen)
    except ValueError:
        return True
    return datetime.now(UTC) < last_dt.astimezone(UTC) + timedelta(hours=QUARANTINE_COOLDOWN_HOURS)


def quarantine_remaining(entry: dict[str, Any]) -> str:
    last_seen = entry.get("last_seen", "")
    if not last_seen:
        return "unknown"
    try:
        last_dt = datetime.fromisoformat(last_seen).astimezone(UTC)
    except ValueError:
        return "unknown"
    remaining = (last_dt + timedelta(hours=QUARANTINE_COOLDOWN_HOURS)) - datetime.now(UTC)
    if remaining.total_seconds() <= 0:
        return "expired"
    hours = int(remaining.total_seconds() // 3600)
    minutes = int((remaining.total_seconds() % 3600) // 60)
    return f"{hours}h {minutes}m"


def state_path(source_id: str) -> Path:
    return STATE_DIR / f"{source_id}.json"


def load_previous_ids(source_id: str) -> set[str]:
    path = state_path(source_id)
    if not path.exists():
        return set()
    data = json.loads(path.read_text(encoding="utf-8"))
    return {item["id"] for item in data.get("items", [])}


def has_previous_state(source_id: str) -> bool:
    return state_path(source_id).exists()


def save_state(source_id: str, items: list[dict[str, str]]) -> None:
    payload = {
        "saved_at": datetime.now(UTC).isoformat(),
        "items": items,
    }
    state_path(source_id).write_text(json.dumps(payload, indent=2), encoding="utf-8")


def novelty_for_source(source: Source) -> str:
    if source.lane == "scene":
        return "emerging"
    if source.confidence == "social-primary":
        return "emerging"
    if source.confidence == "primary":
        return "established"
    return "speculative-interesting"


def action_for_lane(lane: str) -> str:
    return {
        "workflow": "read",
        "infra": "watch",
        "hardware": "watch",
        "scene": "watch",
    }.get(lane, "watch")


def why_it_matters(source: Source, item: dict[str, str]) -> str:
    """Generate a why-it-matters line from the item title. Tries keyword matching
    for specificity; only falls back to a generic lane phrase as last resort."""
    title = item["title"]
    t = title.lower()

    # ── keyword-driven signals (checked before lane fallback) ──
    if any(w in t for w in ("quantiz", "quant", "gguf", "ggml", "awq", "gptq", "exl2")):
        return f"Quantization-related: may affect model compatibility or VRAM efficiency on the 3x3090 stack."
    if any(w in t for w in ("tensor parallel", "multi-gpu", "multi gpu", "split", "pipeline parallel")):
        return f"Multi-GPU inference topic — directly relevant to the 3-card topology."
    if any(w in t for w in ("vram", "memory", "oom", "offload", "kv cache")):
        return f"Memory management signal — matters for fitting large models across 72GB total VRAM."
    if any(w in t for w in ("benchmark", "perf", "throughput", "tok/s", "tokens per second", "latency")):
        return f"Performance data that could inform model selection or serving config."
    if any(w in t for w in ("fine-tun", "finetun", "lora", "qlora", "adapter", "training")):
        return f"Fine-tuning or training technique — relevant if local training becomes part of the workflow."
    if any(w in t for w in ("cuda", "rocm", "vulkan", "hip", "metal", "triton")):
        return f"GPU compute backend change — check if it affects CUDA serving on the 3090s."
    if any(w in t for w in ("docker", "container", "podman", "compose")):
        return f"Container tooling update — relevant to the Docker-based serving stack."
    if any(w in t for w in ("pcie", "nvme", "ssd", "nvlink", "bandwidth")):
        return f"Bus or storage bandwidth topic — relevant to the H12SSL-i's PCIe 4.0 layout."
    if any(w in t for w in ("3090", "a100", "4090", "5090", "h100", "blower", "turbo")):
        return f"GPU hardware mention — directly relevant to the build or resale market."
    if any(w in t for w in ("epyc", "threadripper", "supermicro", "server board", "ecc")):
        return f"Server platform hardware — directly relevant to the H12SSL-i / EPYC stack."
    if any(w in t for w in ("power", "watt", "psu", "thermal", "cooling", "temp", "fan")):
        return f"Power or thermal topic — relevant to the 1600W PSU and blower cooling config."
    if any(w in t for w in ("release", "released", "v0.", "v1.", "v2.", "v3.", "v4.")):
        return f"New release — check changelog for breaking changes or features that affect the local stack."
    if any(w in t for w in ("rag", "retrieval", "embedding", "vector", "search")):
        return f"RAG or embedding pipeline development — potential local workflow pattern."
    if any(w in t for w in ("agent", "tool use", "function call", "mcp")):
        return f"Agent or tool-use pattern — relevant to local AI workflow automation."
    if any(w in t for w in ("llama", "mistral", "qwen", "gemma", "phi", "deepseek")):
        return f"Model family update — check if it changes what's worth running locally."
    if any(w in t for w in ("openai", "anthropic", "claude", "gpt-4", "gpt-5", "closed")):
        return f"Cloud/closed-model news — context for the local-first value proposition."
    if any(w in t for w in ("open source", "open-source", "license", "apache", "mit ")):
        return f"Open-source licensing or release — affects what can run on owned hardware."
    if any(w in t for w in ("10gbe", "10g", "switch", "network", "ethernet", "infiniband")):
        return f"Networking hardware — relevant if scaling beyond single-node."

    # ── social-primary fallback (X feeds) ──
    if source.confidence == "social-primary":
        return f"Social signal from {source.name.replace('X: ', '')} — treat as discovery, verify before acting."

    # ── lane fallback (last resort, kept short) ──
    return {
        "workflow": "Workflow or tooling signal — skim for patterns worth adopting.",
        "infra": "Infrastructure development — check if it touches the local serving stack.",
        "hardware": "Hardware news — evaluate relevance to the current build.",
        "scene": "Scene signal — useful for context on where the ecosystem is heading.",
    }.get(source.lane, "General AI signal — skim for relevance.")


def extract_urls(*values: str) -> list[str]:
    urls: list[str] = []
    for value in values:
        for match in re.findall(r"https?://[^\s)>\]]+", value or ""):
            cleaned = match.rstrip(".,!?;:\"'")
            if cleaned not in urls:
                urls.append(cleaned)
    return urls


def domain_of(url: str) -> str:
    try:
        return urllib.parse.urlparse(url).netloc.lower()
    except Exception:  # noqa: BLE001
        return ""


def followup_type(url: str) -> str:
    domain = domain_of(url)
    path = urllib.parse.urlparse(url).path.lower()
    if "github.com" in domain:
        if "/releases" in path or "/tag/" in path:
            return "release"
        return "github"
    if "arxiv.org" in domain or "openreview.net" in domain:
        return "paper"
    if "youtube.com" in domain or "youtu.be" in domain:
        return "video"
    if path.endswith(".pdf"):
        return "paper"
    return "blog"


def followup_priority(source: Source, followup_kind: str) -> str:
    if source.lane == "infra" and followup_kind in {"release", "github"}:
        return "high"
    if source.lane == "workflow" and followup_kind in {"github", "blog", "paper"}:
        return "high"
    if source.lane == "hardware" and followup_kind in {"github", "blog", "video"}:
        return "medium"
    if source.lane == "scene" and followup_kind in {"github", "blog", "release"}:
        return "medium"
    return "low"


def followup_rank_value(priority: str) -> int:
    return {"high": 0, "medium": 1, "low": 2}.get(priority, 3)


def validation_status(source: Source, discovered_urls: list[dict[str, str]]) -> str:
    if source.confidence != "social-primary":
        return "n/a"
    if not discovered_urls:
        return "direct-post"
    return "needs-followup"


def write_validation_queue(profile: str, run_date: date, queue_items: list[dict[str, Any]]) -> Path:
    suffix = "" if profile == "core" else f".{profile}"
    path = VALIDATION_DIR / f"{run_date.isoformat()}{suffix}.md"
    lines = [
        f"# Validation Queue - {run_date.isoformat()} ({profile})",
        "",
        f"Generated at {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')}",
        "",
    ]
    if not queue_items:
        lines.extend(["- No social items requiring follow-up were found.", ""])
        path.write_text("\n".join(lines), encoding="utf-8")
        return path

    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in queue_items:
        grouped.setdefault(item["lane"], []).append(item)

    for lane in ("workflow", "infra", "hardware", "scene"):
        lane_items = grouped.get(lane, [])
        if not lane_items:
            continue
        lines.extend([f"## {lane.title()}", ""])
        for item in lane_items:
            lines.append(f"### {markdown_escape(item['title'])}")
            lines.append("")
            lines.append(f"- Source: {item['source']}")
            lines.append(f"- Post: {item['link']}")
            lines.append(f"- Validation status: {item['validation_status']}")
            if item["discovered_urls"]:
                lines.append("- Follow-up URLs:")
                for followup in item["discovered_urls"]:
                    title_suffix = f" :: {followup['title']}" if followup.get("title") else ""
                    lines.append(
                        f"  - [{followup['priority']}] [{followup['kind']}] [{followup.get('domain', '')}] {followup['url']}{title_suffix}"
                    )
                    if followup.get("summary"):
                        lines.append(f"    - Summary: {followup['summary']}")
            if item.get("raw_stub"):
                lines.append(f"- Raw stub: {item['raw_stub']}")
            lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def write_health_report(profile: str, run_date: date, statuses: list[dict[str, str]]) -> Path:
    suffix = "" if profile == "core" else f".{profile}"
    path = HEALTH_DIR / f"{run_date.isoformat()}{suffix}.md"
    lines = [
        f"# Sweep Health - {run_date.isoformat()} ({profile})",
        "",
        f"Generated at {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')}",
        "",
    ]
    grouped: dict[str, list[dict[str, str]]] = {}
    for item in statuses:
        grouped.setdefault(item["status"], []).append(item)
    for status_name in ("ok", "cached", "failed", "quarantined"):
        items = grouped.get(status_name, [])
        if not items:
            continue
        lines.extend([f"## {status_name.title()}", ""])
        for item in sorted(items, key=lambda x: x["source"].lower()):
            line = f"- {item['source']}"
            if item.get("detail"):
                line += f": {item['detail']}"
            lines.append(line)
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def slugify(value: str, max_length: int = 64) -> str:
    value = re.sub(r"[^a-zA-Z0-9]+", "-", value.lower()).strip("-")
    if not value:
        value = "item"
    return value[:max_length].rstrip("-")


def maybe_write_raw_stub(
    run_date: date,
    lane: str,
    source_name: str,
    title: str,
    post_url: str,
    published: str,
    followups: list[dict[str, str]],
) -> Path | None:
    high_priority = [item for item in followups if item["priority"] == "high"]
    if not high_priority:
        return None

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    slug = slugify(title)
    path = RAW_DIR / f"{run_date.isoformat()}-{slug}.md"
    if path.exists():
        return path

    lines = [
        f"# {title}",
        "",
        f"- **Date Captured:** {run_date.isoformat()}",
        f"- **Lane:** {lane}",
        f"- **Source:** {source_name}",
        f"- **Social Post:** {post_url}",
        f"- **Published:** {published}",
        f"- **Status:** Auto-generated intake stub from sweep validation",
        "",
        "## Follow-Up Targets",
        "",
    ]
    for item in high_priority:
        label = f"[{item['kind']}]"
        if item.get("domain"):
            label += f" [{item['domain']}]"
        lines.append(f"- {label} {item['url']}")
        if item.get("title"):
            lines.append(f"  - Title: {item['title']}")
        if item.get("summary"):
            lines.append(f"  - Summary: {item['summary']}")
    lines.extend(
        [
            "",
            "## Notes",
            "",
            "- Why this matters:",
            "- Validation summary:",
            "- Promotion decision:",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def markdown_escape(value: str) -> str:
    return value.replace("\n", " ").strip()


def source_priority(entry: dict[str, Any]) -> int:
    if entry["confidence"] == "social-primary" and entry["validation_status"] == "needs-followup":
        return 0
    if entry["lane"] == "infra":
        return 1
    if entry["lane"] == "workflow":
        return 2
    if entry["lane"] == "hardware":
        return 3
    return 4


def keyword_bonus(title: str) -> int:
    lowered = title.lower()
    bonuses = {
        "release": -2,
        "benchmark": -2,
        "agent": -1,
        "workflow": -1,
        "local": -1,
        "llm": -1,
        "quant": -1,
        "inference": -1,
        "vllm": -1,
        "ollama": -1,
        "llama.cpp": -1,
        "karpathy": -1,
        "gemma": -1,
        "qwen": -1,
    }
    score = 0
    for token, bonus in bonuses.items():
        if token in lowered:
            score += bonus
    return score


def entry_rank(entry: dict[str, Any]) -> tuple[int, float]:
    base = source_priority(entry)
    base += keyword_bonus(entry["title"])
    if entry["confidence"] == "social-primary":
        base -= 1
    if entry["followup_urls"]:
        best_followup = min(followup_rank_value(item["priority"]) for item in entry["followup_urls"])
        base += best_followup - 1
    return (base, -sort_stamp(entry["published"]))


def parse_published(value: str) -> datetime:
    value = (value or "").strip()
    if not value:
        return datetime.min.replace(tzinfo=UTC)
    for fmt in ("%Y-%m-%d %H:%M:%S UTC", "%Y-%m-%d %H:%M:%S %z"):
        try:
            dt = datetime.strptime(value, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=UTC)
            return dt.astimezone(UTC)
        except ValueError:
            pass
    try:
        return parsedate_to_datetime(value).astimezone(UTC)
    except Exception:  # noqa: BLE001
        pass
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
    except Exception:  # noqa: BLE001
        return datetime.min.replace(tzinfo=UTC)


def sort_stamp(value: str) -> float:
    dt = parse_published(value)
    if dt.year <= 1900:
        return float("-inf")
    return dt.timestamp()


def item_age_days(run_date: date, published: str) -> float | None:
    dt = parse_published(published)
    if dt.year <= 1900:
        return None
    run_dt = datetime.combine(run_date, datetime.min.time(), tzinfo=UTC) + timedelta(days=1)
    return (run_dt - dt.astimezone(UTC)).total_seconds() / 86400


def is_stale_item(run_date: date, item: dict[str, str]) -> bool:
    age_days = item_age_days(run_date, item.get("published", ""))
    if age_days is None:
        return False
    return age_days > MAX_ITEM_AGE_DAYS


def is_high_signal_commit(title: str) -> bool:
    lowered = title.lower()
    return any(keyword in lowered for keyword in LLAMACPP_COMMIT_KEYWORDS)


def is_low_value_github_activity(title: str) -> bool:
    lowered = title.lower()
    low_value_tokens = (
        "created a branch",
        "starred ",
        "commented on an issue",
    )
    return any(token in lowered for token in low_value_tokens)


def collapse_github_activity(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    passthrough: list[dict[str, Any]] = []

    for entry in entries:
        if "github activity" not in entry["source"].lower():
            passthrough.append(entry)
            continue
        if not is_low_value_github_activity(entry["title"]):
            passthrough.append(entry)
            continue
        key = (entry["lane"], entry["source"])
        grouped.setdefault(key, []).append(entry)

    collapsed: list[dict[str, Any]] = []
    for (lane, source), items in grouped.items():
        if len(items) < GITHUB_ACTIVITY_COLLAPSE_THRESHOLD:
            collapsed.extend(items)
            continue
        actor = source.replace(" GitHub Activity", "")
        event_counts: dict[str, int] = {}
        for item in items:
            lowered = item["title"].lower()
            if "pushed " in lowered:
                label = "pushes"
            elif "created a branch" in lowered:
                label = "branch creations"
            elif "starred " in lowered:
                label = "stars"
            elif "opened a pull request" in lowered:
                label = "pull requests"
            elif "closed a pull request" in lowered:
                label = "closed pull requests"
            elif "commented on an issue" in lowered:
                label = "issue comments"
            else:
                label = "events"
            event_counts[label] = event_counts.get(label, 0) + 1
        top_types = ", ".join(
            f"{count} {label}" for label, count in sorted(event_counts.items(), key=lambda item: (-item[1], item[0]))[:3]
        )
        newest = max(items, key=lambda item: sort_stamp(item["published"]))
        collapsed.append(
            {
                "lane": lane,
                "source": source,
                "title": f"{actor}: {len(items)} GitHub events",
                "link": newest["link"],
                "published": newest["published"],
                "confidence": newest["confidence"],
                "novelty": newest["novelty"],
                "action": "scan",
                "why": f"Routine GitHub activity compressed for scanability: {top_types}.",
                "validation_status": "n/a",
                "followup_urls": [],
            }
        )
    return passthrough + collapsed


def infer_specific_why(source: Source, item: dict[str, str]) -> str:
    title = item["title"].lower()
    sname = source.name.lower()

    # ── source-specific overrides ──
    if "llama.cpp releases" in sname:
        return "llama.cpp release — check for multi-GPU, quantization, or backend changes."
    if "llama.cpp commits" in sname:
        if "tensor parallel" in title or "split-mode tensor" in title:
            return "Directly relevant to 3x3090 multi-GPU topology."
        if any(w in title for w in ("cuda", "vulkan", "hip", "quant", "fuse")):
            return "Performance-sensitive backend path — could affect local throughput."
        return "llama.cpp commit — read only if it touches your serving path."
    if "ollama releases" in sname:
        return "Ollama release — check for model support, multi-GPU, and compatibility."
    if "ollama blog" in sname:
        return "Official Ollama announcement — usually documents new model support or features."
    if "vllm" in sname:
        if "release" in sname:
            return "vLLM release — check for tensor parallelism, memory, and throughput changes."
        return "vLLM development signal — relevant to the production serving layer."
    if "george hotz" in sname or "geohot" in sname:
        return "Geohot take — high-signal on open-source AI, tinygrad, and builder philosophy."
    if "tinygrad" in sname:
        return "tinygrad release — alternative inference engine with strong AMD support."
    if "servethehome" in sname:
        return "ServeTheHome coverage — server hardware reviews and benchmarks from a trusted source."
    if "jeff geerling" in sname or "geerlingguy" in sname:
        return "Geerling content — practical hardware testing, often with Linux and ARM angles."
    if "level1techs" in sname:
        return "Level1Techs — deep-dive hardware and Linux content for builder types."
    if "simon willison" in sname:
        if "github" in sname and "released" in title:
            return "Simon Willison tool release — usually practical and worth evaluating."
        return "Simon Willison signal — surfaces practical patterns before they spread."
    if "karpathy" in sname:
        return "Karpathy signal — watch for workflow shifts, repo movement, or vocabulary changes."
    if "hugging face blog" in sname:
        return "Hugging Face blog post — check for new model releases, library updates, or ecosystem shifts."
    if "raschka" in sname or "rasbt" in sname:
        return "Sebastian Raschka — deep technical writing on training, evaluation, and model internals."
    if "fast.ai" in sname:
        return "fast.ai signal — practical deep learning patterns from Howard's crew."
    if "answer.ai" in sname:
        return "Answer.AI signal — Jeremy Howard's lab, focused on making AI practical and accessible."
    if "steve hanov" in sname or "stevehanov" in sname:
        return "Steve Hanov — lean infra, SQLite, local LLMs, solo-founder running real revenue on minimal stack."

    # ── fall through to keyword-based matching ──
    return why_it_matters(source, item)


def ai_summary_enabled() -> bool:
    return os.getenv("SWEEP_AI_SUMMARY_ENABLED", "false").strip().lower() == "true"


def synthesize_ai_summary(profile: str, run_date: date, entries: list[dict[str, Any]], failures: list[str]) -> str:
    model = os.getenv("SWEEP_AI_SUMMARY_MODEL", "").strip()
    if not model:
        return ""
    endpoint = os.getenv("SWEEP_AI_SUMMARY_URL", "http://127.0.0.1:11434/api/generate").strip()
    top_entries = sorted(entries, key=entry_rank)[:12]
    prompt_lines = [
        f"Summarize this AI infrastructure/newsletter sweep for {run_date.isoformat()} ({profile}).",
        "Write a single paragraph of 4-6 sentences for a technical operator.",
        "Do NOT use bullet points. Write fluent, direct prose.",
        "Prioritize concrete developments that matter for local inference, multi-GPU rigs, workflows, and builder signal.",
        "Ignore routine GitHub churn. Mention uncertainty if sources were degraded.",
        "",
        "Top items:",
    ]
    for entry in top_entries:
        prompt_lines.append(
            f"- [{entry['lane']}] {entry['title']} | source={entry['source']} | why={entry['why']}"
        )
    if failures:
        prompt_lines.extend(["", "Fetch issues:"])
        for failure in failures[:5]:
            prompt_lines.append(f"- {failure}")

    payload = {
        "model": model,
        "prompt": "\n".join(prompt_lines),
        "stream": False,
    }
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "User-Agent": USER_AGENT},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            data = json.loads(response.read().decode("utf-8"))
    except Exception:
        return ""
    response_text = data.get("response", "")
    response_text = re.sub(r"\r\n?", "\n", response_text).strip()
    return response_text


def heuristic_summary(profile: str, run_date: date, entries: list[dict[str, Any]], failures: list[str]) -> str:
    """Build a prose summary paragraph without an LLM."""
    if not entries:
        return ""

    top = sorted(entries, key=entry_rank)[:20]
    lane_counts: dict[str, int] = {}
    for entry in entries:
        lane_counts[entry["lane"]] = lane_counts.get(entry["lane"], 0) + 1

    total = len(entries)
    active_lanes = [lane for lane, _count in sorted(lane_counts.items(), key=lambda item: (-item[1], item[0]))]
    x_failures = sum(1 for failure in failures if failure.startswith("X:"))

    def strip_source_noise(source: str) -> str:
        replacements = (
            " GitHub Activity",
            " Releases",
            " Commits",
            " Blog",
            " Atom",
            " YouTube",
        )
        cleaned = source
        for token in replacements:
            cleaned = cleaned.replace(token, "")
        return cleaned

    def tidy_title(title: str) -> str:
        cleaned = " ".join(title.split())
        return cleaned.rstrip(".")

    def normalized_title(title: str) -> str:
        cleaned = tidy_title(title)
        if cleaned.lower().startswith("blog | "):
            cleaned = cleaned.split("|", 1)[1].strip()
        return cleaned

    def actor_prefix(title: str) -> str:
        lowered = title.lower()
        if lowered.startswith("simonw "):
            return "Simon"
        if lowered.startswith("karpathy "):
            return "Karpathy"
        return ""

    def describe_item(item: dict[str, Any]) -> str:
        title = normalized_title(item["title"])
        source = item["source"]
        lane = item["lane"]
        source_name = strip_source_noise(source)
        lowered = title.lower()

        if "serve the home" in source_name.lower() or "servethehome" in source_name.lower():
            return f"ServeTheHome published {title}"
        if "level1techs" in source_name.lower():
            return f"Level1Techs posted {title}"
        if "geerling" in source_name.lower():
            return f"Jeff Geerling published {title}"
        if "simon willison" in source_name.lower():
            if "released" in lowered or re.fullmatch(r".+\s0\.\d+.*", title):
                return f"Simon Willison published {title}"
            return f"Simon surfaced {title}"
        if "karpathy" in source_name.lower():
            return f"Karpathy posted {title}"
        if "ollama" in source_name.lower():
            return f"Ollama shipped {title}"
        if "vllm" in source_name.lower():
            if title.lower() == "vllm":
                return "vLLM published a new blog post"
            return f"vLLM shipped {title}"
        if "llama.cpp" in source_name.lower():
            if "tensor parallel" in lowered or "split-mode tensor" in lowered:
                return f"llama.cpp landed {title}"
            if re.fullmatch(r"b\d+", title):
                return f"llama.cpp cut release {title}"
            return f"llama.cpp changed {title}"
        if lane == "hardware":
            return f"{source_name} published {title}"
        if lane == "infra":
            return f"{source_name} shipped {title}"
        if lane == "workflow":
            actor = actor_prefix(title)
            if actor:
                return f"{actor} posted {title}"
            return f"{source_name} surfaced {title}"
        return f"{source_name} published {title}"

    def contextualize_item(item: dict[str, Any]) -> str:
        title = normalized_title(item["title"])
        lowered = title.lower()
        lane = item["lane"]
        source_name = strip_source_noise(item["source"])

        if "tensor parallel" in lowered:
            return "a sign that local multi-GPU serving is still getting serious low-level attention"
        if "split-mode tensor" in lowered:
            return "another sign that multi-GPU inference is still in active flux"
        if "cuda" in lowered:
            return "small CUDA changes can compound quickly in local inference stacks"
        if "vulkan" in lowered:
            return "part of the slow spread of local inference beyond the CUDA-only path"
        if "10gbe" in lowered or "10gbe" in source_name.lower():
            return "cheap 10GbE gear is part of the home-rack AI story"
        if "switch" in lowered:
            return "cheap networking gear is part of the home-rack AI story"
        if lowered in {"blog | vllm", "vllm", "blog | ollama", "ollama"}:
            return "another marker of how fast the local serving layer is moving"
        if title.startswith("v0.") or "release" in lowered:
            if lane == "infra":
                return "the local serving layer keeps moving fast"
            return "worth reading for practical changes, not just version churn"
        if lane == "hardware":
            return "useful signal for people building real machines, not just reading model cards"
        if lane == "workflow":
            return "useful if it points to a workflow people can actually steal"
        if lane == "scene":
            return "part of the broader local-first AI scene taking shape"
        return "worth a closer look"

    def preferred_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        def priority(item: dict[str, Any]) -> tuple[int, tuple[int, float]]:
            title = normalized_title(item["title"])
            lowered = title.lower()
            score = 0
            if title.lower() in {"vllm", "ollama"}:
                score += 8
            if "pushed " in lowered or "contributed to " in lowered or "opened a pull request" in lowered:
                score += 5
            if "created a branch" in lowered or "starred " in lowered:
                score += 6
            if re.fullmatch(r"b\d+", title):
                score += 4
            if "tensor parallel" in lowered or "split-mode tensor" in lowered or "cuda" in lowered:
                score -= 5
            if title.startswith("v0."):
                score -= 2
            if "review" in lowered or "benchmark" in lowered:
                score -= 1
            if item["lane"] == "workflow" and "github activity" in item["source"].lower():
                score += 2
            return (score, entry_rank(item))

        def signature(item: dict[str, Any]) -> tuple[str, str]:
            title = normalized_title(item["title"])
            lowered = title.lower()
            if title.startswith("v0."):
                base = re.sub(r"rc\d+.*$", "", lowered)
                return (item["source"], base)
            if re.fullmatch(r"b\d+", title):
                return (item["source"], "llamacpp-build")
            return (item["source"], lowered)

        selected: list[dict[str, Any]] = []
        seen_signatures: set[tuple[str, str]] = set()
        seen_lanes: set[str] = set()
        seen_sources: set[str] = set()

        for item in sorted(items, key=priority):
            title = normalized_title(item["title"])
            if title.lower() in {"vllm", "ollama"}:
                continue
            item_sig = signature(item)
            if item_sig in seen_signatures:
                continue
            if item["lane"] in seen_lanes and len(seen_lanes) < 3:
                continue
            if item["source"] in seen_sources and len(seen_sources) < 3:
                continue
            selected.append(item)
            seen_signatures.add(item_sig)
            seen_lanes.add(item["lane"])
            seen_sources.add(item["source"])
            if len(selected) >= 4:
                break

        return selected or sorted(items, key=priority)[:4]

    summary_items = preferred_items(top)

    sentences: list[str] = []

    if total == 1:
        sentences.append("Quiet day.")
    elif total <= 3:
        sentences.append("Light day, but not empty.")
    elif len(active_lanes) >= 3:
        sentences.append("Busy day across multiple parts of the stack.")
    elif active_lanes and active_lanes[0] == "infra":
        sentences.append("Infra led the day.")
    else:
        sentences.append("A few things moved today.")

    lead = summary_items[0]
    sentences.append(f"{describe_item(lead)} — {contextualize_item(lead)}.")

    for item in summary_items[1:4]:
        lane = item["lane"]
        if lane == lead["lane"] and total <= 2:
            continue
        if lane == lead["lane"] and lead["source"] == item["source"] and total <= 4:
            continue
        sentences.append(f"{describe_item(item)} — {contextualize_item(item)}.")
        if len(sentences) >= 4:
            break

    if failures and len(sentences) < 5:
        if total == 1 and x_failures == len(failures) and x_failures > 5:
            sentences.append("Not a lot broke through, but the signal was clean enough to read.")
        elif len(failures) > 3 and x_failures < len(failures):
            sentences.append("The field looked thinner than usual, so treat this as a partial read.")

    emerging = [item for item in top if item.get("novelty") == "emerging"]
    if emerging and len(sentences) < 5:
        if len(emerging) == 1:
            sentences.append(f"One thing to keep an eye on: {normalized_title(emerging[0]['title'])}.")
        else:
            sentences.append(
                f"Early-signal items worth watching include {normalized_title(emerging[0]['title'])} and {normalized_title(emerging[1]['title'])}."
            )

    while len(sentences) < 4:
        if total == 1:
            sentences.append("That was the only new item in the sweep.")
        elif total <= 3:
            sentences.append("Short issue, easy to scan.")
        else:
            filler = "No single breakthrough, but the pace of small serving-layer fixes is the story."
            if filler in sentences:
                sentences.append("Most of the remaining items are smaller release and commit updates.")
            else:
                sentences.append(filler)

    return " ".join(sentences[:6]).replace("â€”", "-").replace("—", "-")


def format_fetch_issues(failures: list[str]) -> list[str]:
    """Keep known X/OpenRSS outages compact without hiding non-social failures."""
    x_failures = [failure for failure in failures if failure.startswith("X:")]
    other_failures = [failure for failure in failures if not failure.startswith("X:")]
    if not x_failures:
        return failures

    timeout_count = sum(1 for failure in x_failures if "timed out" in failure)
    cached_count = sum(1 for failure in x_failures if "using cached state" in failure)
    if timeout_count == len(x_failures):
        x_summary = f"X/OpenRSS: {len(x_failures)} social feeds timed out"
    else:
        x_summary = f"X/OpenRSS: {len(x_failures)} social feed fetches failed"
        if timeout_count:
            x_summary += f", including {timeout_count} timeouts"
    if cached_count:
        x_summary += f"; cached state used for {cached_count}"
    x_summary += "."
    return [x_summary, *other_failures]


def write_digest(
    profile: str,
    run_date: date,
    entries: list[dict[str, Any]],
    failures: list[str],
    ai_summary: str = "",
) -> Path:
    suffix = "" if profile == "core" else f".{profile}"
    path = DAILY_DIR / f"{run_date.isoformat()}{suffix}.md"
    lines = [
        f"# Daily Sweep - {run_date.isoformat()} ({profile})",
        "",
        f"Generated at {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')}",
        "",
    ]

    if entries:
        lines.extend(["## Top Signals", ""])
        top_entries = sorted(
            entries,
            key=entry_rank,
        )[:5]
        for entry in top_entries:
            lines.append(f"- [{entry['lane']}] {markdown_escape(entry['title'])} ({entry['source']})")
        lines.append("")

    if ai_summary:
        lines.extend(["## Summary", "", ai_summary, ""])

    if failures:
        lines.extend(["## Fetch Issues", ""])
        for failure in format_fetch_issues(failures):
            lines.append(f"- {failure}")
        lines.append("")

    if not entries:
        lines.extend(["## Summary", "", "- No new items detected across configured sources.", ""])
        path.write_text("\n".join(lines), encoding="utf-8")
        return path

    for lane in ("workflow", "infra", "hardware", "scene"):
        lane_entries = [entry for entry in entries if entry["lane"] == lane]
        if not lane_entries:
            continue
        lines.extend([f"## {lane.title()}", ""])
        for entry in lane_entries:
            title = markdown_escape(entry["title"])
            source = markdown_escape(entry["source"])
            link = entry["link"]
            published = markdown_escape(entry["published"])
            why = markdown_escape(entry["why"])
            lines.append(f"### {title}")
            lines.append("")
            lines.append(f"- Source: {source}")
            if link:
                lines.append(f"- Link: {link}")
            if published:
                lines.append(f"- Published: {published}")
            lines.append(f"- Confidence: {entry['confidence']}")
            lines.append(f"- Novelty: {entry['novelty']}")
            lines.append(f"- Action: {entry['action']}")
            if entry["validation_status"] != "n/a":
                lines.append(f"- Validation: {entry['validation_status']}")
            if entry["followup_urls"]:
                rendered = ", ".join(
                    (
                        f"[{item['priority']}/{item['kind']}/{item.get('domain', '')}] {item['url']}"
                        + (f" :: {item['title']}" if item.get("title") else "")
                        + (f" -- {item['summary']}" if item.get("summary") else "")
                    )
                    for item in entry["followup_urls"]
                )
                lines.append(f"- Follow-up: {rendered}")
            lines.append(f"- Why it matters: {why}")
            lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def iso_week_label(run_date: date) -> str:
    year, week, _ = run_date.isocalendar()
    return f"{year}-W{week:02d}"


def write_weekly_rollup_stub(profile: str, run_date: date) -> Path:
    suffix = "" if profile == "core" else f".{profile}"
    week_label = iso_week_label(run_date)
    path = WEEKLY_DIR / f"{week_label}{suffix}.md"
    if path.exists():
        return path
    lines = [
        f"# Weekly Sweep Rollup - {week_label} ({profile})",
        "",
        f"Created at {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        "## Themes",
        "",
        "- Workflow shifts:",
        "- Infra changes:",
        "- Hardware findings:",
        "- Scene discoveries:",
        "",
        "## Candidates For Promotion",
        "",
        "- ",
        "",
        "## Decisions To Revisit",
        "",
        "- ",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Sovereign Node daily research sweeps.")
    parser.add_argument("--date", dest="run_date", help="Override date in YYYY-MM-DD format.")
    parser.add_argument("--dry-run", action="store_true", help="Fetch and diff without writing state.")
    parser.add_argument(
        "--profile",
        choices=("core", "extended", "all"),
        default="core",
        help="Select source profile. 'all' includes both core and extended.",
    )
    parser.add_argument(
        "--bootstrap-emit",
        action="store_true",
        help="Emit items even for sources with no prior state.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=8,
        help="Maximum concurrent fetch workers.",
    )
    parser.add_argument(
        "--skip-ai-summary",
        action="store_true",
        help="Do not generate optional AI summary even if enabled by environment.",
    )
    parser.add_argument(
        "--replay-current",
        action="store_true",
        help="Treat the current fetched snapshot as new items for rendering/testing without relying on saved diff state.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    run_date = date.fromisoformat(args.run_date) if args.run_date else date.today()

    ensure_dirs()
    manifest_sources = read_manifest()
    if args.profile == "all":
        sources = manifest_sources
    else:
        sources = [source for source in manifest_sources if source.profile == args.profile]
    entries: list[dict[str, str]] = []
    validation_queue: list[dict[str, Any]] = []
    failures: list[str] = []
    health_statuses: list[dict[str, str]] = []
    degraded_sources = load_degraded_sources()

    active_sources: list[Source] = []
    for source in sources:
        degraded_entry = degraded_sources.get(source.id, {})
        if quarantine_active(degraded_entry):
            health_statuses.append(
                {
                    "source": source.name,
                    "status": "quarantined",
                    "detail": (
                        f"failures={degraded_entry.get('failures', 0)}; "
                        f"cooldown={quarantine_remaining(degraded_entry)}; "
                        f"last={degraded_entry.get('last_detail', '')}"
                    ),
                }
            )
            continue
        active_sources.append(source)

    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
        future_map = {executor.submit(fetch_source, source): source for source in active_sources}
        results: list[tuple[Source, dict[str, Any]]] = []
        for future in concurrent.futures.as_completed(future_map):
            source = future_map[future]
            try:
                result = future.result()
            except Exception as exc:  # noqa: BLE001
                result = {"ok": False, "items": [], "error": str(exc)}
            results.append((source, result))

    for source, result in sorted(results, key=lambda item: item[0].name.lower()):
        if not result["ok"]:
            saved_at = load_state_saved_at(source.id)
            if saved_at:
                failures.append(f"{source.name}: {result['error']} (using cached state from {saved_at})")
                health_statuses.append(
                    {"source": source.name, "status": "cached", "detail": f"cached state from {saved_at}"}
                )
                degraded_sources = update_degraded_sources(
                    degraded_sources, source, "cached", f"cached state from {saved_at}"
                )
            else:
                failures.append(f"{source.name}: {result['error']}")
                health_statuses.append({"source": source.name, "status": "failed", "detail": result["error"]})
                degraded_sources = update_degraded_sources(degraded_sources, source, "failed", result["error"])
            continue
        health_statuses.append({"source": source.name, "status": "ok", "detail": ""})
        degraded_sources = update_degraded_sources(degraded_sources, source, "ok", "")

        items = result["items"]
        had_previous_state = has_previous_state(source.id)
        previous_ids = load_previous_ids(source.id)
        if args.replay_current:
            new_items = items
        elif had_previous_state or args.bootstrap_emit:
            new_items = [item for item in items if item["id"] not in previous_ids]
        else:
            new_items = []
            failures.append(f"{source.name}: bootstrapped state from current snapshot, no prior diff available")

        filtered_items: list[dict[str, str]] = []
        for item in new_items:
            if is_stale_item(run_date, item):
                continue
            if "llama.cpp commits" in source.name.lower() and not is_high_signal_commit(item["title"]):
                continue
            filtered_items.append(item)

        for item in filtered_items[:10]:
            raw_urls = extract_urls(item["title"], item["summary"])
            followup_urls: list[dict[str, str]] = []
            if source.confidence == "social-primary":
                for raw_url in raw_urls[:2]:
                    try:
                        resolved = resolve_url(raw_url)
                    except Exception:  # noqa: BLE001
                        resolved = raw_url
                    if domain_of(resolved) not in {"twitter.com", "x.com"} and all(
                        entry["url"] != resolved for entry in followup_urls
                    ):
                        kind = followup_type(resolved)
                        resolved_domain = domain_of(resolved)
                        resolved_title = fetch_page_title(resolved)
                        resolved_summary = fetch_page_description(resolved)
                        followup_urls.append(
                            {
                                "url": resolved,
                                "kind": kind,
                                "priority": followup_priority(source, kind),
                                "domain": resolved_domain,
                                "title": resolved_title,
                                "summary": resolved_summary,
                            }
                        )

            status = validation_status(source, followup_urls)
            entries.append(
                {
                    "lane": source.lane,
                    "source": source.name,
                    "title": item["title"],
                    "link": item["link"],
                    "published": item["published"],
                    "confidence": source.confidence,
                    "novelty": novelty_for_source(source),
                    "action": action_for_lane(source.lane),
                    "why": infer_specific_why(source, item),
                    "validation_status": status,
                    "followup_urls": followup_urls,
                }
            )
            if status == "needs-followup":
                raw_stub = maybe_write_raw_stub(
                    run_date,
                    source.lane,
                    source.name,
                    item["title"],
                    item["link"],
                    item["published"],
                    followup_urls,
                )
                validation_queue.append(
                    {
                        "lane": source.lane,
                        "source": source.name,
                        "title": item["title"],
                        "link": item["link"],
                        "validation_status": status,
                        "discovered_urls": followup_urls,
                        "raw_stub": str(raw_stub) if raw_stub else "",
                    }
                )

        if not args.dry_run:
            save_state(source.id, items[:50])

    entries = collapse_github_activity(entries)
    entries.sort(key=lambda entry: (entry["lane"], -sort_stamp(entry["published"]), entry["source"]))
    ai_summary = ""
    if entries and not args.skip_ai_summary:
        if ai_summary_enabled():
            ai_summary = synthesize_ai_summary(args.profile, run_date, entries, failures)
        if not ai_summary:
            ai_summary = heuristic_summary(args.profile, run_date, entries, failures)
    digest_path = write_digest(args.profile, run_date, entries, failures, ai_summary=ai_summary)
    write_validation_queue(args.profile, run_date, validation_queue)
    write_health_report(args.profile, run_date, health_statuses)
    write_weekly_rollup_stub(args.profile, run_date)
    if not args.dry_run:
        save_degraded_sources(degraded_sources)
    print(digest_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
