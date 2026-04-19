@echo off
setlocal EnableExtensions

if "%AGSEKIT_MSYS2_ROOT%"=="" (
    set "MSYS2_ROOT=C:\msys64"
) else (
    set "MSYS2_ROOT=%AGSEKIT_MSYS2_ROOT%"
)

set "MSYS2_BIN=%MSYS2_ROOT%\usr\bin"
set "MSYS2_BASH=%MSYS2_BIN%\bash.exe"

echo Dangerous Windows developer cleanup
echo.
echo This script will:
echo - remove MSYS2 packages used by agsekit prepare: rsync and openssh;
echo - uninstall MSYS2 through winget, if winget is available;
echo - remove the MSYS2 directory "%MSYS2_ROOT%" if it remains;
echo - remove "%MSYS2_BIN%" from the user PATH.
echo.
echo This is intended only for project developers testing installation flows.
echo Do not run it on a workstation where you want to keep MSYS2.
echo.

set /p CONFIRM=Type yes to continue: 
if /I not "%CONFIRM%"=="yes" (
    echo Aborted.
    exit /B 0
)

if exist "%MSYS2_BASH%" (
    echo Removing MSYS2 packages: rsync openssh
    "%MSYS2_BASH%" -lc "pacman -Rns --noconfirm rsync openssh || true"
) else (
    echo MSYS2 bash was not found at "%MSYS2_BASH%"; skipping pacman package removal.
)

where winget >nul 2>nul
if errorlevel 1 (
    echo winget was not found; skipping winget uninstall.
) else (
    echo Uninstalling MSYS2 through winget.
    winget uninstall --id MSYS2.MSYS2 -e
)

where powershell >nul 2>nul
if errorlevel 1 (
    echo PowerShell was not found; skipping user PATH cleanup.
) else (
    echo Removing MSYS2 bin directory from user PATH.
    powershell -NoProfile -ExecutionPolicy Bypass -Command "$entry=$env:MSYS2_BIN; $path=[Environment]::GetEnvironmentVariable('Path','User'); if ($path) { $parts=$path -split ';' | Where-Object { $_ -and ($_ -ine $entry) }; [Environment]::SetEnvironmentVariable('Path', ($parts -join ';'), 'User') }"
)

if exist "%MSYS2_ROOT%" (
    echo Removing "%MSYS2_ROOT%".
    rmdir /S /Q "%MSYS2_ROOT%"
) else (
    echo MSYS2 directory is already absent.
)

echo Done.
