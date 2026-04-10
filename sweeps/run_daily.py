#!/usr/bin/env python3
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import os
import time
import re
import sys
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
DEGRADED_PATH = SWEEPS_DIR / "health" / "degraded_sources.json"
RAW_DIR = ROOT / "docs" / "wiki" / "raw"
MANIFEST_PATH = ROOT / "sweeps" / "sources.json"
USER_AGENT = "SovereignNodeSweep/0.1 (+local)"
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


def ensure_dirs() -> None:
    for directory in (DAILY_DIR, WEEKLY_DIR, VALIDATION_DIR, HEALTH_DIR, STATE_DIR):
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


def parse_feed(xml_bytes: bytes) -> list[dict[str, str]]:
    root = ET.fromstring(xml_bytes)
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
    try:
        body = fetch_url_with_retry(source.url, timeout_seconds=source.timeout_seconds, attempts=source.retries)
        if source.kind == "feed":
            items = parse_feed(body)
        elif source.kind == "page":
            items = parse_page(body, source.url)
        else:
            raise ValueError(f"Unsupported source kind: {source.kind}")
        return {"ok": True, "items": items, "error": ""}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "items": [], "error": str(exc)}


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
    title = item["title"].lower()
    if source.confidence == "social-primary":
        if source.lane == "workflow":
            return "Early workflow discovery from a curated X source; validate if it implies a repeatable pattern."
        if source.lane == "infra":
            return "Early infra or release signal from X; confirm via repo, release notes, or docs."
        return "Early scene signal from X; useful for discovery, not enough alone for a decision."
    if source.lane == "workflow":
        return "Potential workflow or reasoning-pattern signal relevant to the Karpathy loop."
    if source.lane == "infra":
        if "release" in title or title.startswith("v"):
            return "Could change local serving capability, compatibility, or performance."
        return "Relevant to local inference stack evolution."
    if source.lane == "hardware":
        return "May affect performance, tuning, or operational behavior of the physical node."
    return "Useful for tracking local-first builder patterns and early ideas."


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
    if "llama.cpp releases" in source.name.lower():
        return "llama.cpp moved again; check whether this release train includes multi-GPU, quantization, or backend changes."
    if "llama.cpp commits" in source.name.lower():
        if "tensor parallel" in title or "split-mode tensor" in title:
            return "Directly relevant to awkward multi-GPU topologies like 3x3090 builds and worth tracking against current stack assumptions."
        if any(token in title for token in ("cuda", "vulkan", "hip", "quant", "fuse")):
            return "Touches a performance-sensitive inference backend path that could affect local node throughput or compatibility."
        return "Relevant llama.cpp implementation movement; read only if it touches your serving path."
    if "ollama releases" in source.name.lower():
        return "Operational release for the local serving stack; check notes for compatibility, model support, and multi-GPU changes."
    if "simon willison atom" in source.name.lower():
        return "High-signal workflow or tooling note from a builder who often surfaces practical patterns before they spread."
    if "simon willison github activity" in source.name.lower() and "released" in title:
        return "A concrete tool release from Simon, usually more useful than routine GitHub activity."
    if "karpathy" in source.name.lower():
        return "Direct Karpathy-adjacent signal; useful when it reflects workflow shifts, repo movement, or vocabulary changes."
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
        "Write 3-5 tight bullet points for a technical operator.",
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
        lines.extend(["## AI Summary", "", ai_summary, ""])

    if failures:
        lines.extend(["## Fetch Issues", ""])
        for failure in failures:
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
        if had_previous_state or args.bootstrap_emit:
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
    if entries and not args.skip_ai_summary and ai_summary_enabled():
        ai_summary = synthesize_ai_summary(args.profile, run_date, entries, failures)
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
