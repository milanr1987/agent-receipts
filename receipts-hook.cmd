@echo off
call "%~dp0receipts.cmd" hook %*
rem Advisory adapter always fails open, including missing interpreter/setup.
exit /b 0
