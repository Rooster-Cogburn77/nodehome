#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.request
from datetime import date
from pathlib import Path


RESEND_API_URL = "https://api.resend.com/emails"


def digest_path(profile: str, run_date: date) -> Path:
    root = Path(__file__).resolve().parent.parent
    suffix = "" if profile == "core" else f".{profile}"
    return root / "docs" / "sweeps" / "daily" / f"{run_date.isoformat()}{suffix}.md"


def markdown_to_text(markdown: str) -> str:
    text = markdown
    text = re.sub(r"^###\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^##\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^#\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"\[(.*?)\]\((.*?)\)", r"\1 (\2)", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    return text.strip()


def _esc(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# ── Theme constants (from nodehome.ai/assets/styles.css) ──────────────

_BG = "#0a0f0d"
# 1x4px tiling scanline texture (green-tinted base + 1px lighter scanline row)
_BG_TILE = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAAECAYAAABP2FU6AAAAE0lEQVR4nGMQU5L5z8AjJIBEAAAsGATbMcx1qAAAAABJRU5ErkJggg=="
_BG_STYLE = f"background-color:{_BG};background-image:url({_BG_TILE});background-repeat:repeat;"
_BG_ELEV = "#101614"
_BG_SOFT = "#131b18"
_FG = "#d8e2dc"
_MUTED = "#93a19b"
_LINE = "#26302c"
_ACCENT = "#82f28a"
_ACCENT_DIM = "#57c662"
_WARNING = "#e7cf71"
_SERIF = "'Iowan Old Style','Palatino Linotype','Book Antiqua',Georgia,serif"
_SANS = "'Segoe UI','Inter',system-ui,sans-serif"
_MONO = "'IBM Plex Mono','Consolas','SFMono-Regular',monospace"

_LINK_STYLE = f"color:{_ACCENT};text-decoration:underline;text-decoration-color:rgba(130,242,138,0.45);"
_META_FIELDS = {"Source", "Link", "Published", "Confidence", "Novelty", "Action", "Why it matters"}


# ── Phase 1: Parse markdown into structured digest ─────────────────────

def _parse_digest(markdown: str) -> dict:
    """Parse a sweep digest into structured data."""
    result: dict = {
        "title": "",
        "timestamp": "",
        "top_signals": [],
        "fetch_issues": [],
        "sections": [],     # list of {name, items}
        "summary_lines": [],
    }
    lines = markdown.split("\n")
    current_section: dict | None = None
    current_item: dict | None = None
    in_section_name = ""

    def _flush_item():
        nonlocal current_item
        if current_item and current_section is not None:
            current_section["items"].append(current_item)
        current_item = None

    for line in lines:
        s = line.strip()
        if not s:
            continue

        # H1
        if s.startswith("# ") and not s.startswith("## "):
            result["title"] = s[2:]
            continue

        # timestamp
        if s.startswith("Generated at "):
            result["timestamp"] = s
            continue

        # H2 — section boundary
        if s.startswith("## ") and not s.startswith("### "):
            _flush_item()
            name = s[3:]
            in_section_name = name
            if name not in ("Top Signals", "Fetch Issues", "Summary", "AI Summary"):
                current_section = {"name": name, "items": []}
                result["sections"].append(current_section)
            else:
                current_section = None
            continue

        # H3 — item within a lane section
        if s.startswith("### "):
            _flush_item()
            current_item = {"title": s[4:], "meta": {}}
            continue

        # bullet
        if s.startswith("- "):
            text = s[2:]
            if in_section_name == "Top Signals":
                result["top_signals"].append(text)
                continue
            if in_section_name == "Fetch Issues":
                result["fetch_issues"].append(text)
                continue
            if in_section_name in ("Summary", "AI Summary"):
                result["summary_lines"].append(text)
                continue
            # metadata bullet inside an item
            if current_item is not None:
                m = re.match(r"^(Source|Link|Published|Confidence|Novelty|Action|Why it matters):\s*(.+)", text)
                if m:
                    current_item["meta"][m.group(1)] = m.group(2)
                    continue
            # plain bullet in a section (e.g. collapsed GitHub activity)
            if current_section is not None:
                current_section.setdefault("loose_bullets", []).append(text)
            continue

        # plain text (summary, etc.)
        if in_section_name in ("Summary", "AI Summary"):
            result["summary_lines"].append(s)

    _flush_item()
    return result


# ── Phase 2: Render structured digest as themed HTML ───────────────────

def _render_section_header(name: str) -> str:
    return (
        f'<div style="margin:28px 0 14px;font-family:{_MONO};font-size:13px;'
        f'text-transform:uppercase;letter-spacing:0.12em;color:{_ACCENT};'
        f'padding-bottom:6px;border-bottom:1px solid {_LINE};">{_esc(name)}</div>'
    )


def _render_top_signals(signals: list[str]) -> str:
    if not signals:
        return ""
    items_html = ""
    for sig in signals:
        lane_m = re.match(r"^\[(\w+)\]\s+(.+)", sig)
        if lane_m:
            lane = _esc(lane_m.group(1))
            rest = _esc(lane_m.group(2))
            items_html += (
                f'<div style="padding:4px 0;font-size:14px;color:{_FG};line-height:1.6;">'
                f'<span style="display:inline-block;font-family:{_MONO};font-size:11px;'
                f'text-transform:uppercase;letter-spacing:0.06em;color:{_BG};'
                f'background:{_ACCENT_DIM};padding:1px 6px;margin-right:8px;">'
                f'{lane}</span>{rest}</div>'
            )
        else:
            items_html += (
                f'<div style="padding:3px 0;font-size:14px;color:{_FG};line-height:1.6;">'
                f'{_esc(sig)}</div>'
            )
    return (
        f'<div style="margin:20px 0 8px;padding:14px 16px;'
        f'border:1px solid rgba(130,242,138,0.25);background:rgba(130,242,138,0.06);">'
        f'<div style="font-family:{_MONO};font-size:12px;text-transform:uppercase;'
        f'letter-spacing:0.1em;color:{_ACCENT};padding-bottom:8px;">'
        f'<span style="font-weight:700;margin-right:6px;">&#x25B8;</span>Top Signals</div>'
        f'{items_html}</div>'
    )


def _render_fetch_issues(issues: list[str]) -> str:
    if not issues:
        return ""
    items_html = "".join(
        f'<li style="font-size:12px;color:{_MUTED};line-height:1.5;margin:1px 0;">{_esc(i)}</li>'
        for i in issues
    )
    return (
        f'<div style="margin:8px 0 0;padding:10px 12px;background:{_BG_ELEV};'
        f'border:1px solid {_LINE};">'
        f'<span style="font-family:{_MONO};font-size:11px;text-transform:uppercase;'
        f'letter-spacing:0.08em;color:{_MUTED};">Fetch Issues</span>'
        f'<ul style="margin:6px 0 0;padding-left:14px;list-style:none;">{items_html}</ul>'
        f'</div>'
    )


def _format_date_short(raw: str) -> str:
    """Try to produce 'Apr 08, 2026' from various date formats."""
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M:%S %Z",
                "%Y-%m-%d %H:%M:%S %z", "%Y-%m-%d %H:%M:%S"):
        try:
            from datetime import datetime as _dt
            dt = _dt.strptime(raw.strip(), fmt)
            return dt.strftime("%b %d, %Y")
        except ValueError:
            continue
    return raw.strip()[:20]


def _render_item_card(item: dict) -> str:
    meta = item["meta"]
    title_text = _esc(item["title"])
    link = meta.get("Link", "").strip()
    source = meta.get("Source", "")
    published = meta.get("Published", "")
    why = meta.get("Why it matters", "")
    confidence = meta.get("Confidence", "")
    novelty = meta.get("Novelty", "")
    action = meta.get("Action", "")

    # post-meta row: source + date (yellow, mono, uppercase — matches .post-meta)
    date_short = _format_date_short(published) if published else ""
    meta_parts = []
    if source:
        meta_parts.append(_esc(source))
    if date_short:
        meta_parts.append(_esc(date_short))
    meta_html = (
        f'<span style="margin-right:12px;">{meta_parts[0]}</span>'
        f'<span>{meta_parts[1]}</span>'
    ) if len(meta_parts) == 2 else _esc(source)

    post_meta = (
        f'<div style="font-family:{_MONO};font-size:12px;text-transform:uppercase;'
        f'letter-spacing:0.08em;color:{_WARNING};margin-bottom:4px;">'
        f'{meta_html}</div>'
    ) if meta_parts else ""

    # title — linked if we have a URL (matches .post-card h3 > a)
    if link:
        title_html = (
            f'<h3 style="font-family:{_SERIF};font-size:18px;line-height:1.15;'
            f'color:{_FG};margin:0 0 6px;font-weight:600;">'
            f'<a href="{_esc(link)}" style="{_LINK_STYLE}">{title_text}</a></h3>'
        )
    else:
        title_html = (
            f'<h3 style="font-family:{_SERIF};font-size:18px;line-height:1.15;'
            f'color:{_FG};margin:0 0 6px;font-weight:600;">{title_text}</h3>'
        )

    # why it matters — description paragraph (matches .post-card p)
    why_html = (
        f'<p style="font-size:14px;color:{_MUTED};line-height:1.5;margin:0 0 8px;">'
        f'{_esc(why)}</p>'
    ) if why else ""

    # confidence / novelty / action as small inline tags
    tags = []
    for val in (confidence, novelty, action):
        if val:
            tags.append(
                f'<span style="display:inline-block;font-family:{_MONO};font-size:10px;'
                f'text-transform:uppercase;letter-spacing:0.06em;color:{_MUTED};'
                f'border:1px solid {_LINE};padding:1px 6px;margin-right:4px;">'
                f'{_esc(val)}</span>'
            )
    tags_html = f'<div style="margin-top:2px;">{"".join(tags)}</div>' if tags else ""

    return (
        f'<div style="padding:14px 0 16px;border-bottom:1px dotted {_LINE};">'
        f'{post_meta}{title_html}{why_html}{tags_html}'
        f'</div>'
    )


def _render_summary(lines: list[str]) -> str:
    if not lines:
        return ""
    text = " ".join(_esc(l) for l in lines)
    return (
        f'<div style="margin:20px 0;padding:14px 16px;border-left:3px solid {_ACCENT_DIM};'
        f'background:{_BG_ELEV};">'
        f'<span style="font-family:{_MONO};font-size:11px;text-transform:uppercase;'
        f'letter-spacing:0.08em;color:{_ACCENT_DIM};display:block;margin-bottom:6px;">Synthesis</span>'
        f'<p style="font-family:{_SERIF};font-size:15px;color:{_FG};line-height:1.55;margin:0;">{text}</p>'
        f'</div>'
    )


def markdown_to_html(markdown: str) -> str:
    d = _parse_digest(markdown)

    body_parts: list[str] = []

    # top signals box (editor-note style)
    body_parts.append(_render_top_signals(d["top_signals"]))

    # summary if present
    body_parts.append(_render_summary(d["summary_lines"]))

    # lane sections with item cards
    for section in d["sections"]:
        body_parts.append(_render_section_header(section["name"]))
        for item in section["items"]:
            body_parts.append(_render_item_card(item))

    # fetch issues — demoted to bottom, subdued box
    body_parts.append(_render_fetch_issues(d["fetch_issues"]))

    body_content = "\n".join(p for p in body_parts if p)

    return f"""\
<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"></head>
<body style="margin:0;padding:0;{_BG_STYLE}font-family:{_SANS};">
<table width="100%" cellpadding="0" cellspacing="0" style="{_BG_STYLE}">
<tr><td align="center" style="padding:20px 12px;">
<table width="800" cellpadding="0" cellspacing="0" style="max-width:800px;width:100%;">

<!-- HEADER -->
<tr><td style="padding:20px 24px;border-bottom:1px solid {_LINE};{_BG_STYLE}">
<span style="font-family:{_MONO};font-size:22px;font-weight:700;letter-spacing:-0.04em;color:{_ACCENT};text-decoration:none;">Nodehome</span>
<span style="font-family:{_MONO};font-size:12px;text-transform:uppercase;letter-spacing:0.08em;color:{_MUTED};float:right;padding-top:8px;">Daily Sweep</span>
</td></tr>

<!-- TITLE -->
<tr><td style="padding:24px 24px 4px;{_BG_STYLE}">
<p style="font-family:{_MONO};font-size:11px;text-transform:uppercase;letter-spacing:0.08em;color:{_ACCENT_DIM};margin:0 0 8px;">local-first AI // field reports from owned systems</p>
<h1 style="font-family:{_SERIF};font-size:28px;line-height:1.05;letter-spacing:-0.03em;color:{_FG};margin:0;">{_esc(d["title"])}</h1>
<p style="font-family:{_MONO};font-size:12px;color:{_MUTED};margin:8px 0 0;">{_esc(d["timestamp"])}</p>
</td></tr>

<!-- BODY -->
<tr><td style="padding:8px 24px 32px;{_BG_STYLE}">
{body_content}
</td></tr>

<!-- FOOTER -->
<tr><td style="padding:16px 24px;border-top:1px solid {_LINE};{_BG_STYLE}">
<p style="font-family:{_MONO};font-size:12px;color:{_MUTED};margin:0;">Nodehome // AI after the browser.</p>
<p style="font-family:{_MONO};font-size:12px;color:{_MUTED};margin:4px 0 0;">Local models, weird rigs, real builders.</p>
</td></tr>

</table>
</td></tr>
</table>
</body>
</html>"""


def getenv_required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required env var: {name}")
    return value


def parse_recipients(value: str) -> list[str]:
    recipients = [item.strip() for item in value.split(",") if item.strip()]
    if not recipients:
        raise RuntimeError("DIGEST_TO_EMAILS is empty")
    return recipients


def send_email(
    api_key: str,
    from_email: str,
    from_name: str,
    recipients: list[str],
    subject: str,
    text_body: str,
    html_body: str,
) -> dict:
    payload = {
        "from": f"{from_name} <{from_email}>",
        "to": recipients,
        "subject": subject,
        "text": text_body,
        "html": html_body,
    }
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        RESEND_API_URL,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "SovereignNodeSweep/0.1 (+local)",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Send a daily sweep digest via Resend.")
    parser.add_argument("--input", dest="input_path", help="Explicit digest file path.")
    parser.add_argument("--profile", choices=("core", "extended", "all"), default="core")
    parser.add_argument("--date", dest="run_date", help="Digest date in YYYY-MM-DD format.")
    parser.add_argument("--dry-run", action="store_true", help="Render and validate without sending.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    enabled = os.getenv("DIGEST_EMAIL_ENABLED", "false").strip().lower() == "true"
    if not enabled:
        print("DIGEST_EMAIL_ENABLED is not true; skipping email send.")
        return 0

    if args.input_path:
        path = Path(args.input_path)
    else:
        run_date = date.fromisoformat(args.run_date) if args.run_date else date.today()
        path = digest_path(args.profile, run_date)

    if not path.exists():
        raise FileNotFoundError(f"Digest file not found: {path}")

    markdown = path.read_text(encoding="utf-8")
    text_body = markdown_to_text(markdown)
    html_body = markdown_to_html(markdown)

    recipients = parse_recipients(getenv_required("DIGEST_TO_EMAILS"))
    from_email = getenv_required("DIGEST_FROM_EMAIL")
    from_name = getenv_required("DIGEST_FROM_NAME")
    api_key = getenv_required("RESEND_API_KEY")
    subject = f"Daily Sweep - {path.stem}"

    if args.dry_run:
        print(json.dumps({"subject": subject, "to": recipients, "input": str(path)}, indent=2))
        return 0

    response = send_email(api_key, from_email, from_name, recipients, subject, text_body, html_body)
    print(json.dumps(response, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
