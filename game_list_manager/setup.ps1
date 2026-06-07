$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $scriptDir
$venvPath = Join-Path $projectRoot ".venv-py312"
$activateScript = Join-Path $venvPath "Scripts\\Activate.ps1"
$venvPython = Join-Path $venvPath "Scripts\\python.exe"
$requirementsPath = Join-Path $scriptDir "requirements.txt"
$pythonLauncher = Get-Command py -ErrorAction SilentlyContinue
$tempRoot = Join-Path $projectRoot ".tmp"
$localFfmpegBin = Join-Path $scriptDir "ffmpeg\\bin"
$ffmpegZipUrl = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"

if (-not (Test-Path $tempRoot)) {
    New-Item -ItemType Directory -Path $tempRoot | Out-Null
}

$env:TMP = $tempRoot
$env:TEMP = $tempRoot

function Invoke-NativeOrThrow {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Description,
        [Parameter(Mandatory = $true)]
        [scriptblock] $Command
    )

    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw "$Description failed with exit code $LASTEXITCODE."
    }
}

function Test-LocalFfmpegBundle {
    $localFfmpeg = Join-Path $localFfmpegBin "ffmpeg.exe"
    $localFfprobe = Join-Path $localFfmpegBin "ffprobe.exe"
    return (Test-Path $localFfmpeg) -and (Test-Path $localFfprobe)
}

function Install-LocalFfmpeg {
    if (Test-LocalFfmpegBundle) {
        Write-Host "Local FFmpeg bundle already present."
        return
    }

    Write-Host "Downloading FFmpeg essentials..."

    $downloadDir = Join-Path $tempRoot "ffmpeg-download"
    $archivePath = Join-Path $downloadDir "ffmpeg-release-essentials.zip"
    $extractDir = Join-Path $downloadDir "extract"

    if (Test-Path $downloadDir) {
        Remove-Item -LiteralPath $downloadDir -Recurse -Force
    }

    New-Item -ItemType Directory -Path $downloadDir | Out-Null
    Invoke-WebRequest -Uri $ffmpegZipUrl -OutFile $archivePath

    Write-Host "Extracting FFmpeg essentials..."
    Expand-Archive -LiteralPath $archivePath -DestinationPath $extractDir -Force

    $binDir = Get-ChildItem -Path $extractDir -Recurse -Directory |
        Where-Object {
            (Test-Path (Join-Path $_.FullName "ffmpeg.exe")) -and
            (Test-Path (Join-Path $_.FullName "ffprobe.exe"))
        } |
        Select-Object -First 1

    if (-not $binDir) {
        throw "Downloaded FFmpeg archive does not contain a complete bin directory."
    }

    if (Test-Path $localFfmpegBin) {
        Remove-Item -LiteralPath $localFfmpegBin -Recurse -Force
    }

    New-Item -ItemType Directory -Path $localFfmpegBin | Out-Null
    Copy-Item -Path (Join-Path $binDir.FullName "*") -Destination $localFfmpegBin -Recurse -Force

    if (-not (Test-LocalFfmpegBundle)) {
        throw "Local FFmpeg installation is incomplete after extraction."
    }

    Write-Host "Local FFmpeg installed to $localFfmpegBin"
}

if (-not $pythonLauncher) {
    throw "Python launcher 'py' not found. Install Python 3.12 and try again."
}

$python312 = & py -3.12 -c "import sys; print(sys.executable)" 2>$null
if (-not $python312) {
    throw "Python 3.12 not found. Install Python 3.12 and rerun setup.ps1."
}

if ((Test-Path $venvPath) -and -not (Test-Path $activateScript)) {
    Write-Host "Removing incomplete virtual environment..."
    Remove-Item -LiteralPath $venvPath -Recurse -Force
}

if (-not (Test-Path $venvPath)) {
    Write-Host "Creating virtual environment with Python 3.12..."
    Invoke-NativeOrThrow "Virtual environment creation" { py -3.12 -m venv --without-pip $venvPath }
}

Write-Host "Upgrading pip..."
Invoke-NativeOrThrow "pip bootstrap" { py -3.12 -m pip --python $venvPython install --upgrade pip }

Write-Host "Installing Python dependencies..."
Invoke-NativeOrThrow "Dependency installation" { py -3.12 -m pip --python $venvPython install -r $requirementsPath }

Install-LocalFfmpeg

Write-Host "Validating imports..."
Invoke-NativeOrThrow "Dependency validation" { & $venvPython -c "import tkinter, PIL, googletrans, vlc; print('Python dependencies OK')" }

Write-Host ""
Write-Host "Setup complete."
Write-Host "Run the app with: .\\start.bat"
Write-Host ""
Write-Host "Optional system tool:"
Write-Host "- VLC media player: needed for in-app video playback"
