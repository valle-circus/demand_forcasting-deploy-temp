param(
    [string]$InputDirectory = (Join-Path $env:USERPROFILE "Downloads"),
    [string]$OutputDirectory,
    [string]$LocationId = "REWE_CENTRAL_PREP",
    [string]$AsOfDate = (Get-Date -Format "yyyy-MM-dd"),
    [string]$ItemMap,
    [string]$PythonExecutable = "python"
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$env:PYTHONPATH = Join-Path $projectRoot "src"

if (-not $OutputDirectory) {
    $OutputDirectory = Join-Path $projectRoot "data\private\transgourmet"
}

$arguments = @(
    "-m", "supply_planning", "transgourmet-import",
    "--input-dir", $InputDirectory,
    "--output-dir", $OutputDirectory,
    "--location-id", $LocationId,
    "--as-of-date", $AsOfDate
)

if ($ItemMap) {
    $arguments += @("--item-map", $ItemMap)
} else {
    $arguments += "--allow-supplier-item-ids"
}

& $PythonExecutable @arguments
exit $LASTEXITCODE
