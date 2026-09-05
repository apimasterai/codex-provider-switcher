param(
    [Parameter(Position = 0)]
    [string] $Command = "status",
    [Parameter(Position = 1)]
    [string] $Argument,
    [string] $ApiKey,
    [string] $Model,
    [string] $BaseUrl,
    [string] $CodexHome = (Join-Path $env:USERPROFILE ".codex"),
    [string] $ProfileHome,
    [switch] $ChatFallback
)

$ErrorActionPreference = "Stop"
$scriptPath = Join-Path $PSScriptRoot "codex_provider_switcher.py"
$python = Get-Command python -ErrorAction SilentlyContinue
if (!$python) { $python = Get-Command py -ErrorAction SilentlyContinue }
if (!$python) { throw "Python 3 is required." }

$arguments = @($scriptPath, $Command)
if ($Argument) { $arguments += $Argument }
if ($ApiKey) { $arguments += @("--api-key", $ApiKey) }
if ($Model) { $arguments += @("--model", $Model) }
if ($BaseUrl) { $arguments += @("--base-url", $BaseUrl) }
if ($CodexHome) { $arguments += @("--codex-home", $CodexHome) }
if ($ProfileHome) { $arguments += @("--profile-home", $ProfileHome) }
if ($ChatFallback) { $arguments += "--chat-fallback" }

& $python.Source @arguments
exit $LASTEXITCODE
