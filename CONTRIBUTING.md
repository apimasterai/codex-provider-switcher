# Contributing

Use Python 3.10+ on Windows, macOS, or Linux. Runtime dependencies must remain
standard-library only. Build/test tools belong in a virtual environment.

```bash
python -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/python -m unittest discover -s tests -v
```

On Windows use `.venv\Scripts\python.exe`. CI tests Python 3.10 and 3.13 on
all three operating systems.

## Safe tests

Use temporary directories, synthetic SQLite/JSONL fixtures, dummy credentials,
and mocked or loopback HTTP responses. Do not switch your live provider or use
real session files merely to run tests. Never commit keys, auth files, databases,
backups, or private prompts. Never make billable provider requests in CI.

For history changes, cover both provider directions, Windows path normalization,
backups, and preservation of message content. Report which storage format and
client version were actually reproduced; fixtures do not prove live compatibility.

## Pull requests

Explain the user-visible problem and include a regression test. Keep changes
focused, preserve unrelated settings, and update both READMEs for command or
safety changes. Keep runtime output English-only for Windows consoles.
Installation examples must target the release version, not an unpinned branch.

Use the issue forms for installation, provider compatibility, or history
problems. Follow [SECURITY.md](SECURITY.md) for vulnerabilities; never post secrets.
