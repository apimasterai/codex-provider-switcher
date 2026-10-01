$ErrorActionPreference = "Stop"
$Repository = "https://github.com/RomaCredit/codex-provider-switcher/archive/refs/tags/v0.3.3.zip"

if (Get-Command pipx -ErrorAction SilentlyContinue) {
    pipx install --force $Repository
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
    py -m pip install --user --upgrade $Repository
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    python -m pip install --user --upgrade $Repository
} else {
    throw "Python 3 is required. Install Python and run this installer again."
}

if ($LASTEXITCODE -ne 0) {
    throw "Installation failed. Review the package installer output."
}
Write-Host "Installed. Run: codex-provider-switcher"
