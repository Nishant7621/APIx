@echo off
title APIx Automated Daily Scraping Engine Daemon
cd /d "%~dp0\.."
echo =====================================================================
echo       Starting APIx Continuous Automated Scraping Engine
echo       Schedule: Runs every morning at 06:00:00 AM IST
echo =====================================================================
.\venv\Scripts\python.exe scheduler\daily_auto_collector.py --daemon
pause
