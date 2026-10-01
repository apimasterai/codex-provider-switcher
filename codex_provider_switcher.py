#!/usr/bin/env python3
"""Cross-platform Codex Desktop provider profile switcher."""

from __future__ import annotations

import argparse
import ctypes
import getpass
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

if os.name == "nt":
    from ctypes import wintypes

try:
    import tomllib
except ImportError:  # Python 3.10
    tomllib = None

__version__ = "0.3.2"
DEFAULT_MODEL = "gpt-5.6-sol"
DEFAULT_PROFILES = {
    "official": {"type": "subscription"},
    "apimaster": {"type": "api", "base_url": "https://apimaster.ai/v1", "default_model": "gpt-5.6-sol"},
    "openrouter": {"type": "api", "base_url": "https://openrouter.ai/api/v1", "default_model": "anthropic/claude-sonnet-4.6"},
}
MESSAGES = {
    "state_db_missing": "Codex state DB not found: {0}",
    "sessions_missing": "Codex sessions directory not found: {0}",
    "global_state_missing": "Codex Desktop global state not found: {0}",
    "restart": "Restart Codex Desktop if the sidebar still shows stale project chat lists.",
    "invalid_choice": "Invalid choice. Please try again.",
    "profile_missing": "Profile not found: {0}",
    "profile_saved": "Saved profile: {0}",
    "profile_removed": "Removed profile: {0}",
    "profile_exists": "Profile already exists: {0}",
    "key_required": "API key is required for profile: {0}",
    "paste_key": "Paste API key for {0}: ",
    "official_auth_missing": "No saved subscription auth profile found. Use Codex login if the subscription is not active.",
    "switched": "Switched Codex to profile '{0}': model={1}, base_url={2}",
    "switched_subscription": "Switched Codex to subscription profile '{0}'.",
    "history_untouched": "Conversation history is untouched. Restart Codex Desktop or open a new turn if the app has cached provider settings.",
    "models_ok": "Provider /models OK. First models:",
    "models_not_applicable": "Connectivity testing is only available for API profiles.",
    "profile_test_failed": "Provider test failed: {0}",
    "credentials_missing": "No API key found for profile '{0}'. Add one with profile add or enter it when switching.",
}


def tr(key: str, *args: Any) -> str:
    return (MESSAGES.get(key) or key).format(*args)


def timestamp() -> str:
    return time.strftime("%Y%m%d-%H%M%S")


def _toml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=True)


@dataclass
class Profile:
    name: str
    type: str
    base_url: str | None = None
    default_model: str | None = None
    wire_api: str = "responses"
    model_catalog: str | None = None

    @property
    def is_api(self) -> bool:
        return self.type == "api"

    def validate(self) -> None:
        allowed = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_ .".replace(" ", "")
        if not self.name or any(c not in allowed for c in self.name):
            raise ValueError(f"Invalid profile name: {self.name}")
        if self.type not in {"api", "subscription"}:
            raise ValueError(f"Invalid profile type for {self.name}: {self.type}")
        if self.is_api:
            parsed = urlparse(self.base_url or "")
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise ValueError(f"Invalid base_url for profile '{self.name}'")
            if not self.default_model:
                raise ValueError(f"API profile '{self.name}' requires default_model")
            if self.wire_api not in {"responses", "chat"}:
                raise ValueError(f"Invalid wire_api for profile '{self.name}'")


def _parse_simple_toml(text: str) -> dict[str, Any]:
    result: dict[str, Any] = {"profiles": {}}
    current: dict[str, Any] | None = None
    flat_profiles = False
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[profiles.") and line.endswith("]"):
            flat_profiles = False
            current = result["profiles"].setdefault(line[10:-1], {})
        elif line == "[profiles]":
            flat_profiles = True
            current = result["profiles"]
        elif current is not None and "=" in line:
            key, value = (part.strip() for part in line.split("=", 1))
            current[key] = json.loads(value) if value.startswith('"') else value
            if flat_profiles:
                result["profiles"][key] = current[key]
    return result


def load_profiles(path: Path) -> dict[str, Profile]:
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        save_profiles(path, {name: Profile(name, **values) for name, values in DEFAULT_PROFILES.items()})
    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8")) if tomllib else _parse_simple_toml(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError(f"Invalid profiles file: {exc}") from exc
    profiles: dict[str, Profile] = {}
    for name, values in (raw.get("profiles") or {}).items():
        if not isinstance(values, dict):
            raise ValueError(f"Invalid profile: {name}")
        profile = Profile(str(name), str(values.get("type", "")), values.get("base_url"), values.get("default_model"), str(values.get("wire_api", "responses")), values.get("model_catalog"))
        profile.validate()
        profiles[profile.name] = profile
    return profiles


