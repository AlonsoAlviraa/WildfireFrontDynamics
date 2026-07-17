@echo off
REM Field kit: live incident runtime (incident_runtime_v1)
REM Usage:
REM   scripts\run_incident.cmd D:\drops\inbox outputs\incidents\IF2026_XXX
REM   scripts\run_incident.cmd D:\drops\inbox outputs\incidents\IF2026_XXX --once
REM   scripts\run_incident.cmd D:\drops\inbox outputs\incidents\IF2026_XXX --masks D:\masks

setlocal EnableDelayedExpansion
set ROOT=%~dp0..
cd /d "%ROOT%"

if "%~1"=="" (
  echo Usage: run_incident.cmd ^<inbox_dir^> ^<work_dir^> [extra args...]
  echo Example: run_incident.cmd D:\drops\inbox outputs\incidents\demo --max-frames 10
  exit /b 2
)
if "%~2"=="" (
  echo ERROR: work_dir required
  exit /b 2
)

set "INBOX=%~1"
set "WORK=%~2"
set "EVENT_ID=%~n2"
if "!EVENT_ID!"=="" set "EVENT_ID=incident"

REM Collect remaining args after inbox and work_dir
set "EXTRA="
shift
shift
:loop
if "%~1"=="" goto run
set "EXTRA=!EXTRA! "%~1""
shift
goto loop

:run
python -m wildfire_front incident watch --inbox "%INBOX%" --work-dir "%WORK%" --event-id "%EVENT_ID%" --sensor-id lwir_drone --estimated-error-m 2.0 --interval-s 2 %EXTRA%
set ERR=%ERRORLEVEL%
endlocal & exit /b %ERR%
