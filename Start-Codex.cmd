@echo off
setlocal
where codex >nul 2>nul
if errorlevel 1 (
  echo Codex CLI nije na PATH-u. Otvorite ovaj folder u instaliranom Codexu.
  pause
  exit /b 1
)
cd /d "%~dp0"
call codex -C "%~dp0." -a never -s workspace-write -c sandbox_workspace_write.network_access=true
