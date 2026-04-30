# Installer for `irm https://agsekit.org/install.ps1 | iex`
#
# This script is intentionally self-contained:
# - it detects an existing supported Python installation;
# - if Python is missing, it can install Python automatically;
# - it creates a dedicated virtual environment for agsekit;
# - it installs agsekit into that venv;
# - it writes lightweight wrapper scripts so `agsekit` can be started easily.
#
# The script targets interactive PowerShell usage on Windows hosts.

# Convert most runtime errors into terminating errors.
# Without this, many PowerShell commands only emit non-terminating errors and keep going,
# which would make the installer harder to reason about.
$ErrorActionPreference = "Stop"

# Main installation directories:
# - InstallRoot: agsekit-owned application data under the current user profile
# - VenvPath: dedicated Python virtual environment
# - BinDir: user-local command directory used for wrapper .cmd files
# - WrapperPath: wrapper that forwards `agsekit` invocations into the venv executable
$InstallRoot = Join-Path $env:USERPROFILE ".local\share\agsekit"
$VenvPath = Join-Path $InstallRoot "venv"
$BinDir = Join-Path $env:USERPROFILE ".local\bin"
$WrapperPath = Join-Path $BinDir "agsekit.cmd"

# Allow test runs or private distributions to override the package name with AGSEKIT_PACKAGE.
# In the normal public flow this stays `agsekit`.
$Package = if ($env:AGSEKIT_PACKAGE) { $env:AGSEKIT_PACKAGE } else { "agsekit" }

# Python is downloaded from the official Windows downloads page so the script can discover
# the latest current installer rather than hardcoding a single version forever.
$PythonDownloadsPageUrl = "https://www.python.org/downloads/windows/"

# Managed Python install location used by this installer when it has to install Python itself.
# Using a deterministic per-user location makes post-install detection much more reliable than
# waiting for PATH propagation alone.
$ManagedPythonInstallDir = Join-Path $env:LocalAppData "Programs\Python\agsekit-python"
$ManagedPythonExe = Join-Path $ManagedPythonInstallDir "python.exe"

# This is the Scripts directory belonging to the managed Python installation above.
# We also place an `agsekit.cmd` shim here because Python's own installer reliably adds this
# directory to PATH, while Windows terminal sessions may delay seeing a freshly added custom
# user path such as `~\.local\bin`.
$ManagedPythonBinDir = Join-Path $ManagedPythonInstallDir "Scripts"
$ManagedWrapperPath = Join-Path $ManagedPythonBinDir "agsekit.cmd"

function Die {
    param([string]$Message)

    # Emit a PowerShell error record so failures are visible and red in the console,
    # then stop immediately with exit code 1.
    Write-Error $Message
    exit 1
}

function Read-InstallerConfirmation {
    param(
        [string]$Prompt,
        [bool]$DefaultYes = $true
    )

    # Keep asking until the user gives a valid yes/no answer.
    while ($true) {
        # Render the prompt suffix in the conventional form:
        # - [Y/n] means Enter defaults to Yes
        # - [y/N] means Enter defaults to No
        $suffix = if ($DefaultYes) { "[Y/n]" } else { "[y/N]" }
        $answer = Read-Host "$Prompt $suffix"

        # Empty input accepts the default branch.
        if ([string]::IsNullOrWhiteSpace($answer)) {
            return $DefaultYes
        }

        # Accept `y` and `yes`, case-insensitively.
        if ($answer -match '^(?i:y(?:es)?)$') {
            return $true
        }

        # Accept `n` and `no`, case-insensitively.
        if ($answer -match '^(?i:n(?:o)?)$') {
            return $false
        }

        # Anything else is rejected and the loop continues.
        Write-Host "Please answer y or n."
    }
}

