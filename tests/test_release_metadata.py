import re
import unittest
from pathlib import Path

from codex_provider_switcher import __version__


ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = "https://github.com/RomaCredit/codex-provider-switcher"


class ReleaseMetadataTests(unittest.TestCase):
    def test_versioned_documentation_and_installers(self):
        for name in ("README.md", "README.zh-CN.md"):
            text = (ROOT / name).read_text(encoding="utf-8")
            for version in re.findall(r"/(v[\d.]+)/install\.(?:sh|ps1)", text):
                self.assertEqual(version, "v" + __version__)
            self.assertIn(REPOSITORY + "/releases", text)
            self.assertIn("https://github.com/RomaCredit/claude-provider-switcher", text)
            self.assertNotRegex(text, r"\]\((?:README[^)]*|LICENSE)\)")
        windows = (ROOT / "install.ps1").read_text(encoding="utf-8")
        self.assertIn(f"/refs/tags/v{__version__}.zip", windows)
        self.assertIn("$LASTEXITCODE -ne 0", windows)

    def test_release_metadata(self):
        citation = (ROOT / "CITATION.cff").read_text(encoding="utf-8")
        self.assertIn(f"version: {__version__}\n", citation)
        self.assertIn(REPOSITORY, citation)
        self.assertIn(f"## {__version__}\n", (ROOT / "CHANGELOG.md").read_text())
        metadata = (ROOT / "pyproject.toml").read_text()
        self.assertIn("dependencies = []", metadata)
        for keyword in ("codex-desktop", "session-history", "provider-switcher"):
            self.assertIn(keyword, metadata)

    def test_community_resources(self):
        for name in ("CONTRIBUTING.md", "SECURITY.md", "RELEASE.md"):
            self.assertTrue((ROOT / name).is_file())
        for name in ("installation.yml", "provider.yml", "history.yml", "config.yml"):
            self.assertTrue((ROOT / ".github" / "ISSUE_TEMPLATE" / name).is_file())
