import contextlib
import importlib.util
import io
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
NODECHAT_PATH = ROOT / "scripts" / "nodechat.py"
SPEC = importlib.util.spec_from_file_location("nodechat", NODECHAT_PATH)
nodechat = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules["nodechat"] = nodechat
SPEC.loader.exec_module(nodechat)


def make_config(workspace: pathlib.Path, session_root: pathlib.Path):
    return nodechat.Config(
        base_url="http://127.0.0.1:8000/v1",
        model=nodechat.DEFAULT_MODEL,
        api_key="",
        stream=False,
        temperature=0.1,
        max_tokens=0,
        timeout=5,
        max_history_messages=8,
        session_root=session_root,
        workspace=workspace.resolve(),
        history_url="http://127.0.0.1:8765",
        history_token="",
        history_limit=3,
        cmd_timeout=5,
        live_ssh="",
        live_root="~/nodehome",
    )


class NodechatSafetyTests(unittest.TestCase):
    def test_save_session_does_not_raise_when_path_is_unwritable(self):
        with tempfile.TemporaryDirectory() as workspace_raw:
            workspace = pathlib.Path(workspace_raw)
            config = make_config(workspace, workspace / ".sessions")
            session = nodechat.make_session(config)
            original = nodechat.session_path
            try:
                nodechat.session_path = lambda config, session: workspace
                with contextlib.redirect_stderr(io.StringIO()) as buf:
                    path = nodechat.save_session(config, session)
            finally:
                nodechat.session_path = original
            self.assertEqual(path, workspace)
            self.assertIn("could not save nodechat session", buf.getvalue())

    def test_workspace_confinement_blocks_outside_paths(self):
        with tempfile.TemporaryDirectory() as workspace_raw, tempfile.TemporaryDirectory() as outside_raw:
            workspace = pathlib.Path(workspace_raw)
            outside = pathlib.Path(outside_raw) / "outside.txt"
            outside.write_text("secret-ish", encoding="utf-8")
            config = make_config(workspace, workspace / ".sessions")
            session = nodechat.make_session(config)

            self.assertIsNone(nodechat.workspace_confine_reason(config, session, workspace / "inside.txt"))
            reason = nodechat.workspace_confine_reason(config, session, outside)
            self.assertIn("outside nodechat workspace", reason or "")

    def test_read_refuses_outside_workspace(self):
        with tempfile.TemporaryDirectory() as workspace_raw, tempfile.TemporaryDirectory() as outside_raw:
            workspace = pathlib.Path(workspace_raw)
            outside = pathlib.Path(outside_raw) / "outside.txt"
            outside.write_text("outside", encoding="utf-8")
            config = make_config(workspace, workspace / ".sessions")
            session = nodechat.make_session(config)

            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                nodechat.command_read(config, session, str(outside))
            self.assertIn("outside nodechat workspace", buf.getvalue())

    def test_cmd_classifier_refuses_outside_path_and_risky_flags(self):
        with tempfile.TemporaryDirectory() as workspace_raw, tempfile.TemporaryDirectory() as outside_raw:
            workspace = pathlib.Path(workspace_raw)
            outside = pathlib.Path(outside_raw) / "outside.txt"
            outside.write_text("outside", encoding="utf-8")
            config = make_config(workspace, workspace / ".sessions")
            session = nodechat.make_session(config)

            cls, reason, _ = nodechat.classify_command(config, session, f"type {outside}")
            self.assertEqual(cls, "refused")
            self.assertIn("outside nodechat workspace", reason)

            cls, reason, _ = nodechat.classify_command(config, session, "rg --hidden nodechat")
            self.assertEqual(cls, "refused")
            self.assertIn("hidden/no-ignore", reason)

            cls, reason, _ = nodechat.classify_command(config, session, "git pull --ff-only")
            self.assertEqual(cls, "network")
            self.assertIn("refused", reason)

    def test_cmd_queues_selected_git_network_command(self):
        with tempfile.TemporaryDirectory() as workspace_raw:
            workspace = pathlib.Path(workspace_raw)
            config = make_config(workspace, workspace / ".sessions")
            session = nodechat.make_session(config)

            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                nodechat.command_cmd(config, session, "git pull --ff-only")

            text = buf.getvalue()
            self.assertIn("APPROVAL_REQUIRED", text)
            self.assertIn("/approve a1", text)
            approvals = session.get("approvals", [])
            self.assertEqual(len(approvals), 1)
            self.assertEqual(approvals[0]["id"], "a1")
            self.assertEqual(approvals[0]["status"], "pending")

    def test_cmd_refuses_destructive_without_approval_queue(self):
        with tempfile.TemporaryDirectory() as workspace_raw:
            workspace = pathlib.Path(workspace_raw)
            config = make_config(workspace, workspace / ".sessions")
            session = nodechat.make_session(config)

            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                nodechat.command_cmd(config, session, "del tmp.txt")

            self.assertIn("COMMAND_REFUSED", buf.getvalue())
            self.assertEqual(session.get("approvals"), [])

    def test_audit_records_refused_and_queued_commands(self):
        with tempfile.TemporaryDirectory() as workspace_raw:
            workspace = pathlib.Path(workspace_raw)
            config = make_config(workspace, workspace / ".sessions")
            session = nodechat.make_session(config)

            with contextlib.redirect_stdout(io.StringIO()):
                nodechat.command_cmd(config, session, "del tmp.txt")
                nodechat.command_cmd(config, session, "git fetch")

            rows = nodechat.read_recent_audit(config, 10)
            event_types = [row["event_type"] for row in rows]
            self.assertIn("command_refused", event_types)
            self.assertIn("approval_queued", event_types)
            refused = next(row for row in rows if row["event_type"] == "command_refused")
            self.assertEqual(refused["exit_code"], "refused")
            self.assertIn("output_sha256", refused)
            queued = next(row for row in rows if row["event_type"] == "approval_queued")
            self.assertEqual(queued["approval_id"], "a1")

    def test_approve_executes_queued_command_once(self):
        with tempfile.TemporaryDirectory() as workspace_raw:
            workspace = pathlib.Path(workspace_raw)
            config = make_config(workspace, workspace / ".sessions")
            session = nodechat.make_session(config)
            with contextlib.redirect_stdout(io.StringIO()):
                nodechat.command_cmd(config, session, "git fetch")

            original = nodechat.run_approved_command
            try:
                nodechat.run_approved_command = lambda config, session, parts, approval_reason: (
                    0,
                    "fetch ok",
                    "C:\\Program Files\\Git\\cmd\\git.exe",
                    True,
                )
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    nodechat.command_approve(config, session, "a1")
            finally:
                nodechat.run_approved_command = original

            text = buf.getvalue()
            self.assertIn("COMMAND_OUTPUT", text)
            self.assertIn("approval_id: a1", text)
            self.assertIn("fetch ok", text)
            self.assertEqual(session["approvals"][0]["status"], "executed")

            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                nodechat.command_approve(config, session, "a1")
            self.assertIn("already executed", buf.getvalue())
            rows = nodechat.read_recent_audit(config, 10)
            self.assertTrue(any(row["event_type"] == "approval_executed" for row in rows))

    def test_approve_blocks_dirty_git_push_without_execution(self):
        with tempfile.TemporaryDirectory() as workspace_raw:
            workspace = pathlib.Path(workspace_raw)
            config = make_config(workspace, workspace / ".sessions")
            session = nodechat.make_session(config)
            (workspace / "dirty.txt").write_text("dirty", encoding="utf-8")
            subprocess_result = subprocess.run(
                [shutil.which("git") or "git", "init"],
                cwd=str(workspace),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                check=False,
            )
            if subprocess_result.returncode != 0:
                self.skipTest("git init failed")
            with contextlib.redirect_stdout(io.StringIO()):
                nodechat.command_cmd(config, session, "git push")

            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                nodechat.command_approve(config, session, "a1")

            text = buf.getvalue()
            self.assertIn("exit_code: blocked", text)
            self.assertIn("working tree is not clean", text)
            self.assertEqual(session["approvals"][0]["status"], "blocked")
            rows = nodechat.read_recent_audit(config, 10)
            self.assertTrue(any(row["event_type"] == "approval_blocked" for row in rows))

    def test_non_approvable_git_network_variants_do_not_queue(self):
        with tempfile.TemporaryDirectory() as workspace_raw:
            workspace = pathlib.Path(workspace_raw)
            config = make_config(workspace, workspace / ".sessions")
            session = nodechat.make_session(config)
            commands = [
                "git fetch origin main",
                "git fetch --prune --tags",
                "git pull",
                "git pull --ff-only --rebase",
                "git push origin main",
                "git push --force",
            ]
            for command in commands:
                with self.subTest(command=command):
                    buf = io.StringIO()
                    with contextlib.redirect_stdout(buf):
                        nodechat.command_cmd(config, session, command)
                    self.assertIn("COMMAND_REFUSED", buf.getvalue())
            self.assertEqual(session.get("approvals"), [])

    def test_apply_check_and_confirm_write_audit_events(self):
        with tempfile.TemporaryDirectory() as workspace_raw:
            workspace = pathlib.Path(workspace_raw)
            target = workspace / "file.txt"
            target.write_text("alpha\nbeta\n", encoding="utf-8")
            config = make_config(workspace, workspace / ".sessions")
            session = nodechat.make_session(config)
            session["proposals"] = [
                {
                    "created_at": "2026-05-15T00:00:00+00:00",
                    "path": str(target),
                    "instruction": "update beta",
                    "proposal": "\n".join(
                        [
                            "--- file.txt",
                            "+++ file.txt",
                            "@@ -1,2 +1,2 @@",
                            " alpha",
                            "-beta",
                            "+beta-updated",
                            "",
                        ]
                    ),
                }
            ]

            with contextlib.redirect_stdout(io.StringIO()):
                nodechat.command_apply(config, session, "1 --check")
                nodechat.command_apply(config, session, "1 --confirm")

            self.assertEqual(target.read_text(encoding="utf-8").strip(), "alpha\nbeta-updated")
            rows = nodechat.read_recent_audit(config, 10)
            event_types = [row["event_type"] for row in rows]
            self.assertIn("apply_checked", event_types)
            self.assertIn("apply_confirmed", event_types)
            confirmed = next(row for row in rows if row["event_type"] == "apply_confirmed")
            self.assertTrue(pathlib.Path(confirmed["backup_path"]).exists())

    def test_undo_apply_check_does_not_write(self):
        with tempfile.TemporaryDirectory() as workspace_raw:
            workspace = pathlib.Path(workspace_raw)
            target = workspace / "file.txt"
            target.write_text("alpha\nbeta\n", encoding="utf-8")
            config = make_config(workspace, workspace / ".sessions")
            session = nodechat.make_session(config)
            session["proposals"] = [
                {
                    "created_at": "2026-05-15T00:00:00+00:00",
                    "path": str(target),
                    "instruction": "update beta",
                    "proposal": "\n".join(
                        [
                            "--- file.txt",
                            "+++ file.txt",
                            "@@ -1,2 +1,2 @@",
                            " alpha",
                            "-beta",
                            "+beta-updated",
                            "",
                        ]
                    ),
                }
            ]
            with contextlib.redirect_stdout(io.StringIO()):
                nodechat.command_apply(config, session, "1 --confirm")
                nodechat.command_undo_apply(config, session, "latest --check")
            self.assertEqual(target.read_text(encoding="utf-8"), "alpha\nbeta-updated")
            self.assertFalse(session["proposals"][0].get("undone_at"))
            rows = nodechat.read_recent_audit(config, 10)
            self.assertTrue(any(row["event_type"] == "undo_apply_checked" for row in rows))

    def test_undo_apply_restores_backup_and_records_audit(self):
        with tempfile.TemporaryDirectory() as workspace_raw:
            workspace = pathlib.Path(workspace_raw)
            target = workspace / "file.txt"
            target.write_text("alpha\nbeta\n", encoding="utf-8")
            config = make_config(workspace, workspace / ".sessions")
            session = nodechat.make_session(config)
            session["proposals"] = [
                {
                    "created_at": "2026-05-15T00:00:00+00:00",
                    "path": str(target),
                    "instruction": "update beta",
                    "proposal": "\n".join(
                        [
                            "--- file.txt",
                            "+++ file.txt",
                            "@@ -1,2 +1,2 @@",
                            " alpha",
                            "-beta",
                            "+beta-updated",
                            "",
                        ]
                    ),
                }
            ]
            with contextlib.redirect_stdout(io.StringIO()):
                nodechat.command_apply(config, session, "1 --confirm")
                nodechat.command_undo_apply(config, session, "latest")
            self.assertEqual(target.read_text(encoding="utf-8"), "alpha\nbeta\n")
            proposal = session["proposals"][0]
            self.assertTrue(proposal.get("undone_at"))
            self.assertTrue(pathlib.Path(proposal["undo_backup_path"]).exists())
            rows = nodechat.read_recent_audit(config, 20)
            self.assertTrue(any(row["event_type"] == "undo_apply_confirmed" for row in rows))

    def test_undo_apply_refuses_after_post_apply_file_change(self):
        with tempfile.TemporaryDirectory() as workspace_raw:
            workspace = pathlib.Path(workspace_raw)
            target = workspace / "file.txt"
            target.write_text("alpha\nbeta\n", encoding="utf-8")
            config = make_config(workspace, workspace / ".sessions")
            session = nodechat.make_session(config)
            session["proposals"] = [
                {
                    "created_at": "2026-05-15T00:00:00+00:00",
                    "path": str(target),
                    "instruction": "update beta",
                    "proposal": "\n".join(
                        [
                            "--- file.txt",
                            "+++ file.txt",
                            "@@ -1,2 +1,2 @@",
                            " alpha",
                            "-beta",
                            "+beta-updated",
                            "",
                        ]
                    ),
                }
            ]
            with contextlib.redirect_stdout(io.StringIO()):
                nodechat.command_apply(config, session, "1 --confirm")
            target.write_text("alpha\nchanged-again\n", encoding="utf-8")
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                nodechat.command_undo_apply(config, session, "latest")
            self.assertIn("no longer matches", buf.getvalue())
            self.assertEqual(target.read_text(encoding="utf-8"), "alpha\nchanged-again\n")
            self.assertFalse(session["proposals"][0].get("undone_at"))
            rows = nodechat.read_recent_audit(config, 20)
            self.assertTrue(any(row["event_type"] == "undo_apply_refused" for row in rows))

    def test_undo_apply_refuses_unapplied_numeric_proposal_directly(self):
        with tempfile.TemporaryDirectory() as workspace_raw:
            workspace = pathlib.Path(workspace_raw)
            target = workspace / "file.txt"
            target.write_text("alpha\nbeta\n", encoding="utf-8")
            config = make_config(workspace, workspace / ".sessions")
            session = nodechat.make_session(config)
            session["proposals"] = [
                {
                    "created_at": "2026-05-15T00:00:00+00:00",
                    "path": str(target),
                    "instruction": "update beta",
                    "proposal": "--- file.txt\n+++ file.txt\n",
                }
            ]
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                nodechat.command_undo_apply(config, session, "1")
            self.assertIn("has not been applied", buf.getvalue())

    def test_apply_refuses_ambiguous_repeated_hunks(self):
        original = "alpha\nbeta\nalpha\nbeta\n"
        patch = "\n".join(
            [
                "--- file.txt",
                "+++ file.txt",
                "@@ -99,2 +99,2 @@",
                " alpha",
                "-beta",
                "+beta-updated",
                "",
            ]
        )
        with self.assertRaisesRegex(RuntimeError, "multiple times"):
            nodechat.apply_unified_diff_text(original, patch)

    def test_apply_uses_exact_preferred_hunk_when_context_repeats(self):
        original = "alpha\nbeta\nalpha\nbeta\n"
        patch = "\n".join(
            [
                "--- file.txt",
                "+++ file.txt",
                "@@ -3,2 +3,2 @@",
                " alpha",
                "-beta",
                "+beta-updated",
                "",
            ]
        )
        updated = nodechat.apply_unified_diff_text(original, patch)
        self.assertEqual(updated, "alpha\nbeta\nalpha\nbeta-updated\n")

    def test_readonly_command_reports_resolved_executable(self):
        if not shutil.which("git"):
            self.skipTest("git is not available")
        with tempfile.TemporaryDirectory() as workspace_raw:
            workspace = pathlib.Path(workspace_raw)
            config = make_config(workspace, workspace / ".sessions")
            session = nodechat.make_session(config)
            exit_code, output, executable = nodechat.run_readonly_command(
                config, session, ["git", "--version"]
            )
            self.assertEqual(exit_code, 0)
            self.assertIn("git", output.lower())
            self.assertTrue(executable)
            self.assertNotEqual(executable, "git")


