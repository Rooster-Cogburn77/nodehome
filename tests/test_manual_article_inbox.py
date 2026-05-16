import argparse
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from sweeps import manual_article_inbox
from sweeps.run_daily import Source, read_local_jsonl


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


if __name__ == "__main__":
    unittest.main()