function Invoke-PythonProbe {
    param(
        [string]$PythonCommand,
        [string[]]$Arguments
    )

    # This helper runs a lightweight Python command and returns structured success/output data
    # instead of throwing directly. It is used for detection logic, where failure is expected
    # sometimes (stub launchers, broken PATH entries, unsupported versions, etc.).
    try {
        if ($PythonCommand -eq "py -3") {
            # `py -3` is special because it is not a single executable path; it is the Python
            # launcher plus arguments that request Python 3.
            $output = & py -3 @Arguments 2>$null
        } else {
            # For regular executable paths, invoke them directly.
            # stderr is suppressed because many broken/stub Python launchers print noisy messages.
            $output = & $PythonCommand @Arguments 2>$null
        }
    }
    catch {
        # If PowerShell could not launch the candidate at all, report a clean probe failure.
        return [pscustomobject]@{
            Success = $false
            Output = $null
        }
    }

    # `$LASTEXITCODE` reflects the native process exit code.
    # Success here means the child process exited with code 0.
    return [pscustomobject]@{
        Success = $LASTEXITCODE -eq 0
        Output = $output
    }
}

function Get-KnownPythonCandidates {
    # Use a strongly-typed list so we can append candidates from multiple discovery sources.
    $candidates = New-Object System.Collections.Generic.List[string]

    # Prefer our managed install location first if it already exists.
    if (Test-Path $ManagedPythonExe) {
        $candidates.Add($ManagedPythonExe)
    }

    # Ask PowerShell what `python` resolves to in the current environment.
    # This may find a real installation or a WindowsApps stub.
    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($python -and $python.Source) {
        $candidates.Add($python.Source)
    }

    # Detect the Python launcher (`py.exe`) separately.
    # It may be present even when `python.exe` is not directly on PATH.
    $pyLauncher = Get-Command py -ErrorAction SilentlyContinue
    if ($pyLauncher) {
        $candidates.Add("py -3")
    }

    # Search the canonical Python registry keys for both per-user and machine-wide installs.
    # WOW6432Node is included so 32-bit registration on 64-bit Windows is not missed.
    $registryRoots = @(
        "HKCU:\Software\Python\PythonCore",
        "HKLM:\Software\Python\PythonCore",
        "HKLM:\Software\WOW6432Node\Python\PythonCore"
    )

    foreach ($registryRoot in $registryRoots) {
        # Skip registry roots that simply do not exist on this machine.
        if (-not (Test-Path $registryRoot)) {
            continue
        }

        # Enumerate individual version keys, for example PythonCore\3.12.
        Get-ChildItem -Path $registryRoot -ErrorAction SilentlyContinue | ForEach-Object {
            $installPathKey = Join-Path $_.PSPath "InstallPath"

            # Some version keys may exist without an InstallPath subkey; ignore those.
            if (-not (Test-Path $installPathKey)) {
                return
            }

            # The default value under InstallPath normally contains the install directory.
            $installPath = (Get-ItemProperty -Path $installPathKey -ErrorAction SilentlyContinue).'(default)'
            if ([string]::IsNullOrWhiteSpace($installPath)) {
                return
            }

            $pythonExe = Join-Path $installPath "python.exe"

            # Only add registry candidates that actually point to an existing executable.
            if (Test-Path $pythonExe) {
                $candidates.Add($pythonExe)
            }
        }
    }

    # Search common install roots directly as a fallback:
    # - LocalAppData\Programs\Python for per-user installs
    # - Program Files / Program Files (x86) for machine-wide installs
    $searchRoots = @(
        (Join-Path $env:LocalAppData "Programs\Python"),
        $env:ProgramFiles,
        ${env:ProgramFiles(x86)}
    ) | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }

    foreach ($root in $searchRoots) {
        # Skip missing roots because not every Windows install has all of them populated.
        if (-not (Test-Path $root)) {
            continue
        }

        # Probe one level down for directories that directly contain python.exe.
        Get-ChildItem -Path $root -Directory -ErrorAction SilentlyContinue | ForEach-Object {
            $pythonExe = Join-Path $_.FullName "python.exe"
            if (Test-Path $pythonExe) {
                $candidates.Add($pythonExe)
            }
        }
    }

    # Remove duplicates while preserving a useful overall discovery order.
    return $candidates | Select-Object -Unique
}

