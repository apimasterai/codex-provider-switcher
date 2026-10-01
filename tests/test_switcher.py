import tempfile
import unittest
import os
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

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
            with patch.object(store, "_system_set", return_value=False), patch.object(store, "_system_get", return_value=None):
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


def _line(obj):
    import json

    return json.dumps(obj, separators=(",", ":")).encode("utf-8") + b"\n"


def _meta(thread_id, provider, base=None):
    payload = {"id": thread_id, "cwd": "C:\\work", "model_provider": provider}
    if base:
        payload["history_base"] = base
    return _line({"type": "session_meta", "payload": payload})


def _item(payload):
    return _line({"type": "response_item", "payload": payload})


class HistoryRepairTests(unittest.TestCase):
    def test_switch_toggles_model_catalog(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            codex_home = root / "codex"
            codex_home.mkdir()
            (codex_home / "model_catalog.merged.json").write_text('{"models":[]}', encoding="utf-8")
            switcher = Switcher(codex_home, root / "profiles")
            switcher.ensure_state_dir()
            with redirect_stdout(StringIO()):
                switcher.use_profile("apimaster", api_key="sk-test-key")
                self.assertIn("model_catalog_json", (codex_home / "config.toml").read_text(encoding="utf-8"))
                switcher.use_profile("official")
            self.assertNotIn("model_catalog_json", (codex_home / "config.toml").read_text(encoding="utf-8"))

    def test_repair_drops_unreplayable_reasoning_and_fixes_lineage(self):
        import json
        import sqlite3

        parent_id = "0000000a-0000-0000-0000-000000000001"
        child_id = "0000000b-0000-0000-0000-000000000002"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            codex_home = root / "codex"
            sessions = codex_home / "sessions" / "2026" / "10" / "01"
            sessions.mkdir(parents=True)
            keep = {"type": "reasoning", "id": "rs_real", "encrypted_content": "gAAAA", "summary": []}
            drop = {"type": "reasoning", "id": "rs_proxy", "summary": []}
            message = {"type": "message", "id": "item_abc", "role": "user", "content": []}
            parent_lines = [_meta(parent_id, "apimaster"), _item(drop), _item(keep), _item(message), _item(keep)]
            cutoff = sum(len(line) for line in parent_lines[:4])
            parent_path = sessions / f"rollout-x-{parent_id}.jsonl"
            parent_path.write_bytes(b"".join(parent_lines))
            base = {"thread_id": parent_id, "end_ordinal_exclusive": 4, "end_byte_offset": cutoff}
            child_path = sessions / f"rollout-y-{child_id}.jsonl"
            child_path.write_bytes(_meta(child_id, "apimaster", base) + _item(keep))
            db = sqlite3.connect(codex_home / "thread_history_1.sqlite")
            db.execute("create table thread_history_projection_state (thread_id text, next_rollout_byte_offset integer, next_rollout_ordinal integer)")
            for table in ("thread_turns", "thread_items", "thread_realtime_items"):
                db.execute(f"create table {table} (thread_id text)")
            db.execute("insert into thread_history_projection_state values (?, ?, 0)", (parent_id, parent_path.stat().st_size))
            db.commit()
            db.close()

            switcher = Switcher(codex_home, root / "profiles")
            switcher.ensure_state_dir()
            with redirect_stdout(StringIO()):
                switcher.repair_desktop_history_hints()

            parent_data = parent_path.read_bytes()
            self.assertNotIn(b"rs_proxy", parent_data)
            self.assertIn(b"rs_real", parent_data)
            self.assertNotIn(b"item_abc", parent_data)
            first_child = json.loads(child_path.read_bytes().split(b"\n")[0])
            new_base = first_child["payload"]["history_base"]
            self.assertEqual(new_base["end_ordinal_exclusive"], 3)
            self.assertEqual(parent_data[: new_base["end_byte_offset"]].count(b"\n"), 3)
            self.assertEqual(parent_data[new_base["end_byte_offset"] - 1 : new_base["end_byte_offset"]], b"\n")
            self.assertIn(b'"model_provider":"openai"', parent_data.split(b"\n")[0])
            db = sqlite3.connect(codex_home / "thread_history_1.sqlite")
            self.assertEqual(db.execute("select count(*) from thread_history_projection_state").fetchone()[0], 0)
            db.close()


if __name__ == "__main__":
    unittest.main()
