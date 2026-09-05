import tempfile
import unittest
import os
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from codex_provider_switcher import (
    CredentialStore,
    Profile,
    Switcher,
    load_profiles,
    mask_secret,
    parse_args,
    save_profiles,
)


class SwitcherTests(unittest.TestCase):
    def test_cli_mode_is_optional(self):
        self.assertIsNone(parse_args([]).mode)
        self.assertEqual(parse_args(["status"]).mode, "status")

    def test_top_level_config_values(self):
        original = 'model = "old"\n\n[features]\nflag = true\n'
        updated = Switcher.set_top_level_string(original, "model", "new")
        self.assertEqual(Switcher.get_top_level_value(updated, "model"), "new")
        self.assertIn("[features]", updated)

    def test_provider_block_is_replaced(self):
        original = '[model_providers.apimaster]\nbase_url = "old"\n\n[features]\nflag = true\n'
        updated = Switcher.upsert_apimaster_provider(original, "https://example.com/v1", False)
        self.assertEqual(updated.count("[model_providers.apimaster]"), 1)
        self.assertIn('base_url = "https://example.com/v1"', updated)
        self.assertIn("[features]", updated)

    def test_status_with_empty_codex_home(self):
        with tempfile.TemporaryDirectory() as directory:
            switcher = Switcher(Path(directory))
            switcher.status()

    def test_default_profiles_are_created(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            profiles = load_profiles(root / "profiles.toml")
            self.assertEqual(set(profiles), {"official", "apimaster", "openrouter"})
            self.assertTrue((root / "profiles.toml").exists())

    def test_custom_profiles_round_trip_and_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "profiles.toml"
            save_profiles(path, {"local": Profile("local", "api", "http://localhost:8080/v1", "test-model")})
            loaded = load_profiles(path)
            self.assertEqual(loaded["local"].default_model, "test-model")
            path.write_text('[profiles.local]\ntype = "api"\nbase_url = "not a url"\ndefault_model = "x"\n', encoding="utf-8")
            with self.assertRaises(ValueError):
                load_profiles(path)

    def test_credentials_fallback_is_masked_and_private(self):
        with tempfile.TemporaryDirectory() as directory:
            store = CredentialStore(Path(directory))
            store.set("local", "sk-1234567890")
            self.assertEqual(store.get("local"), "sk-1234567890")
            self.assertEqual(mask_secret("sk-1234567890"), "sk-1...7890")
            if os.name != "nt":
                self.assertEqual((Path(directory) / "credentials.toml").stat().st_mode & 0o777, 0o600)

    def test_use_custom_profile_updates_config_and_history_provider(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            codex_home = root / "codex"
            profile_home = root / "profiles"
            switcher = Switcher(codex_home, profile_home)
            switcher.ensure_state_dir()
            out = StringIO()
            with redirect_stdout(out):
                switcher.use_profile("apimaster", api_key="sk-test-key")
            config = (codex_home / "config.toml").read_text(encoding="utf-8")
            self.assertIn('model_provider = "apimaster"', config)
            self.assertEqual((profile_home / "active-profile").read_text(), "apimaster")
            self.assertNotIn("sk-test-key", out.getvalue())

    def test_profile_command_arguments(self):
        args = parse_args(["profile", "remove", "custom"])
        self.assertEqual(args.mode, "profile")
        self.assertEqual(args.profile_name, "custom")


if __name__ == "__main__":
    unittest.main()
