# Codex Provider Switcher: keep Codex Desktop history visible

[![Tests](https://github.com/RomaCredit/codex-provider-switcher/actions/workflows/test.yml/badge.svg)](https://github.com/RomaCredit/codex-provider-switcher/actions/workflows/test.yml)
[![PyPI](https://img.shields.io/pypi/v/codex-provider-switcher)](https://pypi.org/project/codex-provider-switcher/)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green)](https://github.com/RomaCredit/codex-provider-switcher/blob/main/LICENSE)

[中文文档](https://github.com/RomaCredit/codex-provider-switcher/blob/main/README.zh-CN.md) |
[Releases](https://github.com/RomaCredit/codex-provider-switcher/releases) |
[Changelog](https://github.com/RomaCredit/codex-provider-switcher/blob/main/CHANGELOG.md)

When Codex Desktop hits a usage limit and you switch to an OpenAI-compatible
endpoint, the project sidebar can become empty or show the wrong conversations.
This tool switches provider profiles **and repairs the session history metadata**
that Codex Desktop uses to index those conversations.

## Is this for you?

Use `cps` for local provider configuration and Codex Desktop history metadata
that no longer matches the selected provider. It cannot recover deleted
transcripts, migrate ChatGPT cloud conversations, increase a subscription
quota, or repair another computer remotely. A third-party API has its own
billing and must support the protocol and model used by your Codex version.
This is an independent community tool, not an OpenAI product.

## The problem

Changing `config.toml` alone does not update the provider value stored in
`state_5.sqlite` and the first `session_meta` line in
`sessions/rollout-*.jsonl`. That `model_provider` mismatch can make the
Codex Desktop sidebar empty even though the conversation files still exist.

## What this does

The tool backs up Codex state, switches a profile, synchronizes provider values
in both stores, repairs project workspace hints, and normalizes Windows
`\\?\` paths. `repair-history` runs the metadata repair without changing the
active profile.

## Install

Requires **Python 3.10 or newer**. Use the same OS user that runs Codex so the
tool accesses the correct configuration and history.

### macOS / Linux standalone installer

This installs the released Python source from GitHub without using pip or
modifying system Python packages. It works on Ubuntu/Debian with PEP 668 enabled;
it still requires an existing Python 3.10+ installation and `curl` or `wget`.

```bash
curl -fsSL https://raw.githubusercontent.com/RomaCredit/codex-provider-switcher/v0.3.3/install.sh | sh
cps --version
```

Both `cps` and `codex-provider-switcher` are installed. No manual symlink is needed.
Rerun the command to reinstall that version; use a newer release's installer URL
to upgrade. Installation does not switch providers or touch Codex data.

| Run as | Commands | Program |
| --- | --- | --- |
| Regular user | `~/.local/bin/` | `~/.local/share/codex-provider-switcher/` |
| root | `/usr/local/bin/` | `/usr/local/lib/codex-provider-switcher/` |

If `cps` is not found after a user installation:

```bash
export PATH="$HOME/.local/bin:$PATH"
cps --version
```

Add that PATH setting to your shell configuration for future sessions. The
installer prints the appropriate setting but does not edit your shell files.

Set `CODEX_SWITCHER_BIN_DIR` and `CODEX_SWITCHER_DATA_DIR` to customize the
directories. For a different version, set the variable on **`sh`**, not on `curl`:

```bash
curl -fsSL https://raw.githubusercontent.com/RomaCredit/codex-provider-switcher/v0.3.3/install.sh | CODEX_SWITCHER_VERSION=v0.3.0 sh
```

### PyPI

Direct pip installation is supported in a virtual environment or another
pip-managed Python environment:

```bash
python -m pip install --upgrade codex-provider-switcher
```

If Ubuntu/Debian reports `externally-managed-environment`, use the standalone
installer above, pipx, or a virtual environment. `pip install --user` may also
be blocked by PEP 668; do not disable this protection with `--break-system-packages`.

### Homebrew

```bash
brew tap RomaCredit/codex
brew install codex-provider-switcher
```

If Homebrew requires tap trust, inspect the formula and authorize just that
formula with `brew trust --formula RomaCredit/codex/codex-provider-switcher`.

### pipx

With pipx installed:

```bash
pipx install codex-provider-switcher
```

### From source

```bash
git clone https://github.com/RomaCredit/codex-provider-switcher.git
cd codex-provider-switcher
python3 -m venv .venv
.venv/bin/python -m pip install .
.venv/bin/cps --version
```

### Windows PowerShell

```powershell
irm https://raw.githubusercontent.com/RomaCredit/codex-provider-switcher/v0.3.3/install.ps1 | iex
```

Linux server installations operate on that server's local Codex data only.
They do not repair the Desktop sidebar on a separate Windows/macOS computer.

## Quick start

Fully quit Codex Desktop before changing its files:

```bash
cps profile list
cps status
cps use openrouter
cps use official
cps repair-history
```

`codex-provider-switcher` remains an equivalent executable name.

## Profiles

The first run creates `~/.codex-provider-switcher/profiles.toml` (Windows:
`%USERPROFILE%\.codex-provider-switcher\profiles.toml`) with three ordinary
profiles:

```toml
[profiles.official]
type = "subscription"

[profiles.apimaster]
type = "api"
base_url = "https://apimaster.ai/v1"
default_model = "gpt-5.6-sol"

[profiles.openrouter]
type = "api"
base_url = "https://openrouter.ai/api/v1"
default_model = "anthropic/claude-sonnet-4.6"
```

Built-in profiles can be edited, removed, or replaced like any custom profile:

```bash
cps profile add local
cps profile remove local
cps profile test openrouter
```

`profile add` prompts for the type, base URL, model, and API key. Keys are not
stored in `profiles.toml`: macOS uses Keychain when available, Windows uses the
Credential Manager integration when available, and the fallback
`credentials.toml` is restricted to the current user (`0600` on POSIX).
Any OpenAI-compatible endpoint can be represented by an API profile; OpenRouter
is included as a neutral example, alongside the APIMaster preset.

## How it works

Before a switch, timestamped backups are written below the Codex
`provider-switcher` directory. The SQLite `threads.model_provider` values and
the JSONL `session_meta.payload.model_provider` values are changed to the
active API profile name, or to Codex's `openai` value for a subscription
profile. Workspace hints are rebuilt from session metadata and extended Windows
paths are normalized.

The tool never rewrites conversation content. It only updates the index and
metadata fields needed by Codex Desktop.

| Local store | Relevant fields | Purpose |
| --- | --- | --- |
| `config.toml` | `model_provider`, `model`, `[model_providers.<name>]` | Select the endpoint, model, and wire protocol |
| `state_5.sqlite` | `threads.model_provider`, `threads.cwd` | Update the local thread index |
| `sessions/**/rollout-*.jsonl` | First `session_meta` record's `payload.model_provider` and `payload.cwd` | Align session metadata with the index |
| `.codex-global-state.json` | `thread-workspace-root-hints` | Rebuild Desktop project hints |

An API profile uses its profile name as the provider ID; subscription profiles
use `openai`. The JSONL change is limited to the metadata record, not message
content. Windows extended paths such as `\\?\D:\work\app` are normalized to
`D:\work\app`. These are implementation details of the local formats handled
by this release, not a stable upstream storage API.

The default profile wire protocol is `responses`; `wire_api = "chat"` can be
configured where the client supports it. An "OpenAI-compatible" label or a
successful `/models` response alone does not establish Responses API,
streaming, tool-use, or model compatibility.

## Troubleshooting

### Codex Desktop history disappeared after switching provider

If conversation files still exist, a `model_provider` mismatch between the
configuration, thread index, and session metadata is one possible cause.
Quit Codex Desktop, retain the original data, and run:

```bash
cps repair-history
```

### Codex conversations missing after switching provider, or sidebar still empty

Confirm that you are using the same OS account and Codex home as Desktop, then
restart Desktop after the repair. Missing files, a different home directory,
and a changed client storage format require separate investigation. Do not
repeatedly repair unknown formats or post private session files in an issue.

### Codex usage limit reached: does switching add subscription quota?

No. Switching selects a separately billed API provider. It does not bypass
subscription limits, supply a free API key, or guarantee model availability.

### Why does the provider connectivity test fail?

Verify the profile `base_url`, credentials, and whether the gateway exposes a
models-list endpoint:

```bash
cps profile test openrouter
cps status
```

The connectivity check only requests the configured provider's `/v1/models`
endpoint (a base URL ending in `/v1` is expected).

## Safety

The tool creates backups before changing Codex files, never deletes
conversation content, and never logs a complete API key. It collects no
telemetry and sends no requests to third parties except the `/v1/models`
probe explicitly requested by the user.

## Compatibility

The old commands remain available with a deprecation message:

```bash
cps apimaster   # equivalent to cps use apimaster
cps official    # equivalent to cps use official
```

## Verification and related tools

The [test workflow](https://github.com/RomaCredit/codex-provider-switcher/actions/workflows/test.yml)
runs on Windows, macOS, and Linux with Python 3.10 and 3.13. Tests use temporary
fixtures; POSIX installer checks run on Linux/macOS. This does not establish
compatibility with every Desktop release or live provider. No universal
upstream-client compatibility claim is made.

For **Claude Code**, see
[Claude Provider Switcher](https://github.com/RomaCredit/claude-provider-switcher).
It uses the Anthropic Messages protocol and has different history semantics;
the tools do not share credentials or migrate each other's conversations.

[Contributing](https://github.com/RomaCredit/codex-provider-switcher/blob/main/CONTRIBUTING.md) |
[Report an issue](https://github.com/RomaCredit/codex-provider-switcher/issues/new/choose) |
[Security](https://github.com/RomaCredit/codex-provider-switcher/blob/main/SECURITY.md)

## License

MIT. See [LICENSE](https://github.com/RomaCredit/codex-provider-switcher/blob/main/LICENSE).
