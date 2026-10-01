# Changelog

## Unreleased

- Fix the Windows menu launcher requiring option `1` to be chosen twice.
- Point `model_catalog_json` at the profile's model catalog for API profiles and remove it for subscription profiles, so the model list follows the provider.
- Add an optional `model_catalog` field to profiles.
- Make `repair-history` keep going when Desktop global state or sessions are missing.
- When switching to a subscription provider, drop reasoning items that OpenAI cannot replay (no encrypted content, or ids from other providers) and strip foreign item ids, fixing `Invalid 'input[n].id'` and `Items are not persisted` errors in resumed conversations.
- Recompute paginated history lineage offsets after rewriting rollout files, fixing `cutoff byte offset is past the source rollout`, and reset the stale thread history cache.
- Fall back to a model that exists for the active provider for threads whose recorded model is unavailable, and strip the `\?\` prefix from stored rollout paths.
- Preserve rollout line endings when rewriting session metadata.

## 0.3.2

- Clarify local history repair, protocol requirements, billing, and tested scope.
- Add bilingual navigation, troubleshooting answers, package metadata, and
  links to releases and the separate Claude Code tool.
- Add contribution guidance, issue forms, citation metadata, and release checks.
- Pin the Windows installer's source archive and report package install failures.
- Gate PyPI publishing on the three-OS/two-Python matrix.
- Provider selection, history synchronization, and credential behavior are unchanged.

## 0.3.1

- Make the standalone macOS/Linux installer provide both `cps` and
  `codex-provider-switcher` commands.
- Validate that the installer is running with Python 3.10 or newer.
- Allow reproducible installer overrides with `CODEX_SWITCHER_VERSION`.
- Validate downloaded source syntax and version before replacing the installed program.
- Handle custom paths safely, clean up temporary files, and reject directory conflicts.
- Add offline installer integration tests and run tests before publishing to PyPI.
- Document standalone installation without system pip, including Ubuntu PEP 668,
  user/root installation paths, and the now-published Homebrew tap.

## 0.3.0

- Replace hard-coded provider branches with user-editable profiles in `profiles.toml`.
- Add `cps use`, `cps status`, `cps profile`, and `cps repair-history`.
- Add built-in official, APIMaster, and OpenRouter profiles with the same configuration-driven behavior as custom profiles.
- Store API keys in macOS Keychain when available and otherwise in a local credentials file with restricted permissions.
- Keep `apimaster` and `official` as deprecated compatibility aliases.
- Prepare the package for PyPI publishing and trusted publishing from version tags.

## 0.2.4

- Pin standalone installation downloads to a version tag instead of the cache-prone `main` branch.
- Document a versioned one-line installer URL for reproducible installation.

## 0.2.3

- Install a shell launcher that explicitly invokes Python instead of relying on the downloaded file's shebang.
- Store the standalone Python program separately under the system or user data directory.

## 0.2.2

- Remove the UTF-8 BOM that prevented Linux from recognizing the Python shebang.
- Make the standalone installer strip a BOM defensively before installing.

## 0.2.1

- Make the macOS/Linux one-line installer work without pip or pipx.
- Install the standalone command into `/usr/local/bin` for root or `~/.local/bin` for regular users.

## 0.2.0

- Add Python package metadata and the global `codex-provider-switcher` command.
- Open an interactive menu when the installed command is run without arguments.
- Add `pipx`, `pip`, curl, and PowerShell installation paths.
- Add cross-platform GitHub Actions tests.

## 0.1.0

- Add APIMaster and official subscription switching.
- Add one-click Windows batch menu.
- Add Codex Desktop history synchronization across provider modes.
- Repair project sidebar hints, thread `cwd` paths, SQLite provider values, and session metadata provider values.
- Add automatic backups before state changes.
- Add Chinese documentation while keeping runtime output English-only for encoding safety.
- Add cross-platform Python CLI and macOS `.command` menus.
