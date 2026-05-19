import contextlib
import importlib.util
import io
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


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

    def test_send_user_prompt_ignores_blank_prompt(self):
        with tempfile.TemporaryDirectory() as workspace_raw:
            workspace = pathlib.Path(workspace_raw)
            config = make_config(workspace, workspace / ".sessions")
            session = nodechat.make_session(config)

            with contextlib.redirect_stdout(io.StringIO()) as buf:
                status = nodechat.send_user_prompt(config, session, " \n\t ")

            self.assertIn("empty prompt ignored", buf.getvalue())
            self.assertEqual(status, "ignored")
            self.assertNotIn({"role": "user", "content": " \n\t "}, session.get("messages", []))

    def test_once_handles_slash_command_without_model_dispatch(self):
        with tempfile.TemporaryDirectory() as workspace_raw:
            workspace = pathlib.Path(workspace_raw)
            session_root = workspace / ".sessions"
            original_send = nodechat.send_user_prompt
            try:
                nodechat.send_user_prompt = mock.Mock(
                    side_effect=AssertionError("--once slash command should not chat")
                )
                with contextlib.redirect_stdout(io.StringIO()) as buf:
                    rc = nodechat.main([
                        "--session-root", str(session_root),
                        "--workspace", str(workspace),
                        "--once", "/pwd",
                    ])
            finally:
                nodechat.send_user_prompt = original_send

            self.assertEqual(rc, 0)
            self.assertIn(str(workspace.resolve()), buf.getvalue())

    def test_merge_direct_paste_prompt_combines_pending_terminal_lines(self):
        original = nodechat.read_pending_terminal_lines
        try:
            nodechat.read_pending_terminal_lines = mock.Mock(return_value=(["line two", "line three"], False))
            with contextlib.redirect_stdout(io.StringIO()) as buf:
                prompt = nodechat.merge_direct_paste_prompt("line one")
        finally:
            nodechat.read_pending_terminal_lines = original

        self.assertEqual(prompt, "line one\nline two\nline three")
        self.assertIn("combined 3 lines", buf.getvalue())

    def test_main_combines_direct_multiline_paste_into_one_prompt(self):
        with tempfile.TemporaryDirectory() as workspace_raw:
            workspace = pathlib.Path(workspace_raw)
            session_root = workspace / ".sessions"
            seen: list[str] = []
            original_input = __builtins__["input"] if isinstance(__builtins__, dict) else __builtins__.input
            original_pending = nodechat.read_pending_terminal_lines
            original_send = nodechat.send_user_prompt
            try:
                inputs = iter(["line one"])

                def fake_input(prompt=""):
                    try:
                        return next(inputs)
                    except StopIteration:
                        raise EOFError

                if isinstance(__builtins__, dict):
                    __builtins__["input"] = fake_input
                else:
                    __builtins__.input = fake_input
                nodechat.read_pending_terminal_lines = mock.Mock(return_value=(["line two"], False))

                def fake_send(config, session, prompt):
                    seen.append(prompt)
                    return "ok"

                nodechat.send_user_prompt = fake_send
                with contextlib.redirect_stdout(io.StringIO()):
                    rc = nodechat.main([
                        "--session-root", str(session_root),
                        "--workspace", str(workspace),
                        "--no-stream",
                    ])
            finally:
                if isinstance(__builtins__, dict):
                    __builtins__["input"] = original_input
                else:
                    __builtins__.input = original_input
                nodechat.read_pending_terminal_lines = original_pending
                nodechat.send_user_prompt = original_send

            self.assertEqual(rc, 0)
            self.assertEqual(seen, ["line one\nline two"])

    def test_main_discards_queued_terminal_input_after_interrupted_prompt(self):
        with tempfile.TemporaryDirectory() as workspace_raw:
            workspace = pathlib.Path(workspace_raw)
            session_root = workspace / ".sessions"
            original_input = __builtins__["input"] if isinstance(__builtins__, dict) else __builtins__.input
            original_send = nodechat.send_user_prompt
            original_discard = nodechat.discard_pending_terminal_input
            discard = mock.Mock(return_value=2)
            try:
                inputs = iter(["stop me"])

                def fake_input(prompt=""):
                    try:
                        return next(inputs)
                    except StopIteration:
                        raise EOFError

                if isinstance(__builtins__, dict):
                    __builtins__["input"] = fake_input
                else:
                    __builtins__.input = fake_input
                nodechat.send_user_prompt = mock.Mock(return_value="interrupted")
                nodechat.discard_pending_terminal_input = discard
                with contextlib.redirect_stdout(io.StringIO()):
                    rc = nodechat.main([
                        "--session-root", str(session_root),
                        "--workspace", str(workspace),
                        "--no-stream",
                    ])
            finally:
                if isinstance(__builtins__, dict):
                    __builtins__["input"] = original_input
                else:
                    __builtins__.input = original_input
                nodechat.send_user_prompt = original_send
                nodechat.discard_pending_terminal_input = original_discard

            self.assertEqual(rc, 0)
            discard.assert_called_once()

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

    def test_repo_summary_intent_routes_authoritative_overview_docs(self):
        with tempfile.TemporaryDirectory() as workspace_raw:
            workspace = pathlib.Path(workspace_raw)
            (workspace / "docs" / "wiki" / "concepts").mkdir(parents=True)
            (workspace / "docs" / "CURRENT_STATE.md").write_text("state", encoding="utf-8")
            (workspace / "docs" / "wiki" / "concepts" / "full-stack-inventory.md").write_text(
                "inventory", encoding="utf-8"
            )
            config = make_config(workspace, workspace / ".sessions")
            session = nodechat.make_session(config)

            expected = [
                "docs/CURRENT_STATE.md",
                "docs/wiki/concepts/full-stack-inventory.md",
            ]
            for prompt in (
                "dive deep on our codebase and summarize current progress, stack, completed work, and outstanding work",
                "give me a project overview of current progress and what is left",
            ):
                with self.subTest(prompt=prompt):
                    paths = nodechat.detect_repo_targets(config, session, prompt)
                    rels = [nodechat.display_path(config, session, p) for p in paths]
                    self.assertEqual(rels, expected)

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
        # Phase B (live) tightening: when specific checks fire (docker,
        # storage), the project-context "node" word no longer also adds
        # health. Health still fires on explicit health words and as the
        # no-specific-check fallback for stack/nodehome/homelab/the node.
        self.assertEqual(
            nodechat.detect_live_targets("check docker and storage status on the node"),
            ["docker", "storage"],
        )
        self.assertEqual(
            nodechat.detect_live_targets("diagnose the homelab stack"),
            ["health"],
        )
        self.assertEqual(
            nodechat.detect_live_targets(
                "dive deep on our codebase and summarize current progress, stack, completed work, and outstanding work"
            ),
            [],
        )
        self.assertEqual(
            nodechat.detect_live_targets("what did we decide about GPU2?"),
            [],
        )
        # Phase B (live) tightening: web-explicit/public-destination prompts
        # don't fire live even when they mention live objects like vllm.
        self.assertEqual(
            nodechat.detect_live_targets("look up qwen2.5 awq vllm benchmarks online"),
            [],
        )
        self.assertEqual(
            nodechat.detect_live_targets("current ollama version on github"),
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

    # ---- Operator approval lane: /live diag ops + /live restart mutations ----

    def _stub_run_live_op(self, op_argv_capture):
        """Patch run_live_op to capture argv + return a deterministic result."""
        def fake(config, key, spec):
            op_argv_capture.append({"key": key, "argv": list(spec["argv"])})
            return {
                "check": key,
                "target": "local",
                "command": " ".join(spec["argv"]),
                "exit_code": 0,
                "executable": "/usr/bin/" + spec["argv"][0],
                "output": f"{key} ok",
            }
        original = nodechat.run_live_op
        nodechat.run_live_op = fake
        return original

    def test_live_diag_ps_runs_immediately_via_docker_ps_a(self):
        with tempfile.TemporaryDirectory() as workspace_raw:
            workspace = pathlib.Path(workspace_raw)
            config = make_config(workspace, workspace / ".sessions")
            session = nodechat.make_session(config)
            calls: list[dict] = []
            original = self._stub_run_live_op(calls)
            try:
                with contextlib.redirect_stdout(io.StringIO()):
                    nodechat.command_live(config, session, "ps")
            finally:
                nodechat.run_live_op = original
            self.assertEqual(len(calls), 1)
            self.assertEqual(calls[0]["argv"], ["docker", "ps", "-a"])
            blocks = session.get("context_blocks", [])
            self.assertEqual(blocks[-1].get("source"), "manual-live")
            self.assertEqual(blocks[-1].get("provenance", {}).get("kind"), "diag")
            self.assertEqual(session.get("approvals", []), [])
            rows = nodechat.read_recent_audit(config, 10)
            self.assertTrue(any(r["event_type"] == "live_diag_executed" and r.get("op") == "ps" for r in rows))

    def test_live_diag_logs_vllm_uses_docker_logs_no_follow(self):
        spec = nodechat.LIVE_DIAG_OPS["logs vllm"]
        self.assertEqual(spec["argv"], ["docker", "logs", "--tail", "200", "vllm-server"])
        # Hard guardrail: no --follow / -f anywhere in the diag allowlist.
        for key, op in nodechat.LIVE_DIAG_OPS.items():
            for token in op["argv"]:
                self.assertNotEqual(token, "--follow", msg=f"--follow leaked into {key}")
                self.assertNotEqual(token, "-f", msg=f"-f leaked into {key}")

    def test_live_diag_logs_ollama_aliased_to_journalctl(self):
        # Both keys resolve to the same journalctl invocation.
        self.assertEqual(
            nodechat.LIVE_DIAG_OPS["logs ollama"]["argv"],
            nodechat.LIVE_DIAG_OPS["journal ollama"]["argv"],
        )
        self.assertEqual(
            nodechat.LIVE_DIAG_OPS["journal ollama"]["argv"],
            ["journalctl", "-u", "ollama", "--no-pager", "-n", "200"],
        )

    def test_live_journal_truncation_preserves_newest_tail(self):
        limit = nodechat.MAX_CMD_OUTPUT_CHARS
        output = "OLDEST_START\n" + ("x" * (limit + 100)) + "\nNEWEST_RESTART_EVENT"
        block = nodechat._live_diag_block(
            "journal ollama",
            {
                "target": "local",
                "command": "journalctl -u ollama --no-pager -n 200",
                "exit_code": 0,
                "executable": "/usr/bin/journalctl",
                "output": output,
            },
        )
        self.assertIn("truncated: true", block)
        self.assertIn(nodechat.LIVE_OUTPUT_TRUNCATED_HEAD, block)
        self.assertIn("NEWEST_RESTART_EVENT", block)
        self.assertNotIn("OLDEST_START", block)

    def test_live_non_log_truncation_preserves_head(self):
        limit = nodechat.MAX_CMD_OUTPUT_CHARS
        output = "INSPECT_BEGIN\n" + ("x" * (limit + 100)) + "\nINSPECT_END"
        block = nodechat._live_diag_block(
            "inspect vllm",
            {
                "target": "local",
                "command": "docker inspect vllm-server",
                "exit_code": 0,
                "executable": "/usr/bin/docker",
                "output": output,
            },
        )
        self.assertIn("truncated: true", block)
        self.assertIn(nodechat.LIVE_OUTPUT_TRUNCATED_TAIL, block)
        self.assertIn("INSPECT_BEGIN", block)
        self.assertNotIn("INSPECT_END", block)

    def test_live_diag_inspect_uses_docker_inspect_for_known_services(self):
        self.assertEqual(
            nodechat.LIVE_DIAG_OPS["inspect vllm"]["argv"],
            ["docker", "inspect", "vllm-server"],
        )
        self.assertEqual(
            nodechat.LIVE_DIAG_OPS["inspect open-webui"]["argv"],
            ["docker", "inspect", "open-webui"],
        )

    def test_live_diag_arbitrary_unit_or_container_refused(self):
        # Arbitrary container / unit names are NOT in the allowlist.
        for key in (
            "logs nginx",
            "logs sshd",
            "journal sshd",
            "journal docker",
            "inspect random-container",
            "inspect ollama",  # ollama is systemd, not docker; intentionally unsupported as inspect
        ):
            self.assertNotIn(key, nodechat.LIVE_DIAG_OPS, msg=f"unexpected diag key: {key}")
            self.assertNotIn(key, nodechat.LIVE_MUTATION_OPS, msg=f"unexpected mutation key: {key}")

    def test_live_restart_vllm_queues_approval_and_does_not_execute(self):
        with tempfile.TemporaryDirectory() as workspace_raw:
            workspace = pathlib.Path(workspace_raw)
            config = make_config(workspace, workspace / ".sessions")
            session = nodechat.make_session(config)
            calls: list[dict] = []
            original = self._stub_run_live_op(calls)
            try:
                buf = io.StringIO()
                with mock.patch.object(nodechat.shutil, "which", return_value="/usr/bin/docker"), contextlib.redirect_stdout(buf):
                    nodechat.command_live(config, session, "restart vllm-server")
            finally:
                nodechat.run_live_op = original
            self.assertEqual(calls, [], msg="run_live_op must not be called on /live restart")
            self.assertIn("APPROVAL_REQUIRED", buf.getvalue())
            approvals = session.get("approvals", [])
            self.assertEqual(len(approvals), 1)
            self.assertEqual(approvals[0]["class"], "live-mutation")
            self.assertEqual(approvals[0]["status"], "pending")
            self.assertEqual(approvals[0]["command"], "/live restart vllm-server")
            rows = nodechat.read_recent_audit(config, 10)
            self.assertTrue(any(
                r["event_type"] == "live_mutation_queued"
                and r.get("op") == "restart vllm-server"
                and r.get("argv") == ["docker", "restart", "vllm-server"]
                for r in rows
            ))

    def test_live_restart_open_webui_alias_queues_open_webui_argv(self):
        with tempfile.TemporaryDirectory() as workspace_raw:
            workspace = pathlib.Path(workspace_raw)
            config = make_config(workspace, workspace / ".sessions")
            session = nodechat.make_session(config)
            with mock.patch.object(nodechat.shutil, "which", return_value="/usr/bin/docker"), contextlib.redirect_stdout(io.StringIO()):
                nodechat.command_live(config, session, "restart webui")
            approvals = session.get("approvals", [])
            self.assertEqual(len(approvals), 1)
            self.assertEqual(approvals[0]["command"], "/live restart webui")
            rows = nodechat.read_recent_audit(config, 10)
            queued = [r for r in rows if r["event_type"] == "live_mutation_queued"]
            self.assertTrue(queued)
            self.assertEqual(queued[-1]["argv"], ["docker", "restart", "open-webui"])

    def test_live_restart_ollama_queues_sudo_systemctl_argv_with_ssh_target(self):
        with tempfile.TemporaryDirectory() as workspace_raw:
            workspace = pathlib.Path(workspace_raw)
            config = make_config(workspace, workspace / ".sessions")
            config.live_ssh = "bmoore_77@homelab"
            session = nodechat.make_session(config)
            calls: list[dict] = []
            original = self._stub_run_live_op(calls)
            buf = io.StringIO()
            try:
                with contextlib.redirect_stdout(buf):
                    nodechat.command_live(config, session, "restart ollama")
            finally:
                nodechat.run_live_op = original
            text = buf.getvalue()
            self.assertEqual(calls, [], msg="run_live_op must not be called on /live restart")
            self.assertIn("APPROVAL_REQUIRED", text)
            approvals = session.get("approvals", [])
            self.assertEqual(len(approvals), 1)
            self.assertEqual(approvals[0]["class"], "live-mutation")
            self.assertEqual(approvals[0]["status"], "pending")
            self.assertEqual(approvals[0]["command"], "/live restart ollama")
            rows = nodechat.read_recent_audit(config, 10)
            self.assertTrue(any(
                r["event_type"] == "live_mutation_queued"
                and r.get("op") == "restart ollama"
                and r.get("argv") == ["sudo", "-n", "/bin/systemctl", "restart", "ollama"]
                for r in rows
            ))

    def test_live_restart_ollama_refuses_windows_local_linux_argv_before_queue(self):
        with tempfile.TemporaryDirectory() as workspace_raw:
            workspace = pathlib.Path(workspace_raw)
            config = make_config(workspace, workspace / ".sessions")
            session = nodechat.make_session(config)
            buf = io.StringIO()
            with mock.patch.object(nodechat.os, "name", "nt"), contextlib.redirect_stdout(buf):
                nodechat.command_live(config, session, "restart ollama")
            text = buf.getvalue()
            self.assertIn("LIVE_MUTATION_REFUSED", text)
            self.assertIn("local Windows session cannot run POSIX-path", text)
            self.assertEqual(session.get("approvals", []), [])
            rows = nodechat.read_recent_audit(config, 10)
            refused = [r for r in rows if r["event_type"] == "live_mutation_refused"]
            self.assertTrue(refused)
            self.assertEqual(refused[-1]["op"], "restart ollama")
            self.assertEqual(refused[-1]["target"], "local")
            self.assertEqual(refused[-1]["status"], "refused")

    def test_live_restart_arbitrary_container_falls_through_to_unknown(self):
        with tempfile.TemporaryDirectory() as workspace_raw:
            workspace = pathlib.Path(workspace_raw)
            config = make_config(workspace, workspace / ".sessions")
            session = nodechat.make_session(config)
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                nodechat.command_live(config, session, "restart nginx")
            self.assertIn("unknown live check", buf.getvalue())
            self.assertEqual(session.get("approvals", []), [])

    def test_approve_executes_queued_live_mutation(self):
        with tempfile.TemporaryDirectory() as workspace_raw:
            workspace = pathlib.Path(workspace_raw)
            config = make_config(workspace, workspace / ".sessions")
            session = nodechat.make_session(config)
            with mock.patch.object(nodechat.shutil, "which", return_value="/usr/bin/docker"), contextlib.redirect_stdout(io.StringIO()):
                nodechat.command_live(config, session, "restart vllm-server")
            calls: list[dict] = []
            original = self._stub_run_live_op(calls)
            try:
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    nodechat.command_approve(config, session, "a1")
            finally:
                nodechat.run_live_op = original
            self.assertEqual(len(calls), 1)
            self.assertEqual(calls[0]["argv"], ["docker", "restart", "vllm-server"])
            self.assertIn("COMMAND_OUTPUT", buf.getvalue())
            self.assertEqual(session["approvals"][0]["status"], "executed")
            rows = nodechat.read_recent_audit(config, 20)
            event_types = [r["event_type"] for r in rows]
            self.assertIn("live_mutation_queued", event_types)
            self.assertIn("live_mutation_executed", event_types)
            executed = next(r for r in rows if r["event_type"] == "live_mutation_executed")
            self.assertEqual(executed["op"], "restart vllm-server")
            self.assertEqual(executed["argv"], ["docker", "restart", "vllm-server"])
            self.assertEqual(executed["exit_code"], 0)
            self.assertEqual(executed["status"], "executed")
            # Re-approve should be a no-op (status already executed)
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                nodechat.command_approve(config, session, "a1")
            self.assertIn("already executed", buf.getvalue())

    def test_existing_git_approval_flow_still_works_after_live_mutation_branch(self):
        # Regression: make sure the new class-based branch in command_approve
        # didn't break the original git fetch/pull/push approval path.
        with tempfile.TemporaryDirectory() as workspace_raw:
            workspace = pathlib.Path(workspace_raw)
            config = make_config(workspace, workspace / ".sessions")
            session = nodechat.make_session(config)
            with contextlib.redirect_stdout(io.StringIO()):
                nodechat.command_cmd(config, session, "git fetch")
            self.assertEqual(session["approvals"][0]["class"], "network")
            original = nodechat.run_approved_command
            try:
                nodechat.run_approved_command = lambda config, session, parts, approval_reason: (
                    0, "fetch ok", "/usr/bin/git", True,
                )
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    nodechat.command_approve(config, session, "a1")
            finally:
                nodechat.run_approved_command = original
            self.assertIn("approval_id: a1", buf.getvalue())
            self.assertEqual(session["approvals"][0]["status"], "executed")

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

    def test_evidence_groups_by_source_and_preserves_forget_indexes(self):
        with tempfile.TemporaryDirectory() as workspace_raw:
            workspace = pathlib.Path(workspace_raw)
            config = make_config(workspace, workspace / ".sessions")
            session = nodechat.make_session(config)
            nodechat.add_context(
                session, "auto:/history q0", "history zero",
                source="auto-history", provenance={"query": "q0", "chars": 10},
            )
            nodechat.add_context(
                session, "/read docs/CURRENT_STATE.md", "read body",
                source="manual-read", provenance={"path": "docs/CURRENT_STATE.md"},
            )
            nodechat.add_context(
                session, "auto:/history q2", "history two",
                source="auto-history", provenance={"query": "q2", "chars": 20},
            )

            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                nodechat.command_evidence(session)
            text = buf.getvalue()

            self.assertIn("3 context block(s), 2 source group(s), total_chars=39", text)
            self.assertIn("Use /forget <index>", text)
            self.assertIn("[auto-history] blocks=2 chars=30", text)
            self.assertIn("refs: query=q0 | query=q2", text)
            self.assertIn("  1.", text)
            self.assertIn("  3.", text)
            self.assertIn("[manual-read] blocks=1 chars=9", text)
            self.assertIn("path=docs/CURRENT_STATE.md", text)

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

    def test_builtin_model_profiles_match_expected_lanes(self):
        with tempfile.TemporaryDirectory() as workspace_raw:
            workspace = pathlib.Path(workspace_raw)
            config = make_config(workspace, workspace / ".sessions")
            profiles = nodechat.load_model_profiles(config)

            self.assertEqual(profiles["fast"]["model"], "mistral-small3.1:24b")
            self.assertEqual(profiles["strong"]["model"], nodechat.DEFAULT_MODEL)
            self.assertEqual(profiles["strong"]["base_url"], config.base_url)
            self.assertEqual(profiles["deep"]["model"], "llama3.3:70b-instruct-q4_K_M")

    def test_user_model_profiles_extend_builtins(self):
        with tempfile.TemporaryDirectory() as workspace_raw:
            workspace = pathlib.Path(workspace_raw)
            session_root = workspace / ".sessions"
            session_root.mkdir()
            (session_root / "profiles.json").write_text(
                '{"profiles":{"lab":{"model":"local-test","base_url":"http://127.0.0.1:9999/v1","provider":"test"}}}',
                encoding="utf-8",
            )
            config = make_config(workspace, session_root)
            profiles = nodechat.load_model_profiles(config)

            self.assertIn("fast", profiles)
            self.assertEqual(profiles["lab"]["model"], "local-test")
            self.assertEqual(profiles["lab"]["source"], "user")

    def test_user_model_profiles_reject_public_remote_endpoints(self):
        with tempfile.TemporaryDirectory() as workspace_raw:
            workspace = pathlib.Path(workspace_raw)
            session_root = workspace / ".sessions"
            session_root.mkdir()
            (session_root / "profiles.json").write_text(
                '{"profiles":{"remote":{"model":"remote-test","base_url":"https://api.example.com/v1"}}}',
                encoding="utf-8",
            )
            config = make_config(workspace, session_root)
            profiles = nodechat.load_model_profiles(config)

            self.assertNotIn("remote", profiles)

    def test_profile_command_lists_and_switches_model_endpoint_together(self):
        with tempfile.TemporaryDirectory() as workspace_raw:
            workspace = pathlib.Path(workspace_raw)
            config = make_config(workspace, workspace / ".sessions")
            session = nodechat.make_session(config)

            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                nodechat.command_profile(config, session, "")
            self.assertIn("fast", buf.getvalue())
            self.assertIn("strong", buf.getvalue())

            with contextlib.redirect_stdout(io.StringIO()):
                nodechat.command_profile(config, session, "fast")
            self.assertEqual(session["profile"], "fast")
            self.assertEqual(session["model"], "mistral-small3.1:24b")
            self.assertEqual(session["base_url"], "http://localhost:11434/v1")

    def test_model_command_resolves_profile_before_literal(self):
        with tempfile.TemporaryDirectory() as workspace_raw:
            workspace = pathlib.Path(workspace_raw)
            config = make_config(workspace, workspace / ".sessions")
            session = nodechat.make_session(config)

            with contextlib.redirect_stdout(io.StringIO()):
                nodechat.command_model(config, session, "deep")
            self.assertEqual(session["profile"], "deep")
            self.assertEqual(session["model"], "llama3.3:70b-instruct-q4_K_M")

            with contextlib.redirect_stdout(io.StringIO()):
                nodechat.command_model(config, session, "custom-model-id")
            self.assertEqual(session["profile"], "")
            self.assertEqual(session["model"], "custom-model-id")

    def test_runtime_context_reports_current_profile(self):
        with tempfile.TemporaryDirectory() as workspace_raw:
            workspace = pathlib.Path(workspace_raw)
            config = make_config(workspace, workspace / ".sessions")
            session = nodechat.make_session(config)
            with contextlib.redirect_stdout(io.StringIO()):
                nodechat.command_profile(config, session, "fast")

            context = nodechat.runtime_context(config, session)
            self.assertIn("profile: fast", context)
            self.assertIn("model: mistral-small3.1:24b", context)
            self.assertIn("endpoint: http://localhost:11434/v1", context)

    def test_api_messages_include_evidence_state_with_source_labels(self):
        with tempfile.TemporaryDirectory() as workspace_raw:
            workspace = pathlib.Path(workspace_raw)
            config = make_config(workspace, workspace / ".sessions")
            session = nodechat.make_session(config)
            nodechat.add_context(
                session,
                "/read docs/CURRENT_STATE.md",
                nodechat.context_block("file_read", "docs/CURRENT_STATE.md", "fake current state"),
                source="manual-read",
                provenance={"path": "docs/CURRENT_STATE.md", "chars": 18},
            )
            session.setdefault("messages", []).append({"role": "user", "content": "summarize"})

            messages = nodechat.build_api_messages(config, session)
            self.assertEqual(messages[0]["role"], "system")
            self.assertIn("NODECHAT_RUNTIME", messages[1]["content"])
            self.assertIn("NODECHAT_EVIDENCE_STATE", messages[2]["content"])
            self.assertIn("repo: count=1", messages[2]["content"])
            self.assertIn("docs/CURRENT_STATE.md", messages[2]["content"])
            self.assertIn("NODECHAT_TOOL_CONTEXT", messages[3]["content"])

    def test_api_messages_report_no_loaded_evidence(self):
        with tempfile.TemporaryDirectory() as workspace_raw:
            workspace = pathlib.Path(workspace_raw)
            config = make_config(workspace, workspace / ".sessions")
            session = nodechat.make_session(config)
            session.setdefault("messages", []).append({"role": "user", "content": "what is this repo"})

            messages = nodechat.build_api_messages(config, session)
            self.assertIn("NODECHAT_EVIDENCE_STATE", messages[2]["content"])
            self.assertIn("loaded_context: none", messages[2]["content"])

    def test_send_user_prompt_audits_model_dispatch(self):
        # In Phase 2 the default model_mode is "auto", which would pick the
        # fast profile for a short "hello" prompt. This test was written before
        # auto-routing existed and was validating that the configured profile
        # gets dispatched + audited correctly. Pin model_mode="manual" to
        # preserve that intent.
        with tempfile.TemporaryDirectory() as workspace_raw:
            workspace = pathlib.Path(workspace_raw)
            config = make_config(workspace, workspace / ".sessions")
            session = nodechat.make_session(config)
            session["model_mode"] = "manual"
            original = nodechat.complete_chat
            try:
                nodechat.complete_chat = lambda config, session: "ok"
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    nodechat.send_user_prompt(config, session, "hello")
            finally:
                nodechat.complete_chat = original

            self.assertIn("[model: strong]", buf.getvalue())
            rows = nodechat.read_recent_audit(config, 10)
            event = next(row for row in rows if row["event_type"] == "model_dispatched")
            self.assertEqual(event["status"], "ok")
            self.assertEqual(event["profile"], "strong")
            self.assertEqual(event["model"], nodechat.DEFAULT_MODEL)
            self.assertEqual(event["endpoint"], "http://127.0.0.1:8000/v1")
            self.assertGreater(event["prompt_chars"], 0)
            self.assertEqual(event["response_chars"], 2)

    def test_send_user_prompt_handles_keyboard_interrupt_without_traceback(self):
        with tempfile.TemporaryDirectory() as workspace_raw:
            workspace = pathlib.Path(workspace_raw)
            config = make_config(workspace, workspace / ".sessions")
            config.stream = True
            session = nodechat.make_session(config)
            session["model_mode"] = "manual"
            original = nodechat.stream_chat
            try:
                nodechat.stream_chat = mock.Mock(side_effect=KeyboardInterrupt)
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    nodechat.send_user_prompt(config, session, "stop me")
            finally:
                nodechat.stream_chat = original

            self.assertIn("CHAT_INTERRUPTED", buf.getvalue())
            self.assertNotIn({"role": "assistant", "content": ""}, session.get("messages", []))
            rows = nodechat.read_recent_audit(config, 10)
            event = next(row for row in rows if row["event_type"] == "model_dispatched")
            self.assertEqual(event["status"], "interrupted")
            self.assertEqual(event["reason"], "keyboard interrupt")

    # ---- Model auto-routing (Phase 2) -----------------------------------

    def _stub_chat_and_vllm(self, *, vllm_ok: bool):
        """Patch complete_chat + vllm_available_cached for deterministic tests.

        Records every (model, base_url) the chat lambda saw via the captured
        list, and stubs vLLM probe so tests don't hit the network.
        """
        seen: list[dict[str, object]] = []

        def fake_complete(config, session):
            seen.append({
                "model": str(session.get("model") or config.model),
                "base_url": str(session.get("base_url") or config.base_url),
                "profile": str(session.get("profile") or ""),
                "temperature": float(config.temperature),
                "max_tokens": int(config.max_tokens),
            })
            return "ok"

        def fake_probe(config, session, base_url):
            return (vllm_ok, 12 if vllm_ok else 3012)

        original_chat = nodechat.complete_chat
        original_probe = nodechat.vllm_available_cached
        nodechat.complete_chat = fake_complete
        nodechat.vllm_available_cached = fake_probe
        return seen, (original_chat, original_probe)

    def _restore_chat_and_vllm(self, originals):
        nodechat.complete_chat, nodechat.vllm_available_cached = originals

    def test_model_mode_auto_short_chat_stays_fast(self):
        with tempfile.TemporaryDirectory() as workspace_raw:
            workspace = pathlib.Path(workspace_raw)
            config = make_config(workspace, workspace / ".sessions")
            session = nodechat.make_session(config)
            self.assertEqual(session.get("model_mode"), "auto")
            seen, originals = self._stub_chat_and_vllm(vllm_ok=True)
            try:
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    nodechat.send_user_prompt(config, session, "hi there")
            finally:
                self._restore_chat_and_vllm(originals)
            self.assertIn("[model: fast]", buf.getvalue())
            self.assertEqual(seen[0]["profile"], "fast")
            self.assertEqual(seen[0]["model"], "mistral-small3.1:24b")
            self.assertEqual(seen[0]["temperature"], 0.1)
            self.assertEqual(seen[0]["max_tokens"], 0)
            # No auto_route_model audit row should fire on default-fast turns.
            rows = nodechat.read_recent_audit(config, 10)
            self.assertFalse(
                any(r["event_type"] == "auto_route_model" for r in rows),
                msg="default-fast turn should not emit auto_route_model",
            )

    def test_model_mode_auto_long_prompt_routes_strong(self):
        with tempfile.TemporaryDirectory() as workspace_raw:
            workspace = pathlib.Path(workspace_raw)
            config = make_config(workspace, workspace / ".sessions")
            session = nodechat.make_session(config)
            seen, originals = self._stub_chat_and_vllm(vllm_ok=True)
            try:
                long_prompt = "Please consider this carefully. " * 40  # > 800 chars
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    nodechat.send_user_prompt(config, session, long_prompt)
            finally:
                self._restore_chat_and_vllm(originals)
            text = buf.getvalue()
            self.assertIn("model: strong", text)
            self.assertIn("auto-routed", text)
            self.assertIn("long prompt", text)
            self.assertEqual(seen[0]["profile"], "strong")
            self.assertEqual(seen[0]["temperature"], 0.1)
            self.assertEqual(seen[0]["max_tokens"], 3072)
            rows = nodechat.read_recent_audit(config, 10)
            row = next(r for r in rows if r["event_type"] == "auto_route_model")
            self.assertEqual(row["status"], "ok")
            self.assertEqual(row["to_profile"], "strong")
            self.assertIn("long prompt", row["rationale"])
            self.assertTrue(row["vllm_available"])

    def test_model_mode_auto_code_keywords_route_strong(self):
        with tempfile.TemporaryDirectory() as workspace_raw:
            workspace = pathlib.Path(workspace_raw)
            config = make_config(workspace, workspace / ".sessions")
            session = nodechat.make_session(config)
            seen, originals = self._stub_chat_and_vllm(vllm_ok=True)
            try:
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    nodechat.send_user_prompt(
                        config, session,
                        "what does this function return?\n```python\ndef foo(): return 1\n```",
                    )
            finally:
                self._restore_chat_and_vllm(originals)
            self.assertIn("model: strong", buf.getvalue())
            self.assertIn("code markers", buf.getvalue())
            self.assertEqual(seen[0]["profile"], "strong")
            self.assertEqual(seen[0]["temperature"], 0.0)
            self.assertEqual(seen[0]["max_tokens"], 4096)
            rows = nodechat.read_recent_audit(config, 10)
            event = next(row for row in rows if row["event_type"] == "model_dispatched")
            self.assertEqual(event["generation_policy"], "code_patch")
            self.assertEqual(event["temperature"], 0.0)
            self.assertEqual(event["max_tokens"], 4096)
            self.assertIn("auto-route trigger: code markers", event["generation_reasons"])

    def test_loaded_repo_evidence_uses_grounded_generation_policy(self):
        with tempfile.TemporaryDirectory() as workspace_raw:
            workspace = pathlib.Path(workspace_raw)
            config = make_config(workspace, workspace / ".sessions")
            config.temperature = 0.2
            session = nodechat.make_session(config)
            nodechat.add_context(
                session,
                "/read docs/CURRENT_STATE.md",
                nodechat.context_block("file_read", "docs/CURRENT_STATE.md", "fake current state"),
                source="manual-read",
                provenance={"path": "docs/CURRENT_STATE.md", "chars": 18},
            )
            seen, originals = self._stub_chat_and_vllm(vllm_ok=True)
            try:
                with contextlib.redirect_stdout(io.StringIO()):
                    nodechat.send_user_prompt(config, session, "summarize this")
            finally:
                self._restore_chat_and_vllm(originals)

            self.assertEqual(seen[0]["temperature"], 0.1)
            self.assertEqual(seen[0]["max_tokens"], 3072)
            rows = nodechat.read_recent_audit(config, 10)
            event = next(row for row in rows if row["event_type"] == "model_dispatched")
            self.assertEqual(event["generation_policy"], "grounded_analysis")
            self.assertIn("repo evidence loaded", event["generation_reasons"])
            self.assertEqual(event["evidence_state"]["block_count"], 1)
            self.assertEqual(event["evidence_state"]["sources"][0]["category"], "repo")

    def test_model_mode_auto_does_not_select_deep(self):
        with tempfile.TemporaryDirectory() as workspace_raw:
            workspace = pathlib.Path(workspace_raw)
            config = make_config(workspace, workspace / ".sessions")
            session = nodechat.make_session(config)
            seen, originals = self._stub_chat_and_vllm(vllm_ok=True)
            try:
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    # Prompt mentioning "deep dive" + "deep analysis" should
                    # route to strong (analysis verbs), not deep.
                    nodechat.send_user_prompt(
                        config, session,
                        "give me a deep dive analysis of the rdimm dispute we had",
                    )
            finally:
                self._restore_chat_and_vllm(originals)
            self.assertNotIn("model: deep", buf.getvalue())
            self.assertEqual(seen[0]["profile"], "strong")

    def test_model_mode_manual_does_not_silently_switch(self):
        # Critical guardrail: in manual mode, even a long code-heavy prompt
        # must dispatch on the configured profile. No silent auto-switch.
        with tempfile.TemporaryDirectory() as workspace_raw:
            workspace = pathlib.Path(workspace_raw)
            config = make_config(workspace, workspace / ".sessions")
            session = nodechat.make_session(config)
            session["model_mode"] = "manual"
            # Configure profile to fast explicitly to make divergence visible.
            profiles = nodechat.load_model_profiles(config)
            nodechat.apply_model_profile(session, profiles["fast"])
            seen, originals = self._stub_chat_and_vllm(vllm_ok=True)
            try:
                long_prompt = "Please consider this carefully. " * 40 + " ```def foo(): pass```"
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    nodechat.send_user_prompt(config, session, long_prompt)
            finally:
                self._restore_chat_and_vllm(originals)
            self.assertIn("[model: fast]", buf.getvalue())
            self.assertNotIn("auto-routed", buf.getvalue())
            self.assertEqual(seen[0]["profile"], "fast")
            self.assertEqual(seen[0]["model"], "mistral-small3.1:24b")
            rows = nodechat.read_recent_audit(config, 10)
            self.assertFalse(any(r["event_type"] == "auto_route_model" for r in rows))

    def test_model_mode_pinned_strong_overrides_auto_rules(self):
        with tempfile.TemporaryDirectory() as workspace_raw:
            workspace = pathlib.Path(workspace_raw)
            config = make_config(workspace, workspace / ".sessions")
            session = nodechat.make_session(config)
            session["model_mode"] = "strong"
            seen, originals = self._stub_chat_and_vllm(vllm_ok=False)
            try:
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    nodechat.send_user_prompt(config, session, "hi")  # short, no triggers
            finally:
                self._restore_chat_and_vllm(originals)
            # Pinned strong: dispatches strong even on a short greeting AND
            # even when vLLM probe would have failed (pinning skips probe).
            self.assertIn("[model: strong]", buf.getvalue())
            self.assertEqual(seen[0]["profile"], "strong")

    def test_model_mode_pinned_fast_overrides_auto_rules(self):
        with tempfile.TemporaryDirectory() as workspace_raw:
            workspace = pathlib.Path(workspace_raw)
            config = make_config(workspace, workspace / ".sessions")
            session = nodechat.make_session(config)
            session["model_mode"] = "fast"
            seen, originals = self._stub_chat_and_vllm(vllm_ok=True)
            try:
                long_prompt = "Please consider this carefully. " * 40
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    nodechat.send_user_prompt(config, session, long_prompt)
            finally:
                self._restore_chat_and_vllm(originals)
            self.assertIn("[model: fast]", buf.getvalue())
            self.assertNotIn("auto-routed", buf.getvalue())
            self.assertEqual(seen[0]["profile"], "fast")

    def test_model_mode_auto_falls_back_to_fast_when_vllm_unreachable(self):
        with tempfile.TemporaryDirectory() as workspace_raw:
            workspace = pathlib.Path(workspace_raw)
            config = make_config(workspace, workspace / ".sessions")
            session = nodechat.make_session(config)
            seen, originals = self._stub_chat_and_vllm(vllm_ok=False)
            try:
                long_prompt = "Please consider this carefully. " * 40
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    nodechat.send_user_prompt(config, session, long_prompt)
            finally:
                self._restore_chat_and_vllm(originals)
            text = buf.getvalue()
            self.assertIn("model: fast", text)
            self.assertIn("strong unavailable", text)
            self.assertIn("vLLM probe failed", text)
            self.assertEqual(seen[0]["profile"], "fast")
            rows = nodechat.read_recent_audit(config, 10)
            row = next(r for r in rows if r["event_type"] == "auto_route_model")
            self.assertEqual(row["status"], "fallback")
            self.assertEqual(row["to_profile"], "fast")
            self.assertFalse(row["vllm_available"])
            self.assertGreater(row["vllm_probe_ms"], 0)

    def test_per_turn_dispatch_does_not_mutate_session_profile(self):
        # Critical: after an auto-routed turn, session.profile / .model /
        # .base_url must reflect the user's configured choice, not the
        # per-turn dispatch.
        with tempfile.TemporaryDirectory() as workspace_raw:
            workspace = pathlib.Path(workspace_raw)
            config = make_config(workspace, workspace / ".sessions")
            session = nodechat.make_session(config)
            profiles = nodechat.load_model_profiles(config)
            nodechat.apply_model_profile(session, profiles["fast"])
            configured_profile = session.get("profile")
            configured_model = session.get("model")
            configured_base_url = session.get("base_url")

            seen, originals = self._stub_chat_and_vllm(vllm_ok=True)
            try:
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    long_prompt = "Please review this carefully. " * 40
                    nodechat.send_user_prompt(config, session, long_prompt)
            finally:
                self._restore_chat_and_vllm(originals)

            # During the turn, dispatch was strong.
            self.assertEqual(seen[0]["profile"], "strong")
            # After the turn, configured state is unchanged.
            self.assertEqual(session.get("profile"), configured_profile)
            self.assertEqual(session.get("model"), configured_model)
            self.assertEqual(session.get("base_url"), configured_base_url)

    def test_command_model_mode_get_set_and_invalid(self):
        with tempfile.TemporaryDirectory() as workspace_raw:
            workspace = pathlib.Path(workspace_raw)
            config = make_config(workspace, workspace / ".sessions")
            session = nodechat.make_session(config)
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                nodechat.command_model_mode(config, session, "")
            self.assertIn("model-mode: auto", buf.getvalue())

            for mode in ("manual", "fast", "strong", "deep", "auto"):
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    nodechat.command_model_mode(config, session, mode)
                self.assertEqual(session["model_mode"], mode)

            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                nodechat.command_model_mode(config, session, "off")  # not a model mode
            self.assertIn("invalid mode", buf.getvalue())
            self.assertEqual(session["model_mode"], "auto")  # last valid set

    # ---- Remote model profiles (Phase 3) -------------------------------

    def _remote_env(self):
        return {
            "NODECHAT_OPENAI_API_KEY": "sk-test",
            "NODECHAT_OPENAI_MODEL": "gpt-test",
            "NODECHAT_OPENAI_INPUT_PER_MTOK": "2.0",
            "NODECHAT_OPENAI_OUTPUT_PER_MTOK": "8.0",
            "NODECHAT_ANTHROPIC_API_KEY": "sk-ant-test",
            "NODECHAT_ANTHROPIC_MODEL": "claude-test",
            "NODECHAT_ANTHROPIC_INPUT_PER_MTOK": "3.0",
            "NODECHAT_ANTHROPIC_OUTPUT_PER_MTOK": "15.0",
        }

    def test_remote_profiles_are_env_gated(self):
        with tempfile.TemporaryDirectory() as workspace_raw:
            workspace = pathlib.Path(workspace_raw)
            config = make_config(workspace, workspace / ".sessions")
            with mock.patch.dict(os.environ, {
                "NODECHAT_OPENAI_API_KEY": "",
                "NODECHAT_OPENAI_MODEL": "",
                "NODECHAT_ANTHROPIC_API_KEY": "",
                "NODECHAT_ANTHROPIC_MODEL": "",
            }, clear=False):
                profiles = nodechat.load_model_profiles(config)
                self.assertNotIn("openai", profiles)
                self.assertNotIn("anthropic", profiles)

            with mock.patch.dict(os.environ, self._remote_env(), clear=False):
                profiles = nodechat.load_model_profiles(config)
                self.assertEqual(profiles["openai"]["model"], "gpt-test")
                self.assertTrue(profiles["openai"]["remote"])
                self.assertEqual(profiles["openai"]["provider_kind"], "openai")
                self.assertEqual(profiles["anthropic"]["model"], "claude-test")
                self.assertTrue(profiles["anthropic"]["remote"])
                self.assertEqual(profiles["anthropic"]["provider_kind"], "anthropic")

    def test_remote_profile_selection_requires_session_enable(self):
        with tempfile.TemporaryDirectory() as workspace_raw:
            workspace = pathlib.Path(workspace_raw)
            config = make_config(workspace, workspace / ".sessions")
            session = nodechat.make_session(config)
            with mock.patch.dict(os.environ, self._remote_env(), clear=False):
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    nodechat.command_profile(config, session, "openai")
                self.assertIn("requires /remote-models enable", buf.getvalue())
                self.assertNotEqual(session.get("profile"), "openai")

                with contextlib.redirect_stdout(io.StringIO()):
                    nodechat.command_remote_models(config, session, "enable")
                    nodechat.command_profile(config, session, "openai")
                self.assertEqual(session.get("profile"), "openai")
                self.assertEqual(session.get("model"), "gpt-test")
                self.assertEqual(session.get("base_url"), "https://api.openai.com/v1")

    def test_remote_model_mode_requires_enable_and_then_pins_remote(self):
        with tempfile.TemporaryDirectory() as workspace_raw:
            workspace = pathlib.Path(workspace_raw)
            config = make_config(workspace, workspace / ".sessions")
            session = nodechat.make_session(config)
            with mock.patch.dict(os.environ, self._remote_env(), clear=False):
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    nodechat.command_model_mode(config, session, "anthropic")
                self.assertIn("requires /remote-models enable", buf.getvalue())
                self.assertEqual(session.get("model_mode"), "auto")

                with contextlib.redirect_stdout(io.StringIO()):
                    nodechat.command_remote_models(config, session, "enable")
                    nodechat.command_model_mode(config, session, "anthropic")
                self.assertEqual(session.get("model_mode"), "anthropic")

                dispatch = nodechat.pick_turn_dispatch(config, session, "short prompt")
                self.assertEqual(dispatch["profile"], "anthropic")
                self.assertTrue(dispatch["remote"])
                self.assertEqual(dispatch["provider_kind"], "anthropic")

    def test_remote_disabled_dispatch_falls_back_to_fast(self):
        with tempfile.TemporaryDirectory() as workspace_raw:
            workspace = pathlib.Path(workspace_raw)
            config = make_config(workspace, workspace / ".sessions")
            session = nodechat.make_session(config)
            with mock.patch.dict(os.environ, self._remote_env(), clear=False):
                session["model_mode"] = "openai"
                dispatch = nodechat.pick_turn_dispatch(config, session, "short prompt")
                self.assertEqual(dispatch["profile"], "fast")
                self.assertTrue(dispatch["fallback"])
                self.assertTrue(dispatch["remote_blocked"])
                self.assertIn("remote profile 'openai' disabled", dispatch["rationale"])

    def test_remote_openai_dispatch_audits_cost_estimate(self):
        with tempfile.TemporaryDirectory() as workspace_raw:
            workspace = pathlib.Path(workspace_raw)
            config = make_config(workspace, workspace / ".sessions")
            session = nodechat.make_session(config)
            with mock.patch.dict(os.environ, self._remote_env(), clear=False):
                with contextlib.redirect_stdout(io.StringIO()):
                    nodechat.command_remote_models(config, session, "enable")
                    nodechat.command_model_mode(config, session, "openai")
                seen = []

                def fake_complete(config, session):
                    seen.append({
                        "profile": session.get("profile"),
                        "headers": nodechat.model_auth_headers(config, session),
                    })
                    return "remote ok"

                original = nodechat.complete_chat
                try:
                    nodechat.complete_chat = fake_complete
                    with contextlib.redirect_stdout(io.StringIO()):
                        nodechat.send_user_prompt(config, session, "hello remote")
                finally:
                    nodechat.complete_chat = original

                self.assertEqual(seen[0]["profile"], "openai")
                self.assertEqual(seen[0]["headers"], {"Authorization": "Bearer sk-test"})
                rows = nodechat.read_recent_audit(config, 10)
                event = next(row for row in rows if row["event_type"] == "model_dispatched")
                self.assertTrue(event["remote"])
                self.assertEqual(event["provider_kind"], "openai")
                self.assertGreater(event["estimated_input_tokens"], 0)
                self.assertGreater(event["estimated_output_tokens"], 0)
                self.assertGreaterEqual(event["estimated_cost_usd"], 0)
                self.assertEqual(session["costs"]["remote_turns"], 1)

    def test_anthropic_payload_and_complete_shim(self):
        with tempfile.TemporaryDirectory() as workspace_raw:
            workspace = pathlib.Path(workspace_raw)
            config = make_config(workspace, workspace / ".sessions")
            session = nodechat.make_session(config)
            with mock.patch.dict(os.environ, self._remote_env(), clear=False):
                with contextlib.redirect_stdout(io.StringIO()):
                    nodechat.command_remote_models(config, session, "enable")
                    nodechat.command_profile(config, session, "anthropic")
                captured = {}

                def fake_post(url, payload, timeout, headers):
                    captured["url"] = url
                    captured["payload"] = payload
                    captured["headers"] = headers
                    return {"content": [{"type": "text", "text": "anthropic ok"}]}

                original = nodechat.post_json
                try:
                    nodechat.post_json = fake_post
                    buf = io.StringIO()
                    with contextlib.redirect_stdout(buf):
                        result = nodechat.complete_chat(config, session)
                finally:
                    nodechat.post_json = original

                self.assertEqual(result, "anthropic ok")
                self.assertIn("/messages", captured["url"])
                self.assertEqual(captured["payload"]["model"], "claude-test")
                self.assertIn("system", captured["payload"])
                self.assertEqual(captured["headers"]["x-api-key"], "sk-ant-test")

    def test_remote_models_disable_clears_remote_model_mode(self):
        with tempfile.TemporaryDirectory() as workspace_raw:
            workspace = pathlib.Path(workspace_raw)
            config = make_config(workspace, workspace / ".sessions")
            session = nodechat.make_session(config)
            with mock.patch.dict(os.environ, self._remote_env(), clear=False):
                with contextlib.redirect_stdout(io.StringIO()):
                    nodechat.command_remote_models(config, session, "enable")
                    nodechat.command_profile(config, session, "openai")
                    nodechat.command_model_mode(config, session, "openai")
                    nodechat.command_remote_models(config, session, "disable")
                self.assertFalse(session["remote_models_enabled"])
                self.assertEqual(session["model_mode"], nodechat.DEFAULT_MODEL_MODE)
                self.assertEqual(session["profile"], "strong")
                self.assertEqual(session["model"], nodechat.DEFAULT_MODEL)
                self.assertNotIn("api.openai.com", session["base_url"])


# ---------------------------------------------------------------------------
# Routing corpus regression suite (Phase A of the auto-routing recall pass).
#
# Phase A ships measurement infrastructure with no behavior change. Floors are
# pinned to the measured Phase A baseline so the suite is a regression ratchet
# (no router can drop below baseline). Phase B will widen heuristics router by
# router and ratchet floors upward.
#
# Phase B targets (precision 0.95, recall 0.95 across all routers; zero
# guardrail failures) are documented but not enforced in Phase A.
# ---------------------------------------------------------------------------

ROUTING_CORPUS_PATH = ROOT / "tests" / "routing_corpus.py"
_RC_SPEC = importlib.util.spec_from_file_location("routing_corpus", ROUTING_CORPUS_PATH)
routing_corpus = importlib.util.module_from_spec(_RC_SPEC)
assert _RC_SPEC and _RC_SPEC.loader
sys.modules["routing_corpus"] = routing_corpus
_RC_SPEC.loader.exec_module(routing_corpus)


class RoutingCorpusTests(unittest.TestCase):
    """Phase A regression ratchet over the labeled routing corpus."""

    # Precision/recall floors pinned at Phase A baseline (measured 2026-05-15
    # against the corpus in tests/routing_corpus.py). Rounded down to 0.01 so
    # tiny float noise doesn't cause flaky failures. Phase B will raise these.
    # Phase B complete. All four routers measured at 1.00 / 1.00 on the
    # 100-prompt corpus. Floors pinned at the post-Phase-B baseline; any
    # regression below 1.00 fails the suite.
    PRECISION_FLOORS = {
        "history": 1.00,  # Phase B (history) landed: 0.81 -> 1.00
        "repo":    1.00,
        "web":     1.00,  # Phase B (web)     landed: 0.82 -> 1.00
        "live":    1.00,  # Phase B (live)    landed: 0.78 -> 1.00
    }
    RECALL_FLOORS = {
        "history": 1.00,  # Phase B (history) landed: 0.81 -> 1.00
        "repo":    1.00,
        "web":     1.00,  # Phase B (web)     landed: 0.93 -> 1.00
        "live":    1.00,  # Phase B (live)    landed: 0.68 -> 1.00
    }
    PHASE_B_PRECISION_TARGET = 0.95
    PHASE_B_RECALL_TARGET = 0.95

    # Guardrail failures from Phase A are all resolved. Any new guardrail
    # failure is a regression. The inverse-ratchet test will surface a fixed
    # guardrail by failing -- which is fine: this set should stay empty until
    # corpus growth surfaces a new known-bad case.
    PHASE_B_GUARDRAIL_TARGETS: set[tuple[str, str]] = set()
    # Phase B (history) landed -- removed:
    #   g009 history "history of the mongol empire"
    #   g010 history "remind me to call mom tomorrow"
    #   g011 history "previously the romans built aqueducts"
    # Phase B (web) landed -- removed:
    #   g008 web "the latest model we trained"
    # Phase B (live) landed -- removed:
    #   g006 live "current vLLM status on our node" (extra 'health' added)
    #   g007 live "what's running on the box right now" ('box' missing)

    @classmethod
    def setUpClass(cls):
        cls.config, cls.session = routing_corpus.make_corpus_config_and_session()
        cls.matrix = routing_corpus.evaluate(cls.config, cls.session)

    def test_precision_floor_per_router(self):
        for router, floor in self.PRECISION_FLOORS.items():
            with self.subTest(router=router):
                p = self.matrix["metrics"][router]["precision"]
                fps = self.matrix["fps"][router]
                msg = (
                    f"{router} precision {p:.3f} below Phase A floor {floor:.2f}. "
                    f"FPs ({len(fps)}):\n"
                    + "\n".join(f"  {cid} {prompt!r} got={act!r} exp={exp!r}"
                                for cid, prompt, act, exp in fps)
                )
                self.assertGreaterEqual(p, floor, msg=msg)

    def test_recall_floor_per_router(self):
        for router, floor in self.RECALL_FLOORS.items():
            with self.subTest(router=router):
                r = self.matrix["metrics"][router]["recall"]
                fns = self.matrix["fns"][router]
                msg = (
                    f"{router} recall {r:.3f} below Phase A floor {floor:.2f}. "
                    f"FNs ({len(fns)}):\n"
                    + "\n".join(f"  {cid} {prompt!r} got={act!r} exp={exp!r}"
                                for cid, prompt, act, exp in fns)
                )
                self.assertGreaterEqual(r, floor, msg=msg)

    def test_no_new_guardrail_regressions(self):
        observed = {(cid, router) for cid, router, *_ in self.matrix["guardrail_failures"]}
        new = observed - self.PHASE_B_GUARDRAIL_TARGETS
        details = {
            (cid, router): (prompt, act, exp)
            for cid, router, prompt, act, exp in self.matrix["guardrail_failures"]
        }
        msg = "NEW guardrail regressions (not in PHASE_B_GUARDRAIL_TARGETS):\n" + "\n".join(
            f"  {cid} [{router}] {details[(cid, router)][0]!r} "
            f"got={details[(cid, router)][1]!r} exp={details[(cid, router)][2]!r}"
            for cid, router in sorted(new)
        )
        self.assertEqual(set(), new, msg=msg)

    def test_phase_b_targets_still_failing_or_promote(self):
        """Inverse ratchet: if a Phase B target now passes, prompt the operator
        to remove it from PHASE_B_GUARDRAIL_TARGETS so the regression set shrinks."""
        observed = {(cid, router) for cid, router, *_ in self.matrix["guardrail_failures"]}
        promoted = self.PHASE_B_GUARDRAIL_TARGETS - observed
        msg = (
            "Phase B guardrails now passing -- remove from "
            "RoutingCorpusTests.PHASE_B_GUARDRAIL_TARGETS:\n"
            + "\n".join(f"  {cid} [{router}]" for cid, router in sorted(promoted))
        )
        self.assertEqual(set(), promoted, msg=msg)


if __name__ == "__main__":
    unittest.main()
