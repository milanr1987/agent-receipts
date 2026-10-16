@echo off
setlocal
set "PYTHONPATH=%~dp0src"
set "PYTHONUTF8=1"
if defined RECEIPTS_PYTHON goto explicit
if exist "%~dp0.venv\Scripts\python.exe" (
  set "RECEIPTS_PYTHON=%~dp0.venv\Scripts\python.exe"
  goto explicit
)
echo Python environment missing. Run setup.cmd or set RECEIPTS_PYTHON. 1>&2
exit /b 2
:explicit
if not exist "%RECEIPTS_PYTHON%" (
  echo Python interpreter not found: check RECEIPTS_PYTHON. 1>&2
  exit /b 2
)
rem -P keeps modules in the caller's directory off sys.path (hooks run inside user projects).
"%RECEIPTS_PYTHON%" -P -m receipts.cli %*
exit /b %errorlevel%
