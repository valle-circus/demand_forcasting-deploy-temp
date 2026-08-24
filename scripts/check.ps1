param(
    [string]$PythonExecutable = "python"
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$env:PYTHONPATH = Join-Path $projectRoot "src"

& $PythonExecutable -m compileall -q (Join-Path $projectRoot "src") (Join-Path $projectRoot "tests")
& $PythonExecutable -m unittest discover -s (Join-Path $projectRoot "tests") -v
