@echo off
setlocal
set "PYTHONPATH=%~dp0src"
set "PYTHONUTF8=1"
if defined RECEIPTS_PYTHON goto explicit
if exist "%~dp0.venv\Scripts\python.exe" (
  set "RECEIPTS_PYTHON=%~dp0.venv\Scripts\python.exe"
  goto explicit
)
echo Python okruzenje nedostaje. Pokrenite setup.cmd ili postavite RECEIPTS_PYTHON.
exit /b 2
:explicit
if not exist "%RECEIPTS_PYTHON%" (
  echo Python interpreter nije pronadjen: provjerite RECEIPTS_PYTHON.
  exit /b 2
)
"%RECEIPTS_PYTHON%" -m receipts.cli %*
exit /b %errorlevel%
