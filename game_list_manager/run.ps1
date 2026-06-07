$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $scriptDir
$venvPath = Join-Path $projectRoot ".venv-py312"
$activateScript = Join-Path $venvPath "Scripts\\Activate.ps1"
$mainScript = Join-Path $scriptDir "main.py"

if (-not (Test-Path $activateScript)) {
    throw "Virtual environment not found. Run .\\setup.bat first."
}

. $activateScript
python $mainScript
