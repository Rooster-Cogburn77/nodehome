import contextlib
import importlib.util
import io
import pathlib
import shutil
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
