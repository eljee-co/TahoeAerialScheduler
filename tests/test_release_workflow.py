import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest


WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/release.yml"


def workflow_script(step_name):
    section = WORKFLOW.read_text().split(f"      - name: {step_name}\n", 1)[1]
    section = section.split("\n      - ", 1)[0]
    return textwrap.dedent(section.split("        run: |\n", 1)[1])


class ReleaseWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        (self.root / "VERSION").write_text("0.1.4\n")
        (self.root / "dist").mkdir()
        bin_dir = self.root / "bin"
        bin_dir.mkdir()
        (bin_dir / "python3").symlink_to(sys.executable)
        for name, content in {
            "git": "#!/bin/bash\nexit 1\n",
            "gh": """#!/bin/bash
case "$MOCK_RELEASE_CASE" in
missing) echo 'release not found' >&2; exit 1 ;;
forbidden) echo 'HTTP 403: Resource not accessible by integration' >&2; exit 1 ;;
published) echo '{"isDraft":false}' ;;
draft) echo '{"isDraft":true}' ;;
esac
""",
        }.items():
            command = bin_dir / name
            command.write_text(content)
            command.chmod(0o755)
        self.env = {
            **os.environ,
            "PATH": f"{bin_dir}:/usr/bin:/bin",
            "GITHUB_REF_TYPE": "branch",
            "GITHUB_REF_NAME": "main",
            "REQUESTED_TAG": "",
            "RELEASE_TAG": "v0.1.4",
            "GITHUB_OUTPUT": str(self.root / "output"),
            "MOCK_RELEASE_CASE": "missing",
        }

    def run_step(self, name):
        script = workflow_script(name)
        for filename in ("tahoe-existing-release.json", "tahoe-release-error"):
            script = script.replace(f"/tmp/{filename}", str(self.root / filename))
        return subprocess.run(
            ["/bin/bash", "-e", "-o", "pipefail", "-c", script],
            cwd=self.root,
            env=self.env,
            text=True,
            capture_output=True,
        )

    def test_missing_release_proceeds_without_ripgrep(self):
        self.assertIsNone(shutil.which("rg", path=self.env["PATH"]))
        result = self.run_step("Resolve and validate the version")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("publish=true\n", (self.root / "output").read_text())

    def test_permission_failure_stops_publication(self):
        self.env["MOCK_RELEASE_CASE"] = "forbidden"
        result = self.run_step("Resolve and validate the version")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("HTTP 403", result.stderr)
        self.assertNotIn("publish=true", (self.root / "output").read_text())

    def test_published_release_stays_unchanged(self):
        self.env["MOCK_RELEASE_CASE"] = "published"
        result = self.run_step("Resolve and validate the version")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("publish=false\n", (self.root / "output").read_text())

    def test_existing_draft_stops_for_inspection(self):
        self.env["MOCK_RELEASE_CASE"] = "draft"
        result = self.run_step("Resolve and validate the version")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Inspect the existing draft", result.stderr)

    def test_notes_include_only_the_requested_version(self):
        (self.root / "CHANGELOG.md").write_text(
            "# Changelog\n\n## [Unreleased]\n\n"
            "## [0.1.4] - 2026-10-12\n\n"
            "- Restore the selected Tahoe background.\n"
            "- Keep diagnostics bounded.\n\n"
            "## [0.1.3] - 2026-05-27\n\n- Older change.\n"
        )
        result = self.run_step("Extract reviewed release notes")
        self.assertEqual(result.returncode, 0, result.stderr)
        notes = (self.root / "dist/release-notes.md").read_text()
        self.assertTrue(notes.startswith("- Restore the selected Tahoe background.\n"))
        self.assertIn("- Keep diagnostics bounded.", notes)
        self.assertIn("The installer is per-user and unsigned.", notes)
        self.assertNotIn("Older change", notes)
        self.assertNotIn("## [", notes)

    def test_missing_notes_stop_publication(self):
        (self.root / "CHANGELOG.md").write_text("## [0.1.3]\n\n- Older change.\n")
        result = self.run_step("Extract reviewed release notes")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.root / "dist/release-notes.md").exists())

    def test_empty_notes_stop_publication(self):
        (self.root / "CHANGELOG.md").write_text("## [0.1.4]\n\n## [0.1.3]\n\n- Older change.\n")
        result = self.run_step("Extract reviewed release notes")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.root / "dist/release-notes.md").exists())


if __name__ == "__main__":
    unittest.main()