def save_profiles(path: Path, profiles: dict[str, Profile]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    for name in sorted(profiles):
        profile = profiles[name]
        profile.validate()
        lines.extend([f"[profiles.{name}]", f"type = {_toml_string(profile.type)}"])
        if profile.base_url is not None:
            lines.append(f"base_url = {_toml_string(profile.base_url)}")
        if profile.default_model is not None:
            lines.append(f"default_model = {_toml_string(profile.default_model)}")
        if profile.is_api and profile.wire_api != "responses":
            lines.append(f"wire_api = {_toml_string(profile.wire_api)}")
        if profile.model_catalog:
            lines.append(f"model_catalog = {_toml_string(profile.model_catalog)}")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def mask_secret(value: str | None) -> str:
    if not value:
        return "missing"
    return "****" if len(value) <= 8 else f"{value[:4]}...{value[-4:]}"


class CredentialStore:
    """Use macOS Keychain or Windows Credential Manager, then a 0600 file."""

    def __init__(self, root: Path) -> None:
        self.root, self.path = root, root / "credentials.toml"

    def _system_get(self, profile: str) -> str | None:
        if sys.platform == "darwin":
            proc = subprocess.run(["security", "find-generic-password", "-s", f"codex-provider-switcher:{profile}", "-w"], capture_output=True, text=True, check=False)
            return proc.stdout.strip() or None
        if os.name == "nt":
            try:
                class Credential(ctypes.Structure):
                    _fields_ = [
                        ("Flags", wintypes.DWORD), ("Type", wintypes.DWORD),
                        ("TargetName", wintypes.LPWSTR), ("Comment", wintypes.LPWSTR),
                        ("LastWritten", wintypes.FILETIME), ("CredentialBlobSize", wintypes.DWORD),
                        ("CredentialBlob", ctypes.POINTER(ctypes.c_ubyte)),
                        ("Persist", wintypes.DWORD), ("AttributeCount", wintypes.DWORD),
                        ("Attributes", ctypes.c_void_p), ("TargetAlias", wintypes.LPWSTR),
                        ("UserName", wintypes.LPWSTR),
                    ]
                pointer = ctypes.POINTER(Credential)()
                target = f"codex-provider-switcher:{profile}"
                if not ctypes.windll.Advapi32.CredReadW(target, 1, 0, ctypes.byref(pointer)):
                    return None
                try:
                    item = pointer.contents
                    return ctypes.string_at(item.CredentialBlob, item.CredentialBlobSize).decode("utf-16-le").rstrip("\x00")
                finally:
                    ctypes.windll.Kernel32.LocalFree(pointer)
            except Exception:
                return None
        return None

    def _system_set(self, profile: str, value: str) -> bool:
        if sys.platform == "darwin":
            proc = subprocess.run(["security", "add-generic-password", "-U", "-s", f"codex-provider-switcher:{profile}", "-a", profile, "-w", value], capture_output=True, text=True, check=False)
            return proc.returncode == 0
        if os.name == "nt":
            try:
                class Credential(ctypes.Structure):
                    _fields_ = [
                        ("Flags", wintypes.DWORD), ("Type", wintypes.DWORD),
                        ("TargetName", wintypes.LPWSTR), ("Comment", wintypes.LPWSTR),
                        ("LastWritten", wintypes.FILETIME), ("CredentialBlobSize", wintypes.DWORD),
                        ("CredentialBlob", ctypes.c_void_p), ("Persist", wintypes.DWORD),
                        ("AttributeCount", wintypes.DWORD), ("Attributes", ctypes.c_void_p),
                        ("TargetAlias", wintypes.LPWSTR), ("UserName", wintypes.LPWSTR),
                    ]
                target = f"codex-provider-switcher:{profile}"
                blob = ctypes.create_unicode_buffer(value)
                item = Credential(
                    0, 1, target, None, wintypes.FILETIME(), ctypes.sizeof(blob),
                    ctypes.cast(blob, ctypes.c_void_p), 2, 0, None, None, profile,
                )
                return bool(ctypes.windll.Advapi32.CredWriteW(ctypes.byref(item), 0))
            except Exception:
                return False
        return False

    def _read_file(self) -> dict[str, str]:
        if not self.path.exists():
            return {}
        raw = _parse_simple_toml(self.path.read_text(encoding="utf-8"))
        return raw.get("profiles", {})

    def get(self, profile: str) -> str | None:
        return self._system_get(profile) or self._read_file().get(profile)

    def set(self, profile: str, value: str) -> None:
        if self._system_set(profile, value):
            return
        data = self._read_file()
        data[profile] = value
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text("[profiles]\n" + "\n".join(f"{name} = {_toml_string(key)}" for name, key in sorted(data.items())) + "\n", encoding="utf-8")
        if os.name != "nt":
            try:
                self.path.chmod(0o600)
            except OSError:
                pass


class Switcher:
    def __init__(self, codex_home: Path, profile_root: Path | None = None) -> None:
        self.codex_home = codex_home.expanduser()
        self.profile_root = (profile_root or Path(os.environ.get("CODEX_PROVIDER_SWITCHER_HOME", Path.home() / ".codex-provider-switcher"))).expanduser()
        self.profiles_path, self.active_path = self.profile_root / "profiles.toml", self.profile_root / "active-profile"
        self.credentials = CredentialStore(self.profile_root)
        self.config_path, self.auth_path = self.codex_home / "config.toml", self.codex_home / "auth.json"
        self.global_state_path, self.sessions_dir = self.codex_home / ".codex-global-state.json", self.codex_home / "sessions"
        self.state_db_path, self.state_dir = self.codex_home / "state_5.sqlite", self.codex_home / "provider-switcher"

    def say(self, message: str, *args: Any) -> None:
        print(tr(message, *args) if message in MESSAGES else message.format(*args))

    def warn(self, message: str, *args: Any) -> None:
        print("WARNING: " + (tr(message, *args) if message in MESSAGES else message.format(*args)), file=sys.stderr)

    def ensure_state_dir(self) -> None:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.profile_root.mkdir(parents=True, exist_ok=True)
        load_profiles(self.profiles_path)

    def profiles(self) -> dict[str, Profile]:
        return load_profiles(self.profiles_path)

    def backup_current(self) -> None:
        self.ensure_state_dir()
        stamp = timestamp()
        if self.config_path.exists():
            shutil.copy2(self.config_path, self.state_dir / f"config.{stamp}.toml.bak")
        if self.auth_path.exists():
            shutil.copy2(self.auth_path, self.state_dir / f"auth.{stamp}.json.bak")

    def read_config(self) -> str:
        return self.config_path.read_text(encoding="utf-8") if self.config_path.exists() else ""

    def write_config(self, text: str) -> None:
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text(text, encoding="utf-8")

    @staticmethod
    def _head_tail(text: str) -> tuple[str, str]:
        marker = text.find("\n[")
        return (text[:marker], text[marker:]) if marker >= 0 else (text, "")

    @staticmethod
    def get_top_level_value(text: str, key: str) -> str | None:
        head, _ = Switcher._head_tail(text)
        for line in head.splitlines():
            if line.strip() and "=" in line and not line.strip().startswith("#"):
                left, right = line.strip().split("=", 1)
                if left.strip() == key:
                    return right.strip().strip('"').strip("'") or None
        return None

    @staticmethod
    def set_top_level_string(text: str, key: str, value: str) -> str:
        head, tail = Switcher._head_tail(text)
        out, replaced = [], False
        for line in head.splitlines():
            if line.strip() and "=" in line and line.split("=", 1)[0].strip() == key:
                out.append(f"{key} = {_toml_string(value)}")
                replaced = True
            else:
                out.append(line)
        if not replaced:
            out.append(f"{key} = {_toml_string(value)}")
        return "\n".join(out).rstrip() + tail

    @staticmethod
    def remove_top_level_key(text: str, key: str) -> str:
        head, tail = Switcher._head_tail(text)
        return "\n".join(line for line in head.splitlines() if not (line.strip() and "=" in line and line.split("=", 1)[0].strip() == key)).rstrip() + tail

    @staticmethod
    def upsert_provider(text: str, profile: Profile) -> str:
        block = f"\n[model_providers.{profile.name}]\nname = {_toml_string(profile.name)}\nbase_url = {_toml_string(profile.base_url or '')}\nwire_api = {_toml_string(profile.wire_api)}\nrequires_openai_auth = true\n"
        lines, out, replaced, index = text.splitlines(), [], False, 0
        section = f"[model_providers.{profile.name}]"
        while index < len(lines):
            if lines[index].strip() == section:
                if not replaced:
                    out.extend(block.strip("\n").splitlines())
                    replaced = True
                index += 1
                while index < len(lines) and not lines[index].lstrip().startswith("["):
                    index += 1
            else:
                out.append(lines[index])
                index += 1
        result = "\n".join(out).rstrip()
        return result + ("\n" if replaced else block)

    @staticmethod
    def upsert_apimaster_provider(text: str, base_url: str, use_chat: bool) -> str:
        """Compatibility helper retained for callers of the 0.2.x API."""
        profile = Profile("apimaster", "api", base_url, DEFAULT_MODEL, "chat" if use_chat else "responses")
        return Switcher.upsert_provider(text, profile)

    def current_profile_name(self) -> str:
        if self.active_path.exists():
            return self.active_path.read_text(encoding="utf-8").strip()
        provider = self.get_top_level_value(self.read_config(), "model_provider")
        if provider and provider in self.profiles():
            return provider
        return "official" if "official" in self.profiles() else next(iter(self.profiles()), "official")

    def catalog_for(self, profile: Profile) -> Path | None:
        if not profile.is_api:
            return None
        if profile.model_catalog:
            return Path(profile.model_catalog).expanduser()
        default = self.codex_home / "model_catalog.merged.json"
        return default if default.exists() else None

    def apply_model_catalog(self, profile: Profile) -> None:
        catalog = self.catalog_for(profile)
        text = self.read_config()
        if catalog and catalog.exists():
            text = self.set_top_level_string(text, "model_catalog_json", str(catalog))
        else:
            text = self.remove_top_level_key(text, "model_catalog_json")
        self.write_config(text)

    def history_provider(self) -> str:
        profile = self.profiles().get(self.current_profile_name())
        return profile.name if profile and profile.is_api else "openai"

    def available_models(self) -> set[str]:
        profile = self.profiles().get(self.current_profile_name())
        path = self.catalog_for(profile) if profile else None
        if not path and not (profile and profile.is_api):
            path = self.codex_home / "models_cache.json"
        slugs: set[str] = set()
        try:
            if path and path.exists():
                data = json.loads(path.read_text(encoding="utf-8"))
                slugs = {str(m["slug"]) for m in data.get("models", []) if isinstance(m, dict) and m.get("slug")}
        except (OSError, ValueError):
            return set()
        return slugs

    def repair_state_db(self, desired_provider: str) -> None:
        if not self.state_db_path.exists():
            self.warn("state_db_missing", self.state_db_path)
            return
        self.ensure_state_dir()
        backup = self.state_dir / f"state_5.{timestamp()}.sqlite.bak"
        src = sqlite3.connect(self.state_db_path)
        try:
            dst = sqlite3.connect(backup)
            try:
                src.backup(dst)
            finally:
                dst.close()
            cur = src.cursor()
            rows = cur.execute("select id, cwd from threads").fetchall()
            cwd_updated = 0
            for thread_id, cwd in rows:
                if isinstance(cwd, str) and cwd.startswith("\\\\?\\"):
                    cur.execute("update threads set cwd = ? where id = ?", (cwd[4:], thread_id))
                    cwd_updated += 1
            path_updated = cur.execute("update threads set rollout_path = substr(rollout_path, 5) where rollout_path like ?", ("\\\\?\\%",)).rowcount
            model_updated = 0
            available, fallback = self.available_models(), self.get_top_level_value(self.read_config(), "model")
            if available and fallback:
                placeholders = ",".join("?" * len(available))
                model_updated = cur.execute(f"update threads set model = ? where model is not null and model <> '' and model not in ({placeholders})", (fallback, *sorted(available))).rowcount
            provider_updated = cur.execute("update threads set model_provider = ? where model_provider <> ?", (desired_provider, desired_provider)).rowcount
            src.commit()
        finally:
            src.close()
        print(f"Repaired Codex state DB: cwd_checked={len(rows)}, cwd_updated={cwd_updated}, provider={desired_provider}, provider_updated={provider_updated}, model_updated={model_updated}, path_updated={path_updated}, backup={backup}")

    def repair_session_metadata(self, desired_provider: str) -> None:
        if not self.sessions_dir.exists():
            self.warn("sessions_missing", self.sessions_dir)
            return
        backup_dir = self.state_dir / f"session-meta.{timestamp()}.bak"
        checked = changed = errors = 0
        for path in self.sessions_dir.rglob("rollout-*.jsonl"):
            checked += 1
            try:
                text = path.read_bytes().decode("utf-8")
                if not text:
                    continue
                first, separator, rest = text.partition("\n")
                meta = json.loads(first.rstrip("\r"))
                if meta.get("type") != "session_meta":
                    continue
                payload = meta.setdefault("payload", {})
                cwd = str(payload.get("cwd") or "")
                next_cwd = cwd[4:] if cwd.startswith("\\\\?\\") else cwd
                if payload.get("model_provider") == desired_provider and next_cwd == cwd:
                    continue
                payload["model_provider"] = desired_provider
                if next_cwd:
                    payload["cwd"] = next_cwd
                backup_path = backup_dir / path.relative_to(self.sessions_dir)
                backup_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, backup_path)
                path.write_bytes((json.dumps(meta, ensure_ascii=False, separators=(",", ":")) + (separator or "\n") + rest).encode("utf-8"))
                changed += 1
            except Exception:
                errors += 1
        print(f"Repaired Codex session metadata: checked={checked}, changed={changed}, provider={desired_provider}, parse_errors={errors}, backup_dir={backup_dir if changed else 'not-needed'}")

    @staticmethod
    def _foreign_item_id(value: Any) -> bool:
        return isinstance(value, str) and (value.startswith("item_") or re.fullmatch(r"[0-9a-f]{8}-[0-9a-f]{4}-.*", value) is not None)

    @staticmethod
    def _is_replay_unsafe_reasoning(payload: dict[str, Any]) -> bool:
        # OpenAI cannot replay reasoning without its own encrypted content (store=false).
        return payload.get("type") == "reasoning" and (not payload.get("encrypted_content") or bool(payload.get("content")) or Switcher._foreign_item_id(payload.get("id")))

    @staticmethod
    def _response_item(line: bytes) -> dict[str, Any] | None:
        if b'"response_item"' not in line[:80]:
            return None
        try:
            obj = json.loads(line)
        except ValueError:
            return None
        return obj if isinstance(obj, dict) and obj.get("type") == "response_item" and isinstance(obj.get("payload"), dict) else None

    @staticmethod
    def _drops_line(line: bytes) -> bool:
        obj = Switcher._response_item(line)
        return bool(obj) and Switcher._is_replay_unsafe_reasoning(obj["payload"])

    def repair_foreign_item_ids(self) -> None:
        if not self.sessions_dir.exists():
            return
        backup_dir = self.state_dir / f"item-ids.{timestamp()}.bak"
        changed = dropped = stripped = 0
        for path in self.sessions_dir.rglob("rollout-*.jsonl"):
            try:
                raw = path.read_bytes()
                if b'"response_item"' not in raw:
                    continue
                out, touched = [], False
                for line in raw.split(b"\n"):
                    obj = self._response_item(line)
                    if obj:
                        payload = obj["payload"]
                        if self._is_replay_unsafe_reasoning(payload):
                            touched = True
                            dropped += 1
                            continue
                        if self._foreign_item_id(payload.get("id")):
                            touched = True
                            payload.pop("id", None)
                            stripped += 1
                            line = json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8") + (b"\r" if line.endswith(b"\r") else b"")
                    out.append(line)
                if touched:
                    backup_path = backup_dir / path.relative_to(self.sessions_dir)
                    backup_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(path, backup_path)
                    path.write_bytes(b"\n".join(out))
                    changed += 1
            except Exception:
                continue
        print(f"Repaired non-OpenAI item ids: files={changed}, reasoning_dropped={dropped}, ids_stripped={stripped}")

    @staticmethod
    def _rollout_thread_id(path: Path) -> str:
        return path.stem[-36:]

    @staticmethod
    def _first_meta(path: Path) -> dict[str, Any] | None:
        try:
            with path.open("rb") as handle:
                meta = json.loads(handle.readline())
            return meta if isinstance(meta, dict) and meta.get("type") == "session_meta" and isinstance(meta.get("payload"), dict) else None
        except (OSError, ValueError):
            return None

    def snapshot_lineage(self) -> dict[str, Any]:
        paths = {self._rollout_thread_id(p): p for p in self.sessions_dir.rglob("rollout-*.jsonl")} if self.sessions_dir.exists() else {}
        children: dict[str, dict[str, Any]] = {}
        for thread_id, path in paths.items():
            meta = self._first_meta(path)
            base = meta["payload"].get("history_base") if meta else None
            if isinstance(base, dict) and base.get("thread_id") in paths:
                children[thread_id] = base
        sources = {src: paths[src].read_bytes() for src in {b["thread_id"] for b in children.values()}}
        return {"paths": paths, "children": children, "sources": sources}

    def repair_lineage(self, snapshot: dict[str, Any]) -> None:
        paths, children, sources = snapshot["paths"], snapshot["children"], snapshot["sources"]
        order: list[str] = []

        def visit(thread_id: str) -> None:
            if thread_id in order:
                return
            if thread_id in children:
                visit(children[thread_id]["thread_id"])
            order.append(thread_id)

        for thread_id in children:
            visit(thread_id)
        new_bases: dict[str, dict[str, Any]] = {}
        deltas: dict[str, int] = {}
        backup_dir = self.state_dir / f"lineage.{timestamp()}.bak"
        updated = skipped = 0
        for child in (t for t in order if t in children):
            old, source = children[child], children[child]["thread_id"]
            current = paths[source].read_bytes().split(b"\n")
            cutoff, position, new_offset, consumed = old["end_byte_offset"], 0, 0, 0
            for line in sources[source].split(b"\n"):
                if position == cutoff:
                    break
                position += len(line) + 1
                if self._drops_line(line):
                    continue
                if consumed >= len(current):
                    position = -1
                    break
                new_offset += len(current[consumed]) + 1
                consumed += 1
            if position != cutoff or cutoff <= 0:
                skipped += 1
                continue
            new_offset += deltas.get(source, 0)
            parent_ordinal = new_bases.get(source, children.get(source, {})).get("end_ordinal_exclusive", 0)
            new = dict(old, end_ordinal_exclusive=parent_ordinal + consumed, end_byte_offset=new_offset)
            new_bases[child] = new
            if new == old:
                continue
            path = paths[child]
            first, separator, rest = path.read_bytes().partition(b"\n")
            meta = json.loads(first)
            meta["payload"]["history_base"] = new
            rewritten = json.dumps(meta, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            deltas[child] = len(rewritten) - len(first)
            backup_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, backup_dir / path.name)
            path.write_bytes(rewritten + separator + rest)
            updated += 1
        print(f"Repaired history lineage offsets: updated={updated}, skipped={skipped}, backup_dir={backup_dir if updated else 'not-needed'}")

    def reset_history_cache(self) -> None:
        db_path = self.codex_home / "thread_history_1.sqlite"
        if not db_path.exists() or not self.sessions_dir.exists():
            return
        sizes = {self._rollout_thread_id(p): p.stat().st_size for p in self.sessions_dir.rglob("rollout-*.jsonl")}
        stale: list[str] = []
        conn = sqlite3.connect(db_path)
        try:
            rows = conn.execute("select thread_id, next_rollout_byte_offset from thread_history_projection_state").fetchall()
            stale = [t for t, offset in rows if t in sizes and offset != sizes[t]]
            if stale:
                self.ensure_state_dir()
                shutil.copy2(db_path, self.state_dir / f"thread_history_1.{timestamp()}.sqlite.bak")
                for table in ("thread_turns", "thread_items", "thread_history_projection_state", "thread_realtime_items"):
                    conn.executemany(f"delete from {table} where thread_id = ?", [(t,) for t in stale])
                conn.commit()
        except sqlite3.Error as exc:
            self.warn(f"Could not reset Codex history cache: {exc}")
        finally:
            conn.close()
        print(f"Reset Codex history cache for {len(stale)} thread(s); Codex rebuilds it on next start.")

    def repair_desktop_history_hints(self) -> None:
        if self.global_state_path.exists() and self.sessions_dir.exists():
            self._repair_workspace_hints()
        else:
            if not self.global_state_path.exists():
                self.warn("global_state_missing", self.global_state_path)
            if not self.sessions_dir.exists():
                self.warn("sessions_missing", self.sessions_dir)
        snapshot = self.snapshot_lineage()
        if self.history_provider() == "openai":
            self.repair_foreign_item_ids()
        self.repair_session_metadata(self.history_provider())
        self.repair_lineage(snapshot)
        self.reset_history_cache()
        self.repair_state_db(self.history_provider())
        self.say("restart")

    def _repair_workspace_hints(self) -> None:
        state = json.loads(self.global_state_path.read_text(encoding="utf-8"))
        hints = dict(state.get("thread-workspace-root-hints") or {})
        found = added = updated = errors = 0
        for path in self.sessions_dir.rglob("rollout-*.jsonl"):
            try:
                meta = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
                if meta.get("type") != "session_meta":
                    continue
                payload = meta.get("payload") or {}
                thread_id, cwd = str(payload.get("id") or ""), str(payload.get("cwd") or "")
                if cwd.startswith("\\\\?\\"):
                    cwd = cwd[4:]
                if not thread_id or not cwd:
                    continue
                found += 1
                if thread_id not in hints:
                    hints[thread_id], added = cwd, added + 1
                elif hints[thread_id] != cwd:
                    hints[thread_id], updated = cwd, updated + 1
            except Exception:
                errors += 1
        self.state_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(self.global_state_path, self.state_dir / f"global-state.{timestamp()}.json.bak")
        state["thread-workspace-root-hints"] = hints
        self.global_state_path.write_text(json.dumps(state, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        print(f"Repaired Codex Desktop history hints: sessions={found}, added={added}, updated={updated}, parse_errors={errors}")

    def _save_subscription_snapshot(self, name: str) -> None:
        target = self.state_dir / "profiles" / name
        target.mkdir(parents=True, exist_ok=True)
        if self.config_path.exists():
            shutil.copy2(self.config_path, target / "config.toml")
        if self.auth_path.exists():
            shutil.copy2(self.auth_path, target / "auth.json")

    def _restore_subscription_snapshot(self, name: str) -> None:
        target = self.state_dir / "profiles" / name
        if (target / "config.toml").exists():
            shutil.copy2(target / "config.toml", self.config_path)
        else:
            self.write_config(self.remove_top_level_key(self.read_config(), "model_provider"))
        if (target / "auth.json").exists():
            shutil.copy2(target / "auth.json", self.auth_path)
        else:
            self.warn("official_auth_missing")

    def use_profile(self, name: str, api_key: str | None = None, model: str | None = None, base_url: str | None = None, chat_fallback: bool = False) -> None:
        profiles = self.profiles()
        if name not in profiles:
            raise SystemExit(tr("profile_missing", name))
        profile = profiles[name]
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.backup_current()
        current = self.current_profile_name()
        if current != name and current in profiles and profiles[current].type == "subscription":
            self._save_subscription_snapshot(current)
        if profile.is_api:
            key = api_key or self.credentials.get(name)
            if not key and self.auth_path.exists():
                try:
                    key = json.loads(self.auth_path.read_text(encoding="utf-8")).get("OPENAI_API_KEY")
                except (OSError, json.JSONDecodeError):
                    pass
            if not key:
                key = getpass.getpass(tr("paste_key", name))
            if not key:
                raise SystemExit(tr("key_required", name))
            self.credentials.set(name, key)
            selected_model, selected_url = model or profile.default_model or DEFAULT_MODEL, base_url or profile.base_url or ""
            effective = Profile(profile.name, profile.type, selected_url, selected_model, "chat" if chat_fallback else profile.wire_api)
            updated = self.set_top_level_string(self.read_config(), "model_provider", profile.name)
            updated = self.set_top_level_string(updated, "model", selected_model)
            updated = self.set_top_level_string(updated, "model_reasoning_effort", "high")
            self.write_config(self.upsert_provider(updated, effective))
            self.auth_path.write_text(json.dumps({"OPENAI_API_KEY": key}, indent=2), encoding="utf-8")
            self.say("switched", name, selected_model, selected_url)
        else:
            self._restore_subscription_snapshot(name)
            self.say("switched_subscription", name)
        self.apply_model_catalog(profile)
        self.active_path.write_text(name, encoding="utf-8")
        self.repair_desktop_history_hints()
        self.say("history_untouched")

    def status(self) -> None:
        name, profile = self.current_profile_name(), self.profiles().get(self.current_profile_name())
        model = self.get_top_level_value(self.read_config(), "model") or ((profile.default_model or "") if profile else "")
        auth = "missing"
        if profile and profile.is_api:
            key = self.credentials.get(name)
            auth = f"apikey ({mask_secret(key)})" if key else "missing"
        elif self.auth_path.exists():
            try:
                auth = str(json.loads(self.auth_path.read_text(encoding="utf-8")).get("auth_mode") or "subscription")
            except Exception:
                auth = "unknown"
        print(f"Profile: {name}\nType: {profile.type if profile else 'unknown'}\nModel: {model}\nAuth: {auth}\nProfiles: {self.profiles_path}\nSwitcher backups: {self.state_dir}")

    def test_profile(self, name: str, api_key: str | None = None) -> None:
        profile = self.profiles().get(name)
        if not profile:
            raise SystemExit(tr("profile_missing", name))
        if not profile.is_api:
            print(tr("models_not_applicable"))
            return
        key = api_key or self.credentials.get(name)
        if not key and self.auth_path.exists():
            try:
                key = json.loads(self.auth_path.read_text(encoding="utf-8")).get("OPENAI_API_KEY")
            except Exception:
                pass
        if not key:
            raise SystemExit(tr("credentials_missing", name))
        req = urllib.request.Request(profile.base_url.rstrip("/") + "/models", headers={"Authorization": f"Bearer {key}"}, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                data = json.loads(response.read().decode("utf-8"))
        except (OSError, urllib.error.HTTPError) as exc:
            raise SystemExit(tr("profile_test_failed", exc)) from exc
        self.say("models_ok")
        for item in list(data.get("data") or [])[:10]:
            print(f" - {item.get('id') if isinstance(item, dict) else item}")

    def add_profile_interactive(self, name: str) -> None:
        profiles = self.profiles()
        if name in profiles:
            raise SystemExit(tr("profile_exists", name))
        profile_type = input("Profile type (api/subscription): ").strip().lower()
        if profile_type == "api":
            profile = Profile(name, "api", input("Base URL: ").strip(), input("Default model: ").strip(), input("Wire API [responses]: ").strip() or "responses")
        elif profile_type == "subscription":
            profile = Profile(name, "subscription")
        else:
            raise SystemExit("Profile type must be api or subscription.")
        profile.validate()
        profiles[name] = profile
        save_profiles(self.profiles_path, profiles)
        if profile.is_api:
            key = getpass.getpass(tr("paste_key", name))
            if key:
                self.credentials.set(name, key)
        self.say("profile_saved", name)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Switch Codex Desktop provider profiles.")
    parser.add_argument("command", nargs="?")
    parser.add_argument("argument", nargs="?")
    parser.add_argument("profile_name", nargs="?")
    parser.add_argument("--api-key")
    parser.add_argument("--model")
    parser.add_argument("--base-url")
    parser.add_argument("--codex-home", default=os.path.expanduser("~/.codex"))
    parser.add_argument("--profile-home")
    parser.add_argument("--chat-fallback", action="store_true")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    args = parser.parse_args(argv)
    args.mode = args.command
    return args


def run_command(args: argparse.Namespace, switcher: Switcher) -> None:
    command, argument = args.command or "status", args.argument
    aliases = {"apimaster": ("use", "apimaster"), "official": ("use", "official"), "test": ("profile", "test"), "save-official": ("profile", "save-official")}
    if command in aliases:
        target = aliases[command]
        switcher.warn(f"Deprecated command '{command}'. Use 'cps {target[0]} {target[1]}' instead.")
        command, argument = target
        if command == "profile" and argument == "test" and not args.profile_name:
            args.profile_name = switcher.current_profile_name()
        if command == "profile" and argument == "save-official" and not args.profile_name:
            args.profile_name = "official"
    if command == "use":
        if not argument:
            raise SystemExit("Usage: cps use <profile>")
        switcher.use_profile(argument, args.api_key, args.model, args.base_url, args.chat_fallback)
    elif command == "status":
        switcher.status()
    elif command == "repair-history":
        switcher.repair_desktop_history_hints()
    elif command == "profile":
        name = args.profile_name
        if argument == "list":
            for profile in switcher.profiles().values():
                suffix = f" {profile.base_url}" if profile.is_api else ""
                print(f"{profile.name}\t{profile.type}\t{profile.default_model or ''}{suffix}")
        elif argument == "add":
            if not name:
                raise SystemExit("Usage: cps profile add <name>")
            switcher.add_profile_interactive(name)
        elif argument == "remove":
            if not name:
                raise SystemExit("Usage: cps profile remove <name>")
            profiles = switcher.profiles()
            if name not in profiles:
                raise SystemExit(tr("profile_missing", name))
            del profiles[name]
            save_profiles(switcher.profiles_path, profiles)
            if switcher.active_path.exists() and switcher.active_path.read_text(encoding="utf-8").strip() == name:
                switcher.active_path.unlink()
            switcher.say("profile_removed", name)
        elif argument == "test":
            if not name:
                raise SystemExit("Usage: cps profile test <name>")
            switcher.test_profile(name, args.api_key)
        elif argument == "save-official":
            switcher._save_subscription_snapshot("official")
            print("Saved current Codex config/auth as official profile.")
        else:
            raise SystemExit("Usage: cps profile {list|add|remove|test}")
    else:
        raise SystemExit(f"Unknown command: {command}")


def interactive_menu(switcher: Switcher) -> None:
    while True:
        print("\nCodex Provider Switcher\n1. Switch provider\n2. Show status\n3. Test provider connectivity\n4. Manage profiles\n5. Repair Desktop history list\n0. Exit\n")
        try:
            choice = input("Choose: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        try:
            if choice == "0":
                return
            if choice == "1":
                names = list(switcher.profiles())
                for index, name in enumerate(names, 1):
                    print(f"{index}. {name}")
                switcher.use_profile(names[int(input("Choose profile: ").strip()) - 1])
            elif choice == "2":
                switcher.status()
            elif choice == "3":
                names = [name for name, profile in switcher.profiles().items() if profile.is_api]
                for index, name in enumerate(names, 1):
                    print(f"{index}. {name}")
                if names:
                    switcher.test_profile(names[int(input("Choose profile: ").strip()) - 1])
            elif choice == "4":
                for name in switcher.profiles():
                    print(name)
                print("Use 'cps profile add/remove' for changes.")
            elif choice == "5":
                switcher.repair_desktop_history_hints()
            else:
                switcher.warn("invalid_choice")
        except (ValueError, IndexError, OSError, SystemExit) as exc:
            print(f"ERROR: {exc}", file=sys.stderr)


def main() -> None:
    args = parse_args()
    switcher = Switcher(Path(args.codex_home), Path(args.profile_home) if args.profile_home else None)
    switcher.ensure_state_dir()
    if args.command is None and len(sys.argv) == 1 and sys.stdin.isatty():
        interactive_menu(switcher)
    else:
        run_command(args, switcher)


if __name__ == "__main__":
    main()
