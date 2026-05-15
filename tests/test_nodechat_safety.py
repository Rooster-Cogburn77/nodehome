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
    )


class NodechatSafetyTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
