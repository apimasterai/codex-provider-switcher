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
   git tag v0.3.3
   git push origin v0.3.3
   ```

7. The tag workflow runs the tests, downloads the tagged standalone program to
   smoke-test both commands, then builds and uploads the distributions to PyPI.
   Confirm the release page and install it in a clean environment:

   ```bash
   pipx install codex-provider-switcher
   cps --version
   ```

8. Update the URL and SHA256 in `apimasterai/homebrew-codex` for the new tag.
   The SHA256 must be calculated from the downloaded archive, not the git commit.

9. Create a GitHub Release with installation commands, changes, compatibility
   limits, and the successful CI run.

The PyPI owner must authorize owner `apimasterai`, repository
`codex-provider-switcher`, workflow `publish.yml`, environment `pypi`.
Publishing is gated by the Windows/macOS/Linux Python 3.10/3.13 matrix.
Manual dispatch is supported on version tags. For deliberate manual upload,
use `python -m twine upload dist/*` from a clean output directory with a securely
supplied scoped token. Never commit or print tokens.
