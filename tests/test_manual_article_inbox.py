import argparse
import contextlib
import io
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from sweeps import manual_article_inbox
from sweeps.run_daily import Source, diff_items_for_source, is_stale_item, read_local_jsonl, suppresses_age_filter


class ManualArticleInboxTests(unittest.TestCase):
    def test_append_article_writes_deduped_jsonl(self):
        with tempfile.TemporaryDirectory() as tmp:
            inbox = Path(tmp) / "manual.jsonl"
            args = argparse.Namespace(
                output=str(inbox),
                title="Orthrus: Memory-Efficient Parallel Token Generation",
                url="https://github.com/chiennv2000/orthrus",
                summary="Lossless decoding watch item for the stack digest.",
                lane="infra",
                published="2026-05-12",
                source="Manual Stack Article Inbox",
                confidence="manual-primary",
                novelty="operator-curated",
                action="watch",
                why="Serving-layer acceleration signal.",
                id="",
            )

            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(manual_article_inbox.append_article(args), 0)
                self.assertEqual(manual_article_inbox.append_article(args), 0)

            rows = [json.loads(line) for line in inbox.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["lane"], "infra")
            self.assertEqual(rows[0]["action"], "watch")
            self.assertEqual(rows[0]["why"], "Serving-layer acceleration signal.")

    def test_local_jsonl_preserves_manual_metadata_overrides(self):
        with tempfile.TemporaryDirectory() as tmp:
            inbox = Path(tmp) / "manual.jsonl"
            inbox.write_text(
                json.dumps(
                    {
                        "id": "manual-stack:test",
                        "title": "The CTF Scene Is Dead",
                        "link": "https://kabir.au/blog/the-ctf-scene-is-dead",
                        "published": "2026-05-01",
                        "summary": "Evaluation contamination signal.",
                        "lane": "scene",
                        "source": "Manual Stack Article Inbox",
                        "confidence": "manual-primary",
                        "novelty": "operator-curated",
                        "action": "review",
                        "why": "Useful warning for Nodechat eval design.",
                        "validation_status": "n/a",
                    },
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )
            source = Source(
                id="manual-stack-articles",
                name="Manual Stack Article Inbox",
                lane="workflow",
                kind="local_jsonl",
                url=str(inbox),
                confidence="manual-primary",
            )

            items = read_local_jsonl(source)

            self.assertEqual(len(items), 1)
            self.assertEqual(items[0]["lane"], "scene")
            self.assertEqual(items[0]["action"], "review")
            self.assertEqual(items[0]["why"], "Useful warning for Nodechat eval design.")

    def test_manual_stack_articles_emit_on_first_snapshot(self):
        source = Source(
            id="manual-stack-articles",
            name="Manual Stack Article Inbox",
            lane="workflow",
            kind="local_jsonl",
            url="docs/sweeps/inbox/manual_stack_articles.jsonl",
            confidence="manual-primary",
        )
        items = [
            {
                "id": "manual-stack:test",
                "title": "Orthrus: Memory-Efficient Parallel Token Generation",
                "link": "https://github.com/chiennv2000/orthrus",
                "published": "2026-05-12",
                "summary": "Lossless decoding watch item.",
            }
        ]

        new_items, bootstrap_notice = diff_items_for_source(
            source,
            items,
            previous_ids=set(),
            had_previous_state=False,
            bootstrap_emit=False,
            replay_current=False,
        )

        self.assertEqual(new_items, items)
        self.assertEqual(bootstrap_notice, "")
        self.assertTrue(is_stale_item(date(2026, 5, 16), {"published": "2026-05-01"}))
        self.assertTrue(suppresses_age_filter(source))

    def test_manual_stack_articles_emit_current_queue_even_after_state_exists(self):
        source = Source(
            id="manual-stack-articles",
            name="Manual Stack Article Inbox",
            lane="workflow",
            kind="local_jsonl",
            url="docs/sweeps/inbox/manual_stack_articles.jsonl",
            confidence="manual-primary",
        )
        items = [
            {
                "id": "manual-stack:test",
                "title": "delta-mem: Efficient Online Memory for LLMs",
                "link": "https://arxiv.org/abs/2605.12357",
                "published": "2026-05-12",
                "summary": "Memory watch item.",
            }
        ]

        new_items, bootstrap_notice = diff_items_for_source(
            source,
            items,
            previous_ids={"manual-stack:test"},
            had_previous_state=True,
            bootstrap_emit=False,
            replay_current=False,
        )

        self.assertEqual(new_items, items)
        self.assertEqual(bootstrap_notice, "")

    def test_normal_feed_sources_do_not_emit_on_first_snapshot(self):
        source = Source(
            id="example-feed",
            name="Example Feed",
            lane="infra",
            kind="feed",
            url="https://example.com/feed.xml",
            confidence="primary",
        )
        items = [
            {
                "id": "feed:test",
                "title": "Example release",
                "link": "https://example.com/release",
                "published": "2026-05-12",
                "summary": "Release note.",
            }
        ]

        new_items, bootstrap_notice = diff_items_for_source(
            source,
            items,
            previous_ids=set(),
            had_previous_state=False,
            bootstrap_emit=False,
            replay_current=False,
        )

        self.assertEqual(new_items, [])
        self.assertIn("bootstrapped state", bootstrap_notice)

    def test_other_local_jsonl_sources_do_not_emit_on_first_snapshot(self):
        source = Source(
            id="x-email-notifications",
            name="X Email Notifications",
            lane="scene",
            kind="local_jsonl",
            url="docs/sweeps/inbox/x_email_posts.jsonl",
            confidence="social-primary",
        )
        items = [
            {
                "id": "x-email:test",
                "title": "Example social post",
                "link": "https://x.com/example/status/1",
                "published": "2026-05-16",
                "summary": "Social item.",
            }
        ]

        new_items, bootstrap_notice = diff_items_for_source(
            source,
            items,
            previous_ids=set(),
            had_previous_state=False,
            bootstrap_emit=False,
            replay_current=False,
        )

        self.assertEqual(new_items, [])
        self.assertIn("bootstrapped state", bootstrap_notice)


if __name__ == "__main__":
    unittest.main()
