@echo off
setlocal
if defined RECEIPTS_PYTHON goto configure
where py >nul 2>nul
if not errorlevel 1 (
  py -3 -c "import sys; assert sys.version_info >= (3,12); import venv; venv.create(sys.argv[1], with_pip=False)" "%~dp0.venv"
  goto result
)
where python >nul 2>nul
if errorlevel 1 (
  echo Install Python 3.12 or newer, then run setup.cmd again.
  exit /b 2
)
python -c "import sys; assert sys.version_info >= (3,12); import venv; venv.create(sys.argv[1], with_pip=False)" "%~dp0.venv"
goto result
:configure
"%RECEIPTS_PYTHON%" -c "import sys; assert sys.version_info >= (3,12); import venv; venv.create(sys.argv[1], with_pip=False)" "%~dp0.venv"
:result
if errorlevel 1 (
  echo Setup failed. Python 3.12+ with standard venv support is required. No downloads were attempted.
  exit /b 2
)
echo Ready. Run receipts.cmd --help
