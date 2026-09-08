[CmdletBinding()]
param(
    [string]$Python = "python",
    [string]$Wheel = "",
    [switch]$NoDeps
)

$ErrorActionPreference = "Stop"
$root = $env:AGENT_WORKFLOW_SOURCE_ROOT
if (-not $root) { $root = $PSScriptRoot }
$root = (Resolve-Path $root).Path

& $Python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 'agent-workflow requires Python 3.11+')"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$target = if ($Wheel) { (Resolve-Path $Wheel).Path } else { $root }
if ($Wheel -and -not (Test-Path -LiteralPath $target -PathType Leaf)) {
    throw "wheel not found: $Wheel"
}
$pipArgs = @("-m", "pip", "install", "--upgrade")
if ($NoDeps) { $pipArgs += "--no-deps" }
if ($Wheel) { $pipArgs += @("--force-reinstall", $target) } else { $pipArgs += @("--editable", $target) }
& $Python @pipArgs
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$configHome = if ($env:APPDATA) { $env:APPDATA } else { Join-Path $HOME ".config" }
$configDir = Join-Path $configHome "agent-workflow"
$configFile = Join-Path $configDir "config.toml"
New-Item -ItemType Directory -Force -Path $configDir | Out-Null
if (-not (Test-Path -LiteralPath $configFile)) {
    Copy-Item (Join-Path $root "config/agent-workflow.example.toml") $configFile
}

$scripts = (& $Python -c "import sysconfig; print(sysconfig.get_path('scripts'))").Trim()
Write-Output "installed launcher: $(Join-Path $scripts 'agent-workflow.exe')"
Write-Output "config: $configFile"
Write-Output "MCP registration, skills, and hooks are intentionally not changed by the Windows installer."
