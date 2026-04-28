# Installer for irm https://agsekit.org/install.ps1 | iex

$ErrorActionPreference = "Stop"

$InstallRoot = Join-Path $env:USERPROFILE ".local\share\agsekit"
$VenvPath = Join-Path $InstallRoot "venv"
$BinDir = Join-Path $env:USERPROFILE ".local\bin"
$WrapperPath = Join-Path $BinDir "agsekit.cmd"
$Package = if ($env:AGSEKIT_PACKAGE) { $env:AGSEKIT_PACKAGE } else { "agsekit" }
$PythonDownloadsPageUrl = "https://www.python.org/downloads/windows/"

function Die {
    param([string]$Message)
    Write-Error $Message
    exit 1
}

function Read-InstallerConfirmation {
    param(
        [string]$Prompt,
        [bool]$DefaultYes = $true
    )

    while ($true) {
        $suffix = if ($DefaultYes) { "[Y/n]" } else { "[y/N]" }
        $answer = Read-Host "$Prompt $suffix"

        if ([string]::IsNullOrWhiteSpace($answer)) {
            return $DefaultYes
        }
        if ($answer -match '^(?i:y(?:es)?)$') {
            return $true
        }
        if ($answer -match '^(?i:n(?:o)?)$') {
            return $false
        }

        Write-Host "Please answer y or n."
    }
}

function Find-SupportedPython {
    $candidates = @()
    $unsupportedVersion = $null

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
                if (-not $unsupportedVersion) {
                    $unsupportedVersion = $versionText
                }
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
            if (-not $unsupportedVersion) {
                $unsupportedVersion = $versionText
            }
        }
    }

    if ($unsupportedVersion) {
        Die "Python 3.9+ is required; found Python $unsupportedVersion. Install Python 3.9 or newer first, then rerun this installer."
    }

    return $null
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

function Get-PythonInstallerSuffix {
    $arch = $env:PROCESSOR_ARCHITEW6432
    if ([string]::IsNullOrWhiteSpace($arch)) {
        $arch = $env:PROCESSOR_ARCHITECTURE
    }
    $normalized = if ($arch) { $arch.ToUpperInvariant() } else { "" }

    if ($normalized -match "ARM64") {
        return "arm64.exe"
    }
    if ([Environment]::Is64BitOperatingSystem) {
        return "amd64.exe"
    }
    return "exe"
}

function Install-Python-WithWinget {
    $winget = Get-Command winget -ErrorAction SilentlyContinue
    if (-not $winget) {
        return $false
    }

    Write-Host "Installing Python 3.9+ with winget..."
    & $winget.Source install --id Python.Python.3 --exact --source winget --scope user --accept-package-agreements --accept-source-agreements
    if ($LASTEXITCODE -ne 0) {
        Die "winget failed to install Python."
    }

    $env:Path = Get-RefreshedPath
    return $true
}

function Get-LatestPythonInstallerUrl {
    $installerSuffix = Get-PythonInstallerSuffix
    $response = Invoke-WebRequest -Uri $PythonDownloadsPageUrl -UseBasicParsing

    if ($installerSuffix -eq "exe") {
        $pattern = '(?:https://www\.python\.org)?/ftp/python/(?<version>\d+\.\d+\.\d+)/python-(?<fileversion>\d+\.\d+\.\d+)\.exe'
    } else {
        $escapedSuffix = [regex]::Escape($installerSuffix)
        $pattern = "(?:https://www\.python\.org)?/ftp/python/(?<version>\d+\.\d+\.\d+)/python-(?<fileversion>\d+\.\d+\.\d+)-$escapedSuffix"
    }

    $matches = [regex]::Matches($response.Content, $pattern)
    $candidates = foreach ($match in $matches) {
        $versionText = $match.Groups["version"].Value
        $fileVersionText = $match.Groups["fileversion"].Value
        if ($versionText -ne $fileVersionText) {
            continue
        }

        $url = $match.Value
        if ($url -notmatch '^https://') {
            $url = "https://www.python.org$url"
        }

        [pscustomobject]@{
            Version = [version]$versionText
            Url = $url
        }
    }

    $latest = $candidates | Sort-Object Version -Descending | Select-Object -First 1
    if (-not $latest) {
        Die "Could not determine the latest official Python installer from $PythonDownloadsPageUrl."
    }

    return $latest.Url
}

function Install-Python-FromOfficialSite {
    $installerUrl = Get-LatestPythonInstallerUrl
    $tempDir = Join-Path ([System.IO.Path]::GetTempPath()) ("agsekit-python-" + [guid]::NewGuid().ToString("N"))
    $installerPath = Join-Path $tempDir (Split-Path $installerUrl -Leaf)

    New-Item -ItemType Directory -Force -Path $tempDir | Out-Null

    try {
        Write-Host "Downloading Python installer from $installerUrl"
        Invoke-WebRequest -Uri $installerUrl -OutFile $installerPath -UseBasicParsing

        Write-Host "Running Python installer..."
        $process = Start-Process -FilePath $installerPath -ArgumentList @(
            "/quiet",
            "InstallAllUsers=0",
            "PrependPath=1",
            "Include_pip=1",
            "Include_launcher=1",
            "SimpleInstall=1"
        ) -Wait -PassThru

        if ($process.ExitCode -notin @(0, 3010)) {
            Die "The official Python installer failed with exit code $($process.ExitCode)."
        }
    }
    finally {
        Remove-Item -Path $tempDir -Recurse -Force -ErrorAction SilentlyContinue
    }

    $env:Path = Get-RefreshedPath
}

function Ensure-Python {
    $pythonCommand = Find-SupportedPython
    if ($pythonCommand) {
        return $pythonCommand
    }

    Write-Host "Python 3.9+ is required."
    if (-not (Read-InstallerConfirmation "Python 3.9+ was not found. Install it automatically now?" $true)) {
        Die "Python 3.9+ is required. Install Python first, then rerun this installer."
    }

    if (-not (Install-Python-WithWinget)) {
        Install-Python-FromOfficialSite
    }

    $pythonCommand = Find-SupportedPython
    if (-not $pythonCommand) {
        Die "Automatic Python installation completed, but Python 3.9+ is still not available in PATH. Open a new PowerShell session and rerun this installer."
    }

    return $pythonCommand
}

$PythonCommand = Ensure-Python

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
