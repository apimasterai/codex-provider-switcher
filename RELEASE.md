# Release checklist

1. Update the version in `pyproject.toml`, `codex_provider_switcher.py`, and
   the default tag in `install.sh`. Update the versioned URLs in both READMEs.
2. Update `CHANGELOG.md`, run the test suite, and review the generated diff.
3. Build source and wheel distributions:

   ```bash
   python -m build
   ```

4. Validate the distributions:

   ```bash
   twine check dist/*
   ```

5. Configure a PyPI project and trusted publisher for the repository and workflow
   `publish.yml`. This requires a PyPI account and a one-time OIDC trusted
   publisher configuration; no API token belongs in GitHub Actions.
6. Create and push a release tag:

   ```bash
   git tag v0.3.1
   git push origin v0.3.1
   ```

7. The tag workflow runs the tests, downloads the tagged standalone program to
   smoke-test both commands, then builds and uploads the distributions to PyPI.
   Confirm the release page and install it in a clean environment:

   ```bash
   pipx install codex-provider-switcher
   cps --version
   ```

8. Update the URL and SHA256 in `RomaCredit/homebrew-codex` for the new tag.
   The SHA256 must be calculated from the downloaded archive, not the git commit.

The maintainer must complete the PyPI account, project ownership, trusted
publisher, and release-tag steps manually.
