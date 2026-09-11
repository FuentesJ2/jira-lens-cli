@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
set "RUNNER="

if exist "%SCRIPT_DIR%jira-context.exe" (
    "%SCRIPT_DIR%jira-context.exe" %*
    exit /b %errorlevel%
)

where py >nul 2>nul
if not errorlevel 1 (
    py -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)" >nul 2>nul
    if not errorlevel 1 set "RUNNER=py -3"
)

if not defined RUNNER (
    where python >nul 2>nul
    if not errorlevel 1 (
        python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)" >nul 2>nul
        if not errorlevel 1 set "RUNNER=python"
    )
)

if not defined RUNNER (
    echo Python 3.9+ is required to run jira-context. 1>&2
    echo Install Python 3.9+ and make sure either `py` or `python` is available on PATH. 1>&2
    exit /b 1
)

%RUNNER% "%SCRIPT_DIR%run_cli.py" %*
exit /b %errorlevel%