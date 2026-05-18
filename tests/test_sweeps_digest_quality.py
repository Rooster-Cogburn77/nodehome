import unittest

from sweeps.run_daily import (
    Source,
    collapse_github_activity,
    entry_rank,
    select_digest_entries,
    validation_status,
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


if __name__ == "__main__":
    unittest.main()
