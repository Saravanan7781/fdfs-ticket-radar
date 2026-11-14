@echo off
cd /d "%~dp0"
echo Starting FDFS Ticket Radar Dashboard...
.\.venv\Scripts\python.exe web_ui.py
pause
