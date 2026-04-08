#!/usr/bin/env python3
from __future__ import annotations

import html
import json
import re
import shutil
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SITE_DIR = ROOT / "site"
PUBLIC_DIR = SITE_DIR / "public"
ASSETS_DIR = PUBLIC_DIR / "assets"
ARTICLES_DIR = PUBLIC_DIR / "articles"
MANIFEST_PATH = SITE_DIR / "content_manifest.json"
STYLE_PATH = SITE_DIR / "styles.css"


def load_manifest() -> dict:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def slugify(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9]+", "-", value.lower()).strip("-")
    return value or "post"


def format_date(value: str) -> str:
    return datetime.fromisoformat(value).strftime("%b %d, %Y")


def inline_format(text: str) -> str:
    escaped = html.escape(text)
    escaped = re.sub(r"`([^`]+)`", r"<code>\1</code>", escaped)
    escaped = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', escaped)
    return escaped


def markdown_to_html(markdown: str) -> str:
    lines = markdown.splitlines()
    blocks: list[str] = []
    in_list = False
    in_code = False
    code_lines: list[str] = []
    paragraph: list[str] = []

    def flush_paragraph() -> None:
        nonlocal paragraph
        if paragraph:
            text = " ".join(item.strip() for item in paragraph if item.strip())
            blocks.append(f"<p>{inline_format(text)}</p>")
            paragraph = []

    def close_list() -> None:
        nonlocal in_list
        if in_list:
            blocks.append("</ul>")
            in_list = False

    for raw in lines:
        line = raw.rstrip("\n")
        stripped = line.strip()

        if stripped.startswith("```"):
            flush_paragraph()
            close_list()
            if in_code:
                blocks.append(f"<pre><code>{html.escape(chr(10).join(code_lines))}</code></pre>")
                code_lines = []
                in_code = False
            else:
                in_code = True
            continue

        if in_code:
            code_lines.append(line)
            continue

        if not stripped:
            flush_paragraph()
            close_list()
            continue

        if stripped.startswith("# "):
            flush_paragraph()
            close_list()
            blocks.append(f"<h1>{inline_format(stripped[2:])}</h1>")
            continue
        if stripped.startswith("## "):
            flush_paragraph()
            close_list()
            blocks.append(f"<h2>{inline_format(stripped[3:])}</h2>")
            continue
        if stripped.startswith("### "):
            flush_paragraph()
            close_list()
            blocks.append(f"<h3>{inline_format(stripped[4:])}</h3>")
            continue
        if stripped.startswith("- "):
            flush_paragraph()
            if not in_list:
                blocks.append("<ul>")
                in_list = True
            blocks.append(f"<li>{inline_format(stripped[2:])}</li>")
            continue

        paragraph.append(stripped)

    flush_paragraph()
    close_list()
    if in_code:
        blocks.append(f"<pre><code>{html.escape(chr(10).join(code_lines))}</code></pre>")

    return "\n".join(blocks)


def render_layout(title: str, body: str, description: str) -> str:
    clean_title = title.strip()
    page_title = "Nodehome" if clean_title == "Nodehome" else f"{clean_title} // Nodehome"
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{html.escape(page_title)}</title>
  <meta name="description" content="{html.escape(description)}" />
  <link rel="stylesheet" href="/assets/styles.css" />
</head>
<body>
  <div class="page-grid">
    <header class="site-header">
      <a class="brand" href="/">Nodehome</a>
      <nav class="top-nav">
        <a href="/">Feed</a>
        <a href="#field-reports">Field Reports</a>
        <a href="#hardware">Hardware</a>
        <a href="#about">About</a>
      </nav>
    </header>
    {body}
    <footer class="site-footer">
      <div>Nodehome // AI after the browser.</div>
      <div>Local models, weird rigs, real builders.</div>
    </footer>
  </div>