function Wait-ForSupportedPython {
    param(
        [int]$TimeoutSeconds = 20
    )

    # Some installers update the filesystem/registry/PATH asynchronously from the caller's point
    # of view, so this helper retries detection for a bounded amount of time.
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    do {
        $pythonCommand = Find-SupportedPython
        if ($pythonCommand) {
            return $pythonCommand
        }

        # Sleep briefly between retries instead of busy-looping.
        Start-Sleep -Seconds 2
    } while ((Get-Date) -lt $deadline)

    # Give the caller a clean null when detection never succeeds before the timeout.
    return $null
}

function Find-SupportedPython {
    # Try every known candidate until one proves to be Python 3.9+.
    $candidates = Get-KnownPythonCandidates

    # Remember the first unsupported version we saw so we can emit a precise error
    # instead of claiming that Python is completely missing.
    $unsupportedVersion = $null

    foreach ($candidate in $candidates) {
        # First ask the candidate to print its version. This also filters out broken stubs:
        # if the command cannot run Python code, the probe will fail and we skip it.
        $versionProbe = Invoke-PythonProbe $candidate @("-c", "import sys; print('%d.%d.%d' % sys.version_info[:3])")
        $versionText = $versionProbe.Output
        if (-not $versionProbe.Success) {
            continue
        }

        # Now explicitly enforce the project's minimum supported Python version.
        $supportProbe = Invoke-PythonProbe $candidate @("-c", "import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)")
        if ($supportProbe.Success) {
            return $candidate
        }

        # If the candidate is real Python but too old, tell the user exactly what we found.
        if ($versionText) {
            Write-Host "Found Python $versionText, but agsekit requires Python 3.9+."
            if (-not $unsupportedVersion) {
                $unsupportedVersion = $versionText
            }
        }
    }

    # If at least one Python was found but it was too old, fail immediately.
    # This is different from the "Python not found" path, because auto-installing a second
    # Python on top of an explicitly discovered older Python is not the safest silent default.
    if ($unsupportedVersion) {
        Die "Python 3.9+ is required; found Python $unsupportedVersion. Install Python 3.9 or newer first, then rerun this installer."
    }

    # No usable Python was found.
    return $null
}

function Invoke-Python {
    param(
        [string]$PythonCommand,
        [string[]]$Arguments
    )

    # Normal execution helper that mirrors the `py -3` special-case used during detection.
    # This is used once we have chosen the Python command to trust.
    if ($PythonCommand -eq "py -3") {
        & py -3 @Arguments
    } else {
        & $PythonCommand @Arguments
    }
}

function Ensure-UserPath {
    param([string]$PathEntry)

    # Read the user-scoped PATH from the registry-backed environment store, not from $env:Path.
    # We want to persist the change for future sessions.
    $currentPath = [Environment]::GetEnvironmentVariable("Path", "User")
    $parts = @()
    if ($currentPath) {
        $parts = $currentPath -split ";"
    }

    foreach ($part in $parts) {
        # Case-insensitive compare because Windows paths are case-insensitive in practice.
        if ($part -ieq $PathEntry) {
            # Tell the caller nothing changed, so messages can stay accurate.
            return $false
        }
    }

    # Append the entry, preserving any existing user PATH contents.
    if ([string]::IsNullOrEmpty($currentPath)) {
        $newPath = $PathEntry
    } else {
        $newPath = $currentPath.TrimEnd(";") + ";" + $PathEntry
    }

    # Persist the new user PATH for future sessions.
    [Environment]::SetEnvironmentVariable("Path", $newPath, "User")
    return $true
}

