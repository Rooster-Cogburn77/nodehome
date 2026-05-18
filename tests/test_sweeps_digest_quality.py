import unittest
from datetime import date

from sweeps.run_daily import (
    Source,
    collapse_github_activity,
    entry_rank,
    heuristic_summary,
    is_consumer_gaming_hardware_noise,
    parse_page,
    select_digest_entries,
    validation_status,
    why_it_matters,
)


def entry(
    title,
    source="llama.cpp Releases",
    lane="infra",
    confidence="primary",
    published="2026-05-18T09:00:00Z",
    validation_status_value="n/a",
    followup_urls=None,
):
    return {
        "lane": lane,
        "source": source,
        "title": title,
        "link": f"https://example.test/{title.replace(' ', '-')}",
        "published": published,
        "confidence": confidence,
        "novelty": "established",
        "action": "watch",
        "why": "test",
        "validation_status": validation_status_value,
        "followup_urls": followup_urls or [],
    }


class SweepsDigestQualityTests(unittest.TestCase):
    def test_social_direct_posts_do_not_render_validation_noise(self):
        source = Source(
            id="social",
            name="Bluesky: @example.test",
            lane="hardware",
            kind="feed",
            url="at://example.test",
            confidence="social-primary",
        )

        self.assertEqual(validation_status(source, []), "n/a")

    def test_social_primary_does_not_outrank_primary_infra(self):
        primary = entry("b9209")
        social = entry(
            "Memtest86+ 8.10 adds better Intel Panther Lake support",
            source="Bluesky: @videocardz.com",
            lane="hardware",
            confidence="social-primary",
            validation_status_value="n/a",
        )

        self.assertLess(entry_rank(primary), entry_rank(social))

    def test_top_signal_selection_collapses_llamacpp_release_series(self):
        entries = [
            entry("b9209", published="2026-05-18T09:26:32Z"),
            entry("b9208", published="2026-05-18T08:26:32Z"),
            entry("b9204", published="2026-05-18T07:26:32Z"),
            entry("CUDA: Continue directly including cuda/iterator (#23102)", source="llama.cpp Commits"),
        ]

        selected = select_digest_entries(entries, 5)
        release_titles = [item["title"] for item in selected if item["source"] == "llama.cpp Releases"]

        self.assertEqual(release_titles, ["b9209"])

    def test_github_activity_pushes_are_collapsed_by_repo_and_day(self):
        entries = [
            entry(
                "simonw pushed watchfiles",
                source="Simon Willison GitHub Activity",
                lane="workflow",
                published="2026-05-18 00:07:12 UTC",
            ),
            entry(
                "simonw pushed watchfiles",
                source="Simon Willison GitHub Activity",
                lane="workflow",
                published="2026-05-18 00:01:46 UTC",
            ),
            entry(
                "simonw created a branch",
                source="Simon Willison GitHub Activity",
                lane="workflow",
                published="2026-05-17 23:56:55 UTC",
            ),
        ]

        collapsed = collapse_github_activity(entries)

        self.assertEqual(len(collapsed), 1)
        self.assertEqual(collapsed[0]["title"], "Simon Willison: pushed watchfiles (2 events)")

    def test_vllm_blog_page_extracts_article_cards_instead_of_nav_title(self):
        html = b"""
        <html><head><title>Blog | vLLM</title></head><body>
        <a href="/blog/announcing-verl-omni">
          <h2>Announcing VeRL-Omni: Unified RL Infrastructure for Multimodal Models</h2>
          <span>May 14, 2026</span><span>7 min read</span>
          <p>We are excited to introduce VeRL-Omni.</p>
        </a>
        <a href="/blog/tags/performance">Performance</a>
        <a href="/blog/turboquant-study">
          <h2>A First Comprehensive Study of TurboQuant: Accuracy and Performance</h2>
          <span>May 11, 2026</span><span>12 min read</span>
          <p>KV-cache quantization study.</p>
        </a>
        </body></html>
        """

        items = parse_page(html, "https://vllm.ai/blog")

        self.assertEqual(
            [item["title"] for item in items],
            [
                "Announcing VeRL-Omni: Unified RL Infrastructure for Multimodal Models",
                "A First Comprehensive Study of TurboQuant: Accuracy and Performance",
            ],
        )
        self.assertEqual(items[0]["link"], "https://vllm.ai/blog/announcing-verl-omni")
        self.assertEqual(items[0]["published"], "2026-05-14 00:00:00 UTC")

    def test_consumer_gaming_hardware_items_are_filtered(self):
        source = Source(
            id="bsky-videocardz",
            name="Bluesky: @videocardz.com",
            lane="hardware",
            kind="bluesky",
            url="at://videocardz.com",
            confidence="social-primary",
        )

        self.assertTrue(
            is_consumer_gaming_hardware_noise(
                source,
                {
                    "title": "Modder builds PlayStation 2 handheld with custom reverse-engineered mainboard",
                    "summary": "",
                },
            )
        )
        self.assertFalse(
            is_consumer_gaming_hardware_noise(
                source,
                {
                    "title": "Memtest86+ 8.10 adds better Intel Panther Lake support",
                    "summary": "",
                },
            )
        )

    def test_power_keyword_requires_real_power_context(self):
        source = Source(
            id="example",
            name="Example Blog",
            lane="workflow",
            kind="feed",
            url="https://example.test/feed.xml",
            confidence="primary",
        )

        why = why_it_matters(source, {"title": "A powerful LLM CLI trick for shebang lines"})

        self.assertNotIn("Power or thermal", why)

    def test_heuristic_summary_avoids_stock_boilerplate(self):
        entries = [
            entry(
                "Announcing VeRL-Omni: Unified RL Infrastructure for Multimodal Models",
                source="vLLM Blog",
                published="2026-05-14 00:00:00 UTC",
            ),
            entry("b9209", source="llama.cpp Releases", published="2026-05-18T09:26:32Z"),
            entry(
                "CUDA: Continue directly including cuda/iterator (#23102)",
                source="llama.cpp Commits",
                published="2026-05-17T21:00:00Z",
            ),
        ]

        summary = heuristic_summary("core", date(2026, 5, 18), entries, [])

        self.assertIn("VeRL-Omni", summary)
        self.assertNotIn("Busy day", summary)
        self.assertNotIn("A few things moved", summary)
        self.assertNotIn("No single breakthrough", summary)


if __name__ == "__main__":
    unittest.main()
