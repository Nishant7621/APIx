@echo off
REM APIx Automation Command-Line Tool
REM Enables 1-command automated scraping, status checking, and continuous daemon execution.

set SCRIPT_DIR=%~dp0
"%SCRIPT_DIR%venv\Scripts\python.exe" "%SCRIPT_DIR%apix.py" %*
