# Installer for irm https://agsekit.org/install.ps1 | iex

$ErrorActionPreference = "Stop"

$InstallRoot = Join-Path $env:USERPROFILE ".local\share\agsekit"
$VenvPath = Join-Path $InstallRoot "venv"
$BinDir = Join-Path $env:USERPROFILE ".local\bin"
$WrapperPath = Join-Path $BinDir "agsekit.cmd"
$Package = if ($env:AGSEKIT_PACKAGE) { $env:AGSEKIT_PACKAGE } else { "agsekit" }
$PythonDownloadUrl = "https://www.python.org/downloads/windows/"

function Die {
    param([string]$Message)
    Write-Error $Message
    exit 1
}

function Find-Python {
    $candidates = @()

    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($python) {
        $candidates += @($python.Source)
    }

    $pyLauncher = Get-Command py -ErrorAction SilentlyContinue
    if ($pyLauncher) {
        $candidates += @("py -3")
    }

    foreach ($candidate in $candidates) {
        if ($candidate -eq "py -3") {
            $versionText = & py -3 -c "import sys; print('%d.%d.%d' % sys.version_info[:3])" 2>$null
            $isSupported = $LASTEXITCODE -eq 0
            if ($isSupported) {
                & py -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)" 2>$null
                $isSupported = $LASTEXITCODE -eq 0
            }
            if ($isSupported) {
                return "py -3"
            }
            if ($versionText) {
                Write-Host "Found Python $versionText, but agsekit requires Python 3.9+."
            }
            continue
        }

        $versionText = & $candidate -c "import sys; print('%d.%d.%d' % sys.version_info[:3])" 2>$null
        $isSupported = $LASTEXITCODE -eq 0
        if ($isSupported) {
            & $candidate -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)" 2>$null
            $isSupported = $LASTEXITCODE -eq 0
        }
        if ($isSupported) {
            return $candidate
        }
        if ($versionText) {
            Write-Host "Found Python $versionText, but agsekit requires Python 3.9+."
        }
    }

    Write-Host "Python 3.9+ is required. Install Python first, then rerun this installer."
    $answer = Read-Host "Open the Python for Windows download page now? [Y/n]"
    if ($answer -eq "" -or $answer -match "^[Yy]") {
        Start-Process $PythonDownloadUrl
    }
    exit 1
}

function Invoke-Python {
    param(
        [string]$PythonCommand,
        [string[]]$Arguments
    )

    if ($PythonCommand -eq "py -3") {
        & py -3 @Arguments
    } else {
        & $PythonCommand @Arguments
    }
}

function Ensure-UserPath {
    param([string]$PathEntry)

    $currentPath = [Environment]::GetEnvironmentVariable("Path", "User")
    $parts = @()
    if ($currentPath) {
        $parts = $currentPath -split ";"
    }

    foreach ($part in $parts) {
        if ($part -ieq $PathEntry) {
            return $false
        }
    }

    if ([string]::IsNullOrEmpty($currentPath)) {
        $newPath = $PathEntry
    } else {
        $newPath = $currentPath.TrimEnd(";") + ";" + $PathEntry
    }
    [Environment]::SetEnvironmentVariable("Path", $newPath, "User")
    return $true
}

function Get-RefreshedPath {
    $machinePath = [Environment]::GetEnvironmentVariable("Path", "Machine")
    $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
    $parts = @()

    if (-not [string]::IsNullOrEmpty($machinePath)) {
        $parts += $machinePath.TrimEnd(";")
    }
    if (-not [string]::IsNullOrEmpty($userPath)) {
        $parts += $userPath.TrimEnd(";")
    }

    return ($parts -join ";")
}

function Get-PathRefreshCommand {
    return '$env:Path = "$([Environment]::GetEnvironmentVariable(''Path'',''Machine''));$([Environment]::GetEnvironmentVariable(''Path'',''User''))"'
}

$PythonCommand = Find-Python

New-Item -ItemType Directory -Force -Path $InstallRoot | Out-Null
New-Item -ItemType Directory -Force -Path $BinDir | Out-Null

Write-Host "Creating or updating venv: $VenvPath"
Invoke-Python $PythonCommand @("-m", "venv", $VenvPath)

$VenvPython = Join-Path $VenvPath "Scripts\python.exe"
$AgsekitExe = Join-Path $VenvPath "Scripts\agsekit.exe"

if (-not (Test-Path $VenvPython)) {
    Die "Venv Python was not created at $VenvPython."
}

Write-Host "Installing package: $Package"
& $VenvPython -m pip install --upgrade pip
& $VenvPython -m pip install --upgrade $Package

if (-not (Test-Path $AgsekitExe)) {
    Die "agsekit executable was not found at $AgsekitExe after installation."
}

$wrapper = "@echo off`r`n`"$AgsekitExe`" %*`r`n"
Set-Content -Path $WrapperPath -Value $wrapper -Encoding ASCII

$pathChanged = Ensure-UserPath $BinDir
$env:Path = Get-RefreshedPath

Write-Host ""
Write-Host "agsekit installed."
Write-Host "Install directory: $InstallRoot"
Write-Host "Command wrapper: $WrapperPath"
if ($pathChanged) {
    Write-Host "PATH was updated for future terminal sessions."
} else {
    Write-Host "PATH already contains $BinDir"
}
Write-Host "Current PowerShell session PATH was refreshed."
Write-Host "If another terminal still does not see agsekit, run:"
Write-Host (Get-PathRefreshCommand)