function Notify-EnvironmentChange {
    # Some GUI processes on Windows listen for WM_SETTINGCHANGE / "Environment" and may refresh
    # their view of environment variables after receiving it. This is best-effort only, but
    # worth doing after PATH changes.
    if (-not ("Agsekit.NativeMethods" -as [type])) {
        # Define a tiny C# interop wrapper around the Win32 API SendMessageTimeout.
        # PowerShell uses Add-Type to compile this helper type at runtime.
        Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;

namespace Agsekit {
    public static class NativeMethods {
        [DllImport("user32.dll", SetLastError = true, CharSet = CharSet.Auto)]
        public static extern IntPtr SendMessageTimeout(
            IntPtr hWnd,
            uint Msg,
            UIntPtr wParam,
            string lParam,
            uint fuFlags,
            uint uTimeout,
            out UIntPtr lpdwResult
        );
    }
}
"@
    }

    # HWND_BROADCAST = every top-level window
    # WM_SETTINGCHANGE = broadcast "system settings changed"
    # lParam = "Environment" tells listeners that environment variables changed
    # SMTO_ABORTIFHUNG prevents the installer from hanging forever on frozen windows
    $HWND_BROADCAST = [intptr]0xffff
    $WM_SETTINGCHANGE = 0x001A
    $SMTO_ABORTIFHUNG = 0x0002
    $result = [uintptr]::Zero

    [void][Agsekit.NativeMethods]::SendMessageTimeout(
        $HWND_BROADCAST,
        $WM_SETTINGCHANGE,
        [uintptr]::Zero,
        "Environment",
        $SMTO_ABORTIFHUNG,
        5000,
        [ref]$result
    )
}

function Get-RefreshedPath {
    # Reconstruct the effective PATH the same way a fresh process would see it:
    # machine PATH first, then user PATH.
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
    # Return a copy-pastable command string that refreshes the current PowerShell session
    # from persisted machine/user PATH values.
    return '$env:Path = "$([Environment]::GetEnvironmentVariable(''Path'',''Machine''));$([Environment]::GetEnvironmentVariable(''Path'',''User''))"'
}