class NodechatAutoRoutingTests(unittest.TestCase):
    def test_history_pattern_matches_prior_decision_phrasing(self):
        for prompt in (
            "what did we decide about gpu2?",
            "remind me where we left off",
            "previously we capped gpu0 at 300W",
            "history of the rdimm dispute",
            "did we ever fix the bmc fan thresholds?",
        ):
            with self.subTest(prompt=prompt):
                self.assertEqual(nodechat.detect_history_query(prompt), prompt.strip())

    def test_history_pattern_misses_idle_or_general_prompts(self):
        for prompt in (
            "hello there",
            "explain transformers in two lines",
            "what is the current state of the build?",
            "",
            "   ",
        ):
            with self.subTest(prompt=prompt):
                self.assertIsNone(nodechat.detect_history_query(prompt))

    def test_repo_routing_resolves_named_files_and_runbooks_and_paths(self):
        with tempfile.TemporaryDirectory() as workspace_raw:
            workspace = pathlib.Path(workspace_raw)
            (workspace / "docs").mkdir()
            (workspace / "docs" / "CURRENT_STATE.md").write_text("state", encoding="utf-8")
            (workspace / "docs" / "SESSION_LOG.md").write_text("log", encoding="utf-8")
            (workspace / "CLAUDE.md").write_text("claude", encoding="utf-8")
            (workspace / "docs" / "runbooks").mkdir()
            (workspace / "docs" / "runbooks" / "nodechat-scope.md").write_text(
                "scope", encoding="utf-8"
            )
            (workspace / "scripts").mkdir()
            (workspace / "scripts" / "tool.py").write_text("print('x')", encoding="utf-8")
            config = make_config(workspace, workspace / ".sessions")
            session = nodechat.make_session(config)

            cases = {
                "open CURRENT_STATE for the gpu3 cable status": ["docs/CURRENT_STATE.md"],
                "what is in CLAUDE.md right now?": ["CLAUDE.md"],
                "walk me through nodechat-scope": ["docs/runbooks/nodechat-scope.md"],
                "look at scripts/tool.py": ["scripts/tool.py"],
            }
            for prompt, expected_rels in cases.items():
                with self.subTest(prompt=prompt):
                    paths = nodechat.detect_repo_targets(config, session, prompt)
                    rels = [nodechat.display_path(config, session, p) for p in paths]
                    self.assertEqual(rels, expected_rels)

    def test_repo_vague_topic_phrases_do_not_route(self):
        with tempfile.TemporaryDirectory() as workspace_raw:
            workspace = pathlib.Path(workspace_raw)
            (workspace / "docs").mkdir()
            (workspace / "docs" / "CURRENT_STATE.md").write_text("state", encoding="utf-8")
            (workspace / "scripts").mkdir()
            (workspace / "scripts" / "build_operator_brief.py").write_text(
                "x", encoding="utf-8"
            )
            config = make_config(workspace, workspace / ".sessions")
            session = nodechat.make_session(config)

            for prompt in (
                "what is the current state of the build?",
                "how does build_operator_brief.py work?",
                "tell me about the project",
                "this codebase looks interesting",
                "hello there",
            ):
                with self.subTest(prompt=prompt):
                    paths = nodechat.detect_repo_targets(config, session, prompt)
                    self.assertEqual(paths, [])

    def test_repo_routing_caps_at_two_files(self):
        with tempfile.TemporaryDirectory() as workspace_raw:
            workspace = pathlib.Path(workspace_raw)
            (workspace / "docs").mkdir()
            (workspace / "docs" / "CURRENT_STATE.md").write_text("a", encoding="utf-8")
            (workspace / "docs" / "SESSION_LOG.md").write_text("b", encoding="utf-8")
            (workspace / "CLAUDE.md").write_text("c", encoding="utf-8")
            (workspace / "SCRATCH.md").write_text("d", encoding="utf-8")
            config = make_config(workspace, workspace / ".sessions")
            session = nodechat.make_session(config)
            paths = nodechat.detect_repo_targets(
                config,
                session,
                "compare CURRENT_STATE and SESSION_LOG and CLAUDE.md and SCRATCH.md",
            )
            self.assertEqual(len(paths), nodechat.REPO_AUTO_LIMIT)

    def test_repo_routing_refuses_secret_pathlike_targets(self):
        with tempfile.TemporaryDirectory() as workspace_raw:
            workspace = pathlib.Path(workspace_raw)
            (workspace / "scripts").mkdir()
            (workspace / "scripts" / "credentials.json").write_text("{}", encoding="utf-8")
            config = make_config(workspace, workspace / ".sessions")
            session = nodechat.make_session(config)
            paths = nodechat.detect_repo_targets(
                config, session, "open scripts/credentials.json"
            )
            self.assertEqual(paths, [])

    def test_auto_route_skips_when_modes_off(self):
        with tempfile.TemporaryDirectory() as workspace_raw:
            workspace = pathlib.Path(workspace_raw)
            (workspace / "docs").mkdir()
            (workspace / "docs" / "CURRENT_STATE.md").write_text("state", encoding="utf-8")
            config = make_config(workspace, workspace / ".sessions")
            session = nodechat.make_session(config)
            session["history_mode"] = "off"
            session["repo_mode"] = "off"
            disclosure = nodechat.auto_route_turn(
                config,
                session,
                "what did we decide about CURRENT_STATE?",
            )
            self.assertIsNone(disclosure)
            self.assertEqual(session.get("context_blocks"), [])

    def test_auto_route_history_records_audit_skip_on_endpoint_error(self):
        with tempfile.TemporaryDirectory() as workspace_raw:
            workspace = pathlib.Path(workspace_raw)
            config = make_config(workspace, workspace / ".sessions")
            session = nodechat.make_session(config)
            original = nodechat.fetch_history_context
            try:
                nodechat.fetch_history_context = lambda config, query, force=True: (_ for _ in ()).throw(
                    RuntimeError("boom")
                )
                disclosure = nodechat.auto_route_turn(
                    config, session, "what did we decide about gpu2?"
                )
            finally:
                nodechat.fetch_history_context = original
            self.assertIsNotNone(disclosure)
            self.assertIn("history(error", disclosure or "")
            rows = nodechat.read_recent_audit(config, 10)
            self.assertTrue(
                any(r["event_type"] == "auto_route_history" and r.get("status") == "error" for r in rows)
            )
            # On error, no context block should be added.
            self.assertEqual(
                [b for b in session.get("context_blocks", []) if b.get("source") == "auto-history"],
                [],
            )

    def test_auto_route_emits_disclosure_and_evidence_blocks_for_repo(self):
        with tempfile.TemporaryDirectory() as workspace_raw:
            workspace = pathlib.Path(workspace_raw)
            (workspace / "docs").mkdir()
            (workspace / "docs" / "CURRENT_STATE.md").write_text("state", encoding="utf-8")
            config = make_config(workspace, workspace / ".sessions")
            session = nodechat.make_session(config)
            disclosure = nodechat.auto_route_turn(
                config, session, "look at CURRENT_STATE for the gpu3 cable"
            )
            self.assertIsNotNone(disclosure)
            self.assertIn("repo(read", disclosure or "")
            blocks = session.get("context_blocks", [])
            self.assertEqual(len(blocks), 1)
            self.assertEqual(blocks[0].get("source"), "auto-repo")
            prov = blocks[0].get("provenance") or {}
            self.assertEqual(prov.get("rel"), "docs/CURRENT_STATE.md")
            self.assertGreater(int(prov.get("chars", 0)), 0)

    def test_auto_route_does_not_block_when_audit_path_is_unwritable(self):
        with tempfile.TemporaryDirectory() as workspace_raw:
            workspace = pathlib.Path(workspace_raw)
            (workspace / "docs").mkdir()
            (workspace / "docs" / "CURRENT_STATE.md").write_text("state", encoding="utf-8")
            config = make_config(workspace, workspace / ".sessions")
            session = nodechat.make_session(config)
            original = nodechat.audit_log_path
            try:
                nodechat.audit_log_path = lambda config: workspace
                disclosure = nodechat.auto_route_turn(
                    config, session, "look at CURRENT_STATE for the gpu3 cable"
                )
            finally:
                nodechat.audit_log_path = original
            self.assertIsNotNone(disclosure)
            self.assertIn("repo(read", disclosure or "")
            self.assertEqual(session["context_blocks"][0].get("source"), "auto-repo")

    def test_web_routing_detects_urls_and_fresh_public_queries(self):
        url_targets = nodechat.detect_web_targets("check this https://example.com/release.")
        self.assertEqual(url_targets["urls"], ["https://example.com/release"])
        self.assertIsNone(url_targets["query"])

        search_targets = nodechat.detect_web_targets("what is the latest vLLM release?")
        self.assertEqual(search_targets["query"], "what is the latest vLLM release?")
        self.assertEqual(search_targets["urls"], [])

        local_status = nodechat.detect_web_targets("what is the current vLLM status on our node?")
        self.assertIsNone(local_status)

    def test_auto_route_web_skips_when_web_mode_off(self):
        with tempfile.TemporaryDirectory() as workspace_raw:
            workspace = pathlib.Path(workspace_raw)
            config = make_config(workspace, workspace / ".sessions")
            session = nodechat.make_session(config)
            session["web_mode"] = "off"
            original = nodechat.web_search_context
            try:
                nodechat.web_search_context = lambda query, timeout: (_ for _ in ()).throw(
                    AssertionError("web search should not run")
                )
                disclosure = nodechat.auto_route_turn(
                    config, session, "what is the latest vLLM release?"
                )
            finally:
                nodechat.web_search_context = original
            self.assertIsNone(disclosure)
            self.assertEqual(session.get("context_blocks"), [])

    def test_auto_route_web_search_adds_disclosure_provenance_and_audit(self):
        with tempfile.TemporaryDirectory() as workspace_raw:
            workspace = pathlib.Path(workspace_raw)
            config = make_config(workspace, workspace / ".sessions")
            session = nodechat.make_session(config)
            original = nodechat.web_search_context
            try:
                nodechat.web_search_context = lambda query, timeout: (
                    "query: latest vLLM release\n- vLLM release\n  https://example.com",
                    1,
                )
                disclosure = nodechat.auto_route_turn(
                    config, session, "what is the latest vLLM release?"
                )
            finally:
                nodechat.web_search_context = original

            self.assertIsNotNone(disclosure)
            self.assertIn("web(search 1 results", disclosure or "")
            blocks = session.get("context_blocks", [])
            self.assertEqual(len(blocks), 1)
            self.assertEqual(blocks[0].get("source"), "auto-web-search")
            prov = blocks[0].get("provenance") or {}
            self.assertEqual(prov.get("results"), 1)
            rows = nodechat.read_recent_audit(config, 10)
            self.assertTrue(
                any(
                    r["event_type"] == "auto_route_web"
                    and r.get("status") == "ok"
                    and r.get("action") == "search"
                    for r in rows
                )
            )

    def test_auto_route_web_fetch_error_is_disclosed_and_audited(self):
        with tempfile.TemporaryDirectory() as workspace_raw:
            workspace = pathlib.Path(workspace_raw)
            config = make_config(workspace, workspace / ".sessions")
            session = nodechat.make_session(config)
            original = nodechat.web_fetch_context
            try:
                nodechat.web_fetch_context = lambda url, timeout: (_ for _ in ()).throw(
                    RuntimeError("network down")
                )
                disclosure = nodechat.auto_route_turn(config, session, "check https://example.com")
            finally:
                nodechat.web_fetch_context = original
            self.assertIsNotNone(disclosure)
            self.assertIn("web(fetch error", disclosure or "")
            self.assertEqual(
                [b for b in session.get("context_blocks", []) if b.get("source") == "auto-web-fetch"],
                [],
            )
            rows = nodechat.read_recent_audit(config, 10)
            self.assertTrue(
                any(
                    r["event_type"] == "auto_route_web"
                    and r.get("status") == "error"
                    and r.get("action") == "fetch"
                    for r in rows
                )
            )

    def test_live_routing_detects_status_prompts_and_skips_history_style_prompts(self):
        self.assertEqual(
            nodechat.detect_live_targets("is vLLM running and are GPU temps okay?"),
            ["gpu", "vllm"],
        )
        self.assertEqual(
            nodechat.detect_live_targets("check docker and storage status on the node"),
            ["health", "docker", "storage"],
        )
        self.assertEqual(
            nodechat.detect_live_targets("what did we decide about GPU2?"),
            [],
        )

    def test_live_command_uses_optional_ssh_target_for_fixed_checks(self):
        with tempfile.TemporaryDirectory() as workspace_raw:
            workspace = pathlib.Path(workspace_raw)
            config = make_config(workspace, workspace / ".sessions")
            config.live_ssh = "bmoore_77@192.168.1.198"
            self.assertEqual(nodechat.parse_live_arg(""), (["health"], ""))
            argv, target = nodechat.live_command_for_check(config, "health")
            self.assertEqual(target, "ssh:bmoore_77@192.168.1.198")
            self.assertEqual(argv[:3], ["ssh", "-o", "BatchMode=yes"])
            self.assertIn("cd ~/nodehome && ./scripts/healthcheck.sh", argv)

    def test_auto_route_live_skips_when_live_mode_off(self):
        with tempfile.TemporaryDirectory() as workspace_raw:
            workspace = pathlib.Path(workspace_raw)
            config = make_config(workspace, workspace / ".sessions")
            session = nodechat.make_session(config)
            session["live_mode"] = "off"
            original = nodechat.run_live_checks
            try:
                nodechat.run_live_checks = lambda config, checks, extra="": (_ for _ in ()).throw(
                    AssertionError("live checks should not run")
                )
                disclosure = nodechat.auto_route_turn(
                    config, session, "is vLLM running and are GPU temps okay?"
                )
            finally:
                nodechat.run_live_checks = original
            self.assertIsNone(disclosure)
            self.assertEqual(session.get("context_blocks"), [])

    def test_auto_route_live_adds_disclosure_provenance_and_audit(self):
        with tempfile.TemporaryDirectory() as workspace_raw:
            workspace = pathlib.Path(workspace_raw)
            config = make_config(workspace, workspace / ".sessions")
            session = nodechat.make_session(config)
            original = nodechat.run_live_checks
            try:
                nodechat.run_live_checks = lambda config, checks, extra="": [
                    {
                        "check": check,
                        "target": "local",
                        "command": check,
                        "exit_code": 0,
                        "executable": "mock",
                        "output": f"{check} ok",
                    }
                    for check in checks
                ]
                disclosure = nodechat.auto_route_turn(
                    config, session, "is vLLM running and are GPU temps okay?"
                )
            finally:
                nodechat.run_live_checks = original

            self.assertIsNotNone(disclosure)
            self.assertIn("live(gpu, vllm)", disclosure or "")
            blocks = session.get("context_blocks", [])
            self.assertEqual(len(blocks), 1)
            self.assertEqual(blocks[0].get("source"), "auto-live")
            prov = blocks[0].get("provenance") or {}
            self.assertEqual(prov.get("checks"), ["gpu", "vllm"])
            rows = nodechat.read_recent_audit(config, 10)
            self.assertTrue(
                any(
                    r["event_type"] == "auto_route_live"
                    and r.get("status") == "ok"
                    and r.get("checks") == ["gpu", "vllm"]
                    for r in rows
                )
            )

    def test_live_smart_requires_dev_path(self):
        with tempfile.TemporaryDirectory() as workspace_raw:
            workspace = pathlib.Path(workspace_raw)
            config = make_config(workspace, workspace / ".sessions")
            with self.assertRaisesRegex(RuntimeError, "usage: /live smart"):
                nodechat.live_command_for_check(config, "smart", "C:\\Users\\bmoor\\secret")
            argv, target = nodechat.live_command_for_check(config, "smart", "/dev/sda")
            self.assertEqual(target, "local")
            self.assertEqual(argv, ["smartctl", "-a", "/dev/sda"])

    def test_routing_mode_set_get_and_invalid(self):
        with tempfile.TemporaryDirectory() as workspace_raw:
            workspace = pathlib.Path(workspace_raw)
            config = make_config(workspace, workspace / ".sessions")
            session = nodechat.make_session(config)
            # default "auto"
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                nodechat.command_routing_mode(session, "history_mode", "history-mode", "")
            self.assertIn("history-mode: auto", buf.getvalue())
            # set "off"
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                nodechat.command_routing_mode(session, "history_mode", "history-mode", "off")
            self.assertEqual(session["history_mode"], "off")
            # invalid
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                nodechat.command_routing_mode(session, "history_mode", "history-mode", "loud")
            self.assertIn("invalid mode", buf.getvalue())
            self.assertEqual(session["history_mode"], "off")
            # web mode uses the same mode controller.
            with contextlib.redirect_stdout(io.StringIO()):
                nodechat.command_routing_mode(session, "web_mode", "web-mode", "manual")
            self.assertEqual(session["web_mode"], "manual")
            with contextlib.redirect_stdout(io.StringIO()):
                nodechat.command_routing_mode(session, "live_mode", "live-mode", "manual")
            self.assertEqual(session["live_mode"], "manual")

    def test_evidence_lists_source_and_provenance_and_handles_legacy(self):
        with tempfile.TemporaryDirectory() as workspace_raw:
            workspace = pathlib.Path(workspace_raw)
            config = make_config(workspace, workspace / ".sessions")
            session = nodechat.make_session(config)
            # Auto-routed block via add_context.
            nodechat.add_context(
                session, "auto:/history q", "HISTORY_CONTEXT body",
                source="auto-history", provenance={"query": "q", "chars": 19},
            )
            # Legacy block (no source / no provenance).
            session["context_blocks"].append(
                {"created_at": "2026-05-15T00:00:00+00:00", "query": "old", "content": "legacy body"}
            )
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                nodechat.command_evidence(session)
            text = buf.getvalue()
            self.assertIn("history_mode=auto", text)
            self.assertIn("web_mode=auto", text)
            self.assertIn("live_mode=auto", text)
            self.assertIn("[auto-history]", text)
            self.assertIn("query=q", text)
            self.assertIn("[manual-legacy]", text)

    def test_forget_drops_block_by_index_and_all(self):
        with tempfile.TemporaryDirectory() as workspace_raw:
            workspace = pathlib.Path(workspace_raw)
            config = make_config(workspace, workspace / ".sessions")
            session = nodechat.make_session(config)
            for i in range(3):
                nodechat.add_context(
                    session, f"q{i}", f"body{i}",
                    source="manual-read", provenance={"path": f"p{i}"},
                )
            self.assertEqual(len(session["context_blocks"]), 3)
            with contextlib.redirect_stdout(io.StringIO()):
                nodechat.command_forget(session, "2")
            self.assertEqual(len(session["context_blocks"]), 2)
            self.assertEqual([b["query"] for b in session["context_blocks"]], ["q0", "q2"])
            with contextlib.redirect_stdout(io.StringIO()):
                nodechat.command_forget(session, "all")
            self.assertEqual(session["context_blocks"], [])


if __name__ == "__main__":
    unittest.main()
