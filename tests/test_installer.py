import ast
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "codex_provider_switcher.py").read_text(encoding="utf-8")
VERSION = next(
    node.value.value
    for node in ast.parse(SOURCE).body
    if isinstance(node, ast.Assign)
    and any(isinstance(target, ast.Name) and target.id == "__version__" for target in node.targets)
)


class InstallerVersionTests(unittest.TestCase):
    def test_release_versions_agree(self):
        metadata = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        installer = (ROOT / "install.sh").read_text(encoding="utf-8")
        self.assertEqual(re.search(r'^version = "([^"]+)"', metadata, re.M).group(1), VERSION)
        self.assertIn(f"CODEX_SWITCHER_VERSION:-v{VERSION}", installer)


@unittest.skipUnless(os.name == "posix", "Requires a POSIX shell (Linux/macOS CI)")
class StandaloneInstallerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.tools = self.root / "tools"
        self.tools.mkdir()
        self.bin_dir = self.root / "bin"
        self.data_dir = self.root / "data"
        self.fixture = self.root / "download.py"
        self.fixture.write_text(SOURCE, encoding="utf-8")
        self.log = self.root / "download-args.txt"
        self.shell = shutil.which("sh")
        self.env = {
            **os.environ,
            "HOME": str(self.root / "home"),
            "PATH": str(self.tools),
            "CODEX_SWITCHER_VERSION": f"v{VERSION}",
            "CODEX_SWITCHER_BIN_DIR": str(self.bin_dir),
            "CODEX_SWITCHER_DATA_DIR": str(self.data_dir),
            "INSTALLER_TEST_SOURCE": str(self.fixture),
            "INSTALLER_TEST_LOG": str(self.log),
            "INSTALLER_TEST_FAIL": "0",
        }
        # Restrict PATH so downloader and Python availability are deterministic.
        for name in ("mkdir", "mktemp", "cp", "mv", "rm", "chmod", "head", "tail", "sed"):
            (self.tools / name).symlink_to(shutil.which(name))
        self.write_tool("python3", f'exec {shlex.quote(sys.executable)} "$@"\n')
        self.write_tool("id", "printf '1000\\n'\n")
        self.write_tool("curl", self.downloader())

    def write_tool(self, name, content):
        path = self.tools / name
        path.write_text("#!/bin/sh\nset -eu\n" + content, encoding="utf-8")
        path.chmod(0o755)

    @staticmethod
    def downloader():
        return """\
printf '%s\\n' "$@" > "$INSTALLER_TEST_LOG"
while [ "$#" -gt 0 ]; do
  case "$1" in
    -o|-qO) output="$2"; shift ;;
  esac
  shift
done
cp "$INSTALLER_TEST_SOURCE" "$output"
if [ "$INSTALLER_TEST_FAIL" = 1 ]; then
  exit 22
fi
"""

    def install(self):
        # Feed the script on stdin, as with curl ... | sh.
        return subprocess.run(
            [self.shell],
            input=(ROOT / "install.sh").read_text(encoding="utf-8"),
            env=self.env,
            cwd=self.root,
            capture_output=True,
            text=True,
            timeout=30,
        )

    def assert_installed(self):
        for name in ("cps", "codex-provider-switcher"):
            result = subprocess.run(
                [str(self.bin_dir / name), "--version"],
                env=self.env,
                capture_output=True,
                text=True,
                timeout=10,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(VERSION, result.stdout)
        self.assertFalse((self.root / "home" / ".codex").exists())
        self.assertFalse((self.root / "home" / ".codex-provider-switcher").exists())
        self.assertEqual(list(self.root.rglob("*.tmp.*")), [])

    def test_both_commands_and_repeat_install(self):
        self.env.pop("CODEX_SWITCHER_VERSION")
        for _ in range(2):
            result = self.install()
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assert_installed()
        self.assertIn(f"/v{VERSION}/codex_provider_switcher.py", self.log.read_text())
        self.assertIn("export PATH=", result.stdout)

    def test_launcher_quotes_paths_and_preserves_arguments(self):
        self.data_dir = self.root / "data ' $not_a_variable `not_a_command`"
        self.bin_dir = self.root / "bin with spaces"
        self.env["CODEX_SWITCHER_DATA_DIR"] = str(self.data_dir)
        self.env["CODEX_SWITCHER_BIN_DIR"] = str(self.bin_dir)
        self.assertEqual(self.install().returncode, 0)
        self.assert_installed()
        help_result = subprocess.run(
            [str(self.bin_dir / "cps"), "--codex-home", "path with spaces", "--help"],
            env=self.env, capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(help_result.returncode, 0, help_result.stderr)

    def test_wget_fallback_and_bom_removal(self):
        (self.tools / "curl").unlink()
        self.write_tool("wget", self.downloader())
        self.fixture.write_bytes(b"\xef\xbb\xbf" + SOURCE.encode("utf-8"))
        self.assertEqual(self.install().returncode, 0)
        self.assert_installed()
        self.assertTrue((self.data_dir / "codex_provider_switcher.py").read_bytes().startswith(b"#!"))

    def test_relative_directory_overrides_are_resolved(self):
        self.env["CODEX_SWITCHER_BIN_DIR"] = "bin"
        self.env["CODEX_SWITCHER_DATA_DIR"] = "data"
        self.assertEqual(self.install().returncode, 0)
        self.assert_installed()

    def test_existing_symlink_is_replaced_without_modifying_its_target(self):
        other = self.root / "old-command"
        other.write_text("other installation\n", encoding="utf-8")
        self.bin_dir.mkdir()
        (self.bin_dir / "cps").symlink_to(other)
        self.assertEqual(self.install().returncode, 0)
        self.assert_installed()
        self.assertFalse((self.bin_dir / "cps").is_symlink())
        self.assertEqual(other.read_text(), "other installation\n")

    def test_download_failure_leaves_old_installation_intact(self):
        self.assertEqual(self.install().returncode, 0)
        self.fixture.write_text("partial download", encoding="utf-8")
        self.env["INSTALLER_TEST_FAIL"] = "1"
        self.assertNotEqual(self.install().returncode, 0)
        self.assertEqual((self.data_dir / "codex_provider_switcher.py").read_text(), SOURCE)
        self.assert_installed()

    def test_invalid_or_wrong_version_download_is_not_installed(self):
        self.assertEqual(self.install().returncode, 0)
        for data in ("<html>Not Found</html>", '__version__ = "0.0.0"\n', ""):
            with self.subTest(data=data):
                self.fixture.write_text(data, encoding="utf-8")
                result = self.install()
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("Existing installation was not changed", result.stderr)
                self.assertEqual((self.data_dir / "codex_provider_switcher.py").read_text(), SOURCE)
                self.assert_installed()

    def test_explicit_version_is_used(self):
        self.env["CODEX_SWITCHER_VERSION"] = "v0.2.4"
        self.fixture.write_text('__version__ = "0.2.4"\n', encoding="utf-8")
        result = self.install()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("/v0.2.4/codex_provider_switcher.py", self.log.read_text())

    def test_user_defaults_and_path_already_present(self):
        self.env.pop("CODEX_SWITCHER_BIN_DIR")
        self.env.pop("CODEX_SWITCHER_DATA_DIR")
        self.bin_dir = self.root / "home" / ".local" / "bin"
        self.env["PATH"] = f"{self.bin_dir}:{self.tools}"
        result = self.install()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_installed()
        self.assertNotIn("export PATH=", result.stdout)
        self.assertTrue((self.root / "home/.local/share/codex-provider-switcher/codex_provider_switcher.py").exists())

    def test_missing_or_old_python_stops_before_download(self):
        for old_python in (True, False):
            with self.subTest(old_python=old_python):
                if old_python:
                    self.write_tool("python3", "exit 1\n")
                else:
                    (self.tools / "python3").unlink()
                result = self.install()
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("Python 3.10 or newer", result.stderr)
                self.assertFalse(self.log.exists())
                self.assertFalse(self.bin_dir.exists())

    def test_missing_downloader_stops_before_creating_directories(self):
        (self.tools / "curl").unlink()
        result = self.install()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("curl or wget is required", result.stderr)
        self.assertFalse(self.bin_dir.exists())

    def test_existing_directory_is_not_overwritten(self):
        (self.bin_dir / "cps").mkdir(parents=True)
        result = self.install()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Cannot replace a directory", result.stderr)
        self.assertFalse(self.log.exists())


if __name__ == "__main__":
    unittest.main()
