import tempfile
import unittest
from pathlib import Path

from sweeps import llm_synthesize


class LlmSynthesizeTests(unittest.TestCase):
    def test_brief_path_for_date_respects_profile_suffix(self):
        original_dir = llm_synthesize.OPERATOR_DIR
        try:
            with tempfile.TemporaryDirectory() as tmp:
                llm_synthesize.OPERATOR_DIR = Path(tmp)
                core = Path(tmp) / "2026-05-16.md"
                extended = Path(tmp) / "2026-05-16.extended.md"
                core.write_text("core", encoding="utf-8")
                extended.write_text("extended", encoding="utf-8")

                self.assertEqual(llm_synthesize.brief_path_for_date("2026-05-16", "core"), core)
                self.assertEqual(llm_synthesize.brief_path_for_date("2026-05-16", "extended"), extended)
        finally:
            llm_synthesize.OPERATOR_DIR = original_dir

    def test_latest_brief_path_respects_profile_suffix(self):
        original_dir = llm_synthesize.OPERATOR_DIR
        try:
            with tempfile.TemporaryDirectory() as tmp:
                llm_synthesize.OPERATOR_DIR = Path(tmp)
                (Path(tmp) / "2026-05-15.md").write_text("old core", encoding="utf-8")
                latest_core = Path(tmp) / "2026-05-16.md"
                latest_extended = Path(tmp) / "2026-05-16.extended.md"
                latest_core.write_text("core", encoding="utf-8")
                latest_extended.write_text("extended", encoding="utf-8")

                self.assertEqual(llm_synthesize.latest_brief_path("core"), latest_core)
                self.assertEqual(llm_synthesize.latest_brief_path("extended"), latest_extended)
        finally:
            llm_synthesize.OPERATOR_DIR = original_dir


if __name__ == "__main__":
    unittest.main()
