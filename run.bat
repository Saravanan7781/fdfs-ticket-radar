@echo off
cd /d "%~dp0"
echo Starting FDFS Ticket Radar (BookMyShow + District by Zomato)...
.\.venv\Scripts\python.exe radar.py
pause