function Write-WrapperScript {
    param(
        [string]$DestinationPath,
        [string]$TargetCommand
    )

    # Write a tiny .cmd launcher:
    # - @echo off keeps the wrapper quiet
    # - the quoted target preserves spaces in paths
    # - %* forwards all user arguments unchanged
    $wrapper = "@echo off`r`n`"$TargetCommand`" %*`r`n"
    Set-Content -Path $DestinationPath -Value $wrapper -Encoding ASCII
}

function Get-PythonInstallerSuffix {
    # PROCESSOR_ARCHITEW6432 is set when a 32-bit process runs on 64-bit Windows.
    # If it is unavailable, fall back to PROCESSOR_ARCHITECTURE.
    $arch = $env:PROCESSOR_ARCHITEW6432
    if ([string]::IsNullOrWhiteSpace($arch)) {
        $arch = $env:PROCESSOR_ARCHITECTURE
    }

    $normalized = if ($arch) { $arch.ToUpperInvariant() } else { "" }

    # Choose the most appropriate official Windows installer flavor.
    if ($normalized -match "ARM64") {
        return "arm64.exe"
    }
    if ([Environment]::Is64BitOperatingSystem) {
        return "amd64.exe"
    }
    return "exe"
}

function Install-Python-WithWinget {
    # If winget does not exist, the caller should try the official python.org installer path.
    $winget = Get-Command winget -ErrorAction SilentlyContinue
    if (-not $winget) {
        return $false
    }

    Write-Host "Installing Python 3.9+ with winget..."

    # `Python.Python.3` means "the current Python 3 package".
    # --exact avoids partial matches.
    # --source winget pins the source explicitly.
    # --scope user avoids machine-wide elevation-sensitive installation.
    # The output is captured so the function returns a strict boolean outcome instead of
    # accidentally leaking winget text into the caller's condition logic.
    $wingetOutput = & $winget.Source install --id Python.Python.3 --exact --source winget --scope user --accept-package-agreements --accept-source-agreements 2>&1
    if ($LASTEXITCODE -ne 0) {
        # Fall back instead of failing outright: winget may be present but unavailable,
        # blocked by policy, missing a package source, or simply not have a usable package.
        Write-Host "winget failed to install Python. Falling back to the official installer."
        return $false
    }

    # Refresh the current session PATH after a successful winget install attempt.
    $env:Path = Get-RefreshedPath
    return $true
}

function Get-LatestPythonInstallerUrl {
    $installerSuffix = Get-PythonInstallerSuffix

    # Download the official Python downloads page and extract installer URLs from it.
    # This keeps the installer current without updating the script for every Python release.
    $response = Invoke-WebRequest -Uri $PythonDownloadsPageUrl -UseBasicParsing

    if ($installerSuffix -eq "exe") {
        # 32-bit x86 installers have names like `python-3.14.4.exe`.
        $pattern = '(?:https://www\.python\.org)?/ftp/python/(?<version>\d+\.\d+\.\d+)/python-(?<fileversion>\d+\.\d+\.\d+)\.exe'
    } else {
        # 64-bit / ARM64 installers have names like `python-3.14.4-amd64.exe`.
        $escapedSuffix = [regex]::Escape($installerSuffix)
        $pattern = "(?:https://www\.python\.org)?/ftp/python/(?<version>\d+\.\d+\.\d+)/python-(?<fileversion>\d+\.\d+\.\d+)-$escapedSuffix"
    }

    $matches = [regex]::Matches($response.Content, $pattern)
    $candidates = foreach ($match in $matches) {
        $versionText = $match.Groups["version"].Value
        $fileVersionText = $match.Groups["fileversion"].Value

        # Ignore mismatched URLs if the directory version and filename version disagree.
        if ($versionText -ne $fileVersionText) {
            continue
        }

        $url = $match.Value
        if ($url -notmatch '^https://') {
            # The page may contain root-relative links; normalize them to absolute URLs.
            $url = "https://www.python.org$url"
        }

        [pscustomobject]@{
            Version = [version]$versionText
            Url = $url
        }
    }

    # Pick the highest semantic version.
    $latest = $candidates | Sort-Object Version -Descending | Select-Object -First 1
    if (-not $latest) {
        Die "Could not determine the latest official Python installer from $PythonDownloadsPageUrl."
    }

    return $latest.Url
}

function Install-Python-FromOfficialSite {
    $installerUrl = Get-LatestPythonInstallerUrl

    # Use a dedicated temp directory per run so logs and downloaded installers do not collide.
    $tempDir = Join-Path ([System.IO.Path]::GetTempPath()) ("agsekit-python-" + [guid]::NewGuid().ToString("N"))
    $installerPath = Join-Path $tempDir (Split-Path $installerUrl -Leaf)
    $logPath = Join-Path $tempDir "python-installer.log"

    Write-Host "Downloading Python installer from $installerUrl"
    Write-Host "Running Python installer..."

    # Run the official installer inside a child PowerShell process encoded as UTF-16 Base64.
    # This avoids quoting problems and isolates the installer execution from the current session.
    $helperScript = @'
$ErrorActionPreference = 'Stop'

# Silence PowerShell's own progress renderer so large downloads do not flood the interactive UI.
$ProgressPreference = 'SilentlyContinue'

$tempDir = '__TEMP_DIR__'
$installerUrl = '__INSTALLER_URL__'
$installerPath = '__INSTALLER_PATH__'
$logPath = '__LOG_PATH__'
$targetDir = '__TARGET_DIR__'

# Ensure the temp directory exists before downloading into it.
New-Item -ItemType Directory -Force -Path $tempDir | Out-Null

# Download the official installer executable.
Invoke-WebRequest -Uri $installerUrl -OutFile $installerPath -UseBasicParsing

# Start-Process is used here instead of direct invocation because we want:
# - an explicit process object,
# - a reliable exit code,
# - a synchronous wait,
# - a clean argument list.
$process = Start-Process -FilePath $installerPath -ArgumentList @(
    '/quiet',

    # /log writes the detailed MSI/bootstrapper log to a predictable file for troubleshooting.
    '/log',
    $logPath,

    # Install per-user to avoid requiring machine-wide admin installation.
    'InstallAllUsers=0',

    # Ask the official installer to prepend its own paths to PATH.
    'PrependPath=1',

    # Include pip so the rest of this installer can install agsekit.
    'Include_pip=1',

    # Include the Python launcher as well.
    'Include_launcher=1',

    # SimpleInstall keeps the install minimal and unattended-friendly.
    'SimpleInstall=1',

    # Use a deterministic target directory owned by this installer.
    ('TargetDir=' + $targetDir)
) -Wait -PassThru

# Emit a single JSON object so the parent process can parse a precise result contract.
[pscustomobject]@{
    ExitCode = $process.ExitCode
    PythonExists = (Test-Path (Join-Path $targetDir 'python.exe'))
    LogPath = $logPath
} | ConvertTo-Json -Compress
'@

    # Fill the child script placeholders with the runtime values chosen in this outer process.
    $helperScript = $helperScript.Replace('__TEMP_DIR__', $tempDir)
    $helperScript = $helperScript.Replace('__INSTALLER_URL__', $installerUrl)
    $helperScript = $helperScript.Replace('__INSTALLER_PATH__', $installerPath)
    $helperScript = $helperScript.Replace('__LOG_PATH__', $logPath)
    $helperScript = $helperScript.Replace('__TARGET_DIR__', $ManagedPythonInstallDir)

    # PowerShell's -EncodedCommand expects UTF-16LE/Unicode bytes.
    $encodedHelper = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($helperScript))
    $helperOutput = & powershell.exe -NoProfile -EncodedCommand $encodedHelper

    # Treat the last line as the JSON contract. Earlier lines, if any, are ignored.
    $helperResultJson = $helperOutput | Select-Object -Last 1
    if ([string]::IsNullOrWhiteSpace($helperResultJson)) {
        Die "The official Python installer did not return a result. Check $logPath for details."
    }

    $helperResult = $helperResultJson | ConvertFrom-Json

    # Exit code 0 means success.
    # Exit code 3010 is the standard Windows installer code for "success, reboot required".
    if ($helperResult.ExitCode -notin @(0, 3010)) {
        Die "The official Python installer failed with exit code $($helperResult.ExitCode). See $($helperResult.LogPath) for details."
    }

    # Refresh PATH in the current process, then wait a bit for the filesystem/registration state
    # to settle before checking the managed install path.
    $env:Path = Get-RefreshedPath
    Start-Sleep -Seconds 5

    if (Test-Path $ManagedPythonExe) {
        return [pscustomobject]@{
            PythonCommand = $ManagedPythonExe
            TempDir = $tempDir
            LogPath = $helperResult.LogPath
        }
    }

    # Return structured failure information to the caller instead of dying here so the caller
    # can still try the generic retry-based detection path.
    return [pscustomobject]@{
        PythonCommand = $null
        TempDir = $tempDir
        LogPath = $helperResult.LogPath
    }
}

function Ensure-Python {
    # First, try to reuse any already-installed supported Python.
    $pythonCommand = Find-SupportedPython
    if ($pythonCommand) {
        return $pythonCommand
    }

    Write-Host "Python 3.9+ is required."

    # Missing Python is an interactive decision point by design: the user explicitly asked
    # for automatic Python installation behavior in this script.
    if (-not (Read-InstallerConfirmation "Python 3.9+ was not found. Install it automatically now?" $true)) {
        Die "Python 3.9+ is required. Install Python first, then rerun this installer."
    }

    $officialInstall = $null

    # Prefer winget when available because it is the most native package-manager path.
    # If winget is missing or fails, fall back to python.org.
    if (-not (Install-Python-WithWinget)) {
        $officialInstall = Install-Python-FromOfficialSite
    }

    # If the official installer returned a direct managed executable path, validate it immediately.
    if ($officialInstall -and $officialInstall.PythonCommand) {
        $supportProbe = Invoke-PythonProbe $officialInstall.PythonCommand @("-c", "import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)")
        if ($supportProbe.Success) {
            $pythonCommand = $officialInstall.PythonCommand
        }
    }

    # If immediate validation failed, keep probing for a while.
    if (-not $pythonCommand) {
        $pythonCommand = Wait-ForSupportedPython -TimeoutSeconds 120
    }

    # Only clean up the temporary installer directory after we have a working Python command.
    # If installation detection failed, the log file is still valuable for debugging.
    if ($pythonCommand -and $officialInstall -and $officialInstall.TempDir) {
        Remove-Item -Path $officialInstall.TempDir -Recurse -Force -ErrorAction SilentlyContinue
    }

    if (-not $pythonCommand) {
        if ($officialInstall -and $officialInstall.LogPath) {
            Die "Automatic Python installation completed, but Python 3.9+ could not be located afterwards. Expected managed install path: $ManagedPythonExe. Installer log: $($officialInstall.LogPath)"
        }
        Die "Automatic Python installation completed, but Python 3.9+ could not be located afterwards. Expected managed install path: $ManagedPythonExe"
    }

    return $pythonCommand
}

# Resolve Python before doing any agsekit-specific work.
$PythonCommand = Ensure-Python

# Create the installation and wrapper directories if they do not exist already.
New-Item -ItemType Directory -Force -Path $InstallRoot | Out-Null
New-Item -ItemType Directory -Force -Path $BinDir | Out-Null

Write-Host "Creating or updating venv: $VenvPath"

# Use the chosen Python to create a dedicated virtual environment.
Invoke-Python $PythonCommand @("-m", "venv", $VenvPath)

$VenvPython = Join-Path $VenvPath "Scripts\python.exe"
$AgsekitExe = Join-Path $VenvPath "Scripts\agsekit.exe"

if (-not (Test-Path $VenvPython)) {
    Die "Venv Python was not created at $VenvPython."
}

Write-Host "Installing package: $Package"

# Upgrade pip inside the venv first so wheel/install behavior is current.
& $VenvPython -m pip install --upgrade pip

# Install or upgrade the requested package into the venv.
& $VenvPython -m pip install --upgrade $Package

if (-not (Test-Path $AgsekitExe)) {
    Die "agsekit executable was not found at $AgsekitExe after installation."
}

# Always create the user-local wrapper in ~/.local/bin.
Write-WrapperScript -DestinationPath $WrapperPath -TargetCommand $AgsekitExe

$managedWrapperWritten = $false

# If Python came from our managed install path, also create a second wrapper inside the managed
# Python Scripts directory. That directory is normally added to PATH by the Python installer,
# so this makes `agsekit` discoverable even in some Windows sessions that do not immediately
# notice a new custom user PATH entry such as `~\.local\bin`.
if ($PythonCommand -and $PythonCommand -ne "py -3" -and $PythonCommand -ieq $ManagedPythonExe) {
    New-Item -ItemType Directory -Force -Path $ManagedPythonBinDir | Out-Null
    Write-WrapperScript -DestinationPath $ManagedWrapperPath -TargetCommand $AgsekitExe
    $managedWrapperWritten = $true
}

# Persist ~/.local/bin into the user PATH for future terminal sessions.
$pathChanged = Ensure-UserPath $BinDir

# Broadcast the environment change and refresh this current PowerShell process as well.
Notify-EnvironmentChange
$env:Path = Get-RefreshedPath

Write-Host ""
Write-Host "agsekit installed."
Write-Host "Install directory: $InstallRoot"
Write-Host "Command wrapper: $WrapperPath"
if ($managedWrapperWritten) {
    Write-Host "Managed Python shim: $ManagedWrapperPath"
}
if ($pathChanged) {
    Write-Host "PATH was updated for future terminal sessions."
} else {
    Write-Host "PATH already contains $BinDir"
}
Write-Host "Current PowerShell session PATH was refreshed."
Write-Host "If another terminal app still does not see agsekit, fully close and reopen it."
Write-Host "This especially applies to already-running Windows Terminal windows/tabs."
Write-Host "If you want to refresh the current session manually, run:"
Write-Host (Get-PathRefreshCommand)
