@echo off
REM Launches the Instagram Content Automation desktop GUI using the project's venv.
cd /d "%~dp0"
call venv\Scripts\activate.bat
python main.py --gui
pause
