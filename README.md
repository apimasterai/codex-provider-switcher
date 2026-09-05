# Codex Provider Switcher: keep Codex Desktop history visible

[中文文档](README.zh-CN.md)

When Codex Desktop hits a usage limit and you switch to an OpenAI-compatible
endpoint, the project sidebar can become empty or show the wrong conversations.
This tool switches provider profiles **and repairs the session history metadata**
that Codex Desktop uses to index those conversations. It addresses the common
cases described as “codex desktop history disappeared”, “codex conversations
missing after switching provider”, and “codex usage limit reached”.

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
curl -fsSL https://raw.githubusercontent.com/RomaCredit/codex-provider-switcher/v0.3.1/install.sh | sh
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
curl -fsSL https://raw.githubusercontent.com/RomaCredit/codex-provider-switcher/v0.3.1/install.sh | CODEX_SWITCHER_VERSION=v0.3.0 sh
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
irm https://raw.githubusercontent.com/RomaCredit/codex-provider-switcher/main/install.ps1 | iex
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

## Troubleshooting

If you see “codex desktop sidebar empty”, “codex model_provider mismatch”, or
“codex conversations missing after switching provider”, quit Codex Desktop and
run:

```bash
cps repair-history
```

If the provider test fails, verify the profile `base_url` and credentials:

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

## License

MIT. See [LICENSE](LICENSE).
