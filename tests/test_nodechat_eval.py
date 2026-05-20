import json
import importlib.util
import pathlib
import subprocess
import sys
import tempfile
import unittest

from tests import nodechat_eval_corpus as corpus


ROOT = pathlib.Path(__file__).resolve().parents[1]


def load_eval_harness():
    path = ROOT / "scripts" / "nodechat_eval.py"
    spec = importlib.util.spec_from_file_location("nodechat_eval_test_harness", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class NodechatEvalCorpusTests(unittest.TestCase):
    def test_corpus_schema_is_explicit_and_reproducible(self):
        ids = [case["id"] for case in corpus.CORPUS]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertGreaterEqual(len(ids), 6)
        self.assertEqual(corpus.ACCEPTANCE_TARGETS["high_severity_unsupported_claims"], 0)
        self.assertLess(corpus.ACCEPTANCE_TARGETS["project_fact_unsupported_claim_rate_lt"], 0.10)
        self.assertIn("high_severity_zero_tolerance", corpus.CLAIM_TAXONOMY)
        self.assertIn("project_fact_unsupported", corpus.CLAIM_TAXONOMY)
        self.assertIn("out_of_scope", corpus.CLAIM_TAXONOMY)

        for case in corpus.CORPUS:
            self.assertIn("prompt", case)
            self.assertIn("context_sets", case)
            self.assertEqual(set(case["context_sets"]), {"zero", "correct", "irrelevant"})
            self.assertIn("expected", case)
            self.assertEqual(case["expected"]["high_severity_unsupported_claims"], 0)
            self.assertLess(case["expected"]["project_fact_unsupported_claim_rate_lt"], 0.10)
            if "commit" in case["prompt"]:
                self.assertRegex(case.get("hardcoded_commit", ""), r"^[0-9a-f]{7,40}$")

            for context_name, specs in case["context_sets"].items():
                self.assertIsInstance(specs, list, context_name)
                for spec in specs:
                    self.assertIn(spec.get("type"), {"repo_file", "repo_search", "git_commit"})
                    if spec["type"] == "repo_file":
                        self.assertIn("path", spec)
                    if spec["type"] == "repo_search":
                        self.assertIn("query", spec)
                    if spec["type"] == "git_commit":
                        self.assertRegex(spec.get("commit", ""), r"^[0-9a-f]{7,40}$")

    def test_eval_harness_dry_run_writes_jsonl(self):
        with tempfile.TemporaryDirectory() as raw:
            output = pathlib.Path(raw) / "eval.jsonl"
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "nodechat_eval.py"),
                    "--dry-run",
                    "--case",
                    "torrentleech_no_repo_artifact",
                    "--context",
                    "correct",
                    "--output",
                    str(output),
                ],
                cwd=str(ROOT),
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout)
            rows = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["case_id"], "torrentleech_no_repo_artifact")
            self.assertEqual(rows[0]["context"], "correct")
            self.assertEqual(rows[0]["status"], "dry-run")
            self.assertEqual(rows[0]["manual_score"]["high_severity_unsupported_claims"], None)

    def test_eval_session_disables_auto_routing_and_caps_output(self):
        harness = load_eval_harness()
        args = harness.parse_args(["--dry-run", "--max-tokens", "640"])
        config = harness.make_config(args)
        session = harness.prepare_eval_session(config, args)

        self.assertEqual(session["model_mode"], "manual")
        self.assertEqual(session["history_mode"], "off")
        self.assertEqual(session["repo_mode"], "off")
        self.assertEqual(session["web_mode"], "off")
        self.assertEqual(session["live_mode"], "off")
        self.assertEqual(session["_max_tokens_cap"], 640)

    def test_manual_score_overlay_drives_review_result(self):
        harness = load_eval_harness()
        rows = [
            {
                "case_id": "nodechat_file_behavior",
                "context": "correct",
                "status": "ok",
                "manual_score": {
                    "high_severity_unsupported_claims": None,
                    "project_fact_unsupported_claims": None,
                    "project_fact_claims_total": None,
                    "unsupported_claims": [],
                    "notes": "",
                },
            }
        ]

        incomplete = harness.summarize_eval_rows(rows)
        self.assertEqual(incomplete["result"], "incomplete")
        self.assertEqual(incomplete["needs_score"], [("nodechat_file_behavior", "correct")])

        scored = harness.apply_score_overrides(
            rows,
            {
                ("nodechat_file_behavior", "correct"): {
                    "high_severity_unsupported_claims": 0,
                    "project_fact_unsupported_claims": 0,
                    "project_fact_claims_total": 4,
                    "unsupported_claims": [],
                    "notes": "reviewed manually",
                }
            },
        )
        summary = harness.summarize_eval_rows(scored)
        self.assertEqual(summary["result"], "pass")
        self.assertEqual(summary["manual_scores_complete"], 1)
        self.assertEqual(summary["project_fact_unsupported_claim_rate"], 0.0)

    def test_manual_score_review_fails_on_high_severity_or_rate(self):
        harness = load_eval_harness()
        high_severity = [
            {
                "case_id": "hardcoded_commit_202bc41",
                "context": "correct",
                "status": "ok",
                "manual_score": {
                    "high_severity_unsupported_claims": 1,
                    "project_fact_unsupported_claims": 0,
                    "project_fact_claims_total": 3,
                },
            }
        ]
        self.assertEqual(harness.summarize_eval_rows(high_severity)["result"], "fail")

        high_rate = [
            {
                "case_id": "project_summary_current_stack",
                "context": "correct",
                "status": "ok",
                "manual_score": {
                    "high_severity_unsupported_claims": 0,
                    "project_fact_unsupported_claims": 1,
                    "project_fact_claims_total": 10,
                },
            }
        ]
        self.assertEqual(harness.summarize_eval_rows(high_rate)["result"], "fail")

    def test_score_template_defaults_gated_rows_to_zero(self):
        harness = load_eval_harness()
        row = {
            "case_id": "bmc_current_state",
            "context": "zero",
            "status": "gated",
            "response": "Unknown - not loaded.",
        }
        template = harness.score_template_row(row)
        self.assertEqual(template["high_severity_unsupported_claims"], 0)
        self.assertEqual(template["project_fact_unsupported_claims"], 0)
        self.assertEqual(template["project_fact_claims_total"], 0)
        self.assertEqual(template["response_excerpt"], "Unknown - not loaded.")

    def test_review_does_not_treat_dry_run_as_quality_pass(self):
        harness = load_eval_harness()
        rows = [
            {
                "case_id": "torrentleech_no_repo_artifact",
                "context": "correct",
                "status": "dry-run",
                "manual_score": {},
            }
        ]
        self.assertEqual(harness.summarize_eval_rows(rows)["result"], "dry-run")
