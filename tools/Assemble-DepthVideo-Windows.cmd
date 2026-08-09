@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

set "NO_PAUSE="
if /I "%~1"=="--no-pause" set "NO_PAUSE=1"

set "PART1=DepthVideo-Windows-x64.zip.001"
set "PART2=DepthVideo-Windows-x64.zip.002"
set "OUTPUT=DepthVideo-Windows-x64.zip"
set "EXPECTED=633176ACD08EBF8DAF958FF6805E64223250F6107A13906CCCD1266EA459BB93"

if not exist "%PART1%" (
    echo Missing %PART1%
    goto :failed
)

if not exist "%PART2%" (
    echo Missing %PART2%
    goto :failed
)

if exist "%OUTPUT%" del /q "%OUTPUT%"

echo Assembling %OUTPUT%...
copy /b "%PART1%"+"%PART2%" "%OUTPUT%" >nul
if errorlevel 1 goto :failed

set "ACTUAL="
for /f "skip=1 tokens=*" %%H in ('certutil -hashfile "%OUTPUT%" SHA256') do (
    if not defined ACTUAL set "ACTUAL=%%H"
)
set "ACTUAL=!ACTUAL: =!"

if /I not "!ACTUAL!"=="%EXPECTED%" (
    echo SHA-256 verification failed.
    echo Expected: %EXPECTED%
    echo Actual:   !ACTUAL!
    del /q "%OUTPUT%"
    goto :failed
)

echo.
echo SHA-256 verified.
echo Created: %OUTPUT%
echo Extract the ZIP, then run DepthVideo\DepthVideo.exe.
echo.
if not defined NO_PAUSE pause
exit /b 0

:failed
echo.
echo Assembly failed. Download all release files again and retry.
echo.
if not defined NO_PAUSE pause
exit /b 1