</body>
</html>
"""


def render_index(site: dict, posts: list[dict]) -> str:
    latest = [post for post in posts if post["section"] == "Latest"]
    field_reports = [post for post in posts if post["section"] == "Field Reports"]
    hardware = [post for post in posts if post["section"] == "Hardware"]
    latest_post = max(posts, key=lambda post: post["date"])

    def post_card(post: dict) -> str:
        return f"""
        <article class="post-card">
          <div class="post-meta">
            <span>{html.escape(post['type'])}</span>
            <span>{format_date(post['date'])}</span>
          </div>
          <h3><a href="/articles/{post['slug']}.html">{html.escape(post['title'])}</a></h3>
          <p>{html.escape(post['excerpt'])}</p>
        </article>
        """

    body = f"""
    <main class="main-layout">
      <section class="hero">
        <p class="eyebrow">{html.escape(site['eyebrow'])}</p>
        <h1>{html.escape(site['title'])}</h1>
        <p class="lede">{html.escape(site['description'])}</p>
      </section>
      <section class="editor-note">
        <span class="prompt">&gt;</span>
        <p>{html.escape(site['editor_note'])}</p>
      </section>
      <div class="content-layout">
        <section class="feed">
          <div class="section-header"><h2>Latest</h2><span>live publication feed</span></div>
          {''.join(post_card(post) for post in latest)}
          <div id="field-reports" class="section-header"><h2>Field Reports</h2><span>builds, experiments, notes</span></div>
          {''.join(post_card(post) for post in field_reports)}
          <div id="hardware" class="section-header"><h2>Hardware</h2><span>machines, thermals, economics</span></div>
          {''.join(post_card(post) for post in hardware)}
        </section>
        <aside class="sidebar">
          <section class="sidebar-block">
            <h3>What this is</h3>
            <p>{html.escape(site['about'])}</p>
          </section>
          <section class="sidebar-block">
            <h3>Latest issue</h3>
            <p><a href="/articles/{latest_post['slug']}.html">{html.escape(latest_post['title'])}</a></p>
          </section>
          <section class="sidebar-block">
            <h3>Coverage</h3>
            <ul>
              <li>Local models</li>
              <li>Private inference</li>
              <li>Self-hosted agents</li>
              <li>Research sweeps</li>
              <li>Homelab and rack builds</li>
            </ul>
          </section>
          <section class="sidebar-block">
            <h3>Sovereign Node</h3>
            <p>Flagship build, recurring field report, and proof that owned AI infrastructure is real now.</p>
          </section>
          <section id="about" class="sidebar-block">
            <h3>Signal</h3>
            <p>{html.escape(site['signal'])}</p>
          </section>
        </aside>
      </div>
    </main>
    """
    return render_layout(site["title"], body, site["description"])


def render_article(site: dict, post: dict, source_markdown: str) -> str:
    article_html = markdown_to_html(source_markdown)
    body = f"""
    <main class="article-layout">
      <article class="article-shell">
        <a class="back-link" href="/">&larr; Back to Nodehome</a>
        <div class="post-meta">
          <span>{html.escape(post['type'])}</span>
          <span>{format_date(post['date'])}</span>
        </div>
        <h1>{html.escape(post['title'])}</h1>
        <p class="article-dek">{html.escape(post['excerpt'])}</p>
        <div class="article-body">
          {article_html}
        </div>
      </article>
    </main>
    """
    return render_layout(post["title"], body, post["excerpt"])


def main() -> int:
    manifest = load_manifest()
    site = manifest["site"]
    posts = manifest["posts"]

    if PUBLIC_DIR.exists():
        shutil.rmtree(PUBLIC_DIR)
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    ARTICLES_DIR.mkdir(parents=True, exist_ok=True)

    shutil.copy2(STYLE_PATH, ASSETS_DIR / "styles.css")

    index_html = render_index(site, posts)
    (PUBLIC_DIR / "index.html").write_text(index_html, encoding="utf-8")

    for post in posts:
        source_path = ROOT / post["source"]
        markdown = source_path.read_text(encoding="utf-8")
        article_html = render_article(site, post, markdown)
        (ARTICLES_DIR / f"{post['slug']}.html").write_text(article_html, encoding="utf-8")

    print(PUBLIC_DIR)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
