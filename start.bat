@echo off
REM Instagram Content Automation - launcher / status checker
cd /d "%~dp0"
call venv\Scripts\activate.bat

:menu
cls
echo ============================================
echo   Instagram Content Automation
echo ============================================
echo.
echo  1. Open dashboard (GUI)
echo  2. Quick status check (local)
echo  3. Check the automated 24/7 scans (GitHub)
echo  4. Open GitHub Actions in browser
echo  5. Exit
echo.
set "choice="
set /p choice="Choose an option (1-5): "

if "%choice%"=="1" goto gui
if "%choice%"=="2" goto status
if "%choice%"=="3" goto actions
if "%choice%"=="4" goto web
if "%choice%"=="5" goto end
goto menu

:gui
python main.py --gui
goto end

:status
echo.
python main.py --status
echo.
pause
goto menu

:actions
echo.
echo Checking the automated scan that runs every hour on GitHub...
echo (This is the part that runs on its own, without your computer.)
echo.

for /f "usebackq tokens=*" %%r in (`gh run list --workflow=scan.yml --limit 1 --json databaseId --jq ".[0].databaseId"`) do set LATEST_RUN=%%r

if "%LATEST_RUN%"=="" (
    echo Could not reach GitHub. Check your internet connection, or that
    echo "gh auth status" is still logged in.
    echo.
    pause
    goto menu
)

echo Most recent automated run: %LATEST_RUN%
echo.
powershell -NoProfile -Command "$s = gh run view %LATEST_RUN% --log | Select-String 'Check complete'; if ($s) { $s.Line -replace '.*Check complete', 'Scrape result -> Check complete' } else { 'Scrape result -> not found (run may still be in progress)' }"
powershell -NoProfile -Command "$s = gh run view %LATEST_RUN% --log | Select-String '\"published\":'; if ($s) { 'Publish result -> ' + ($s.Line -replace '.*\"published\": (\d+).*', '$1 post(s) published this run') } else { 'Publish result -> not found (run may still be in progress)' }"
echo.
echo Last 5 automated runs (success/failure, how long ago):
gh run list --workflow=scan.yml --limit 5
echo.
echo Tip: if "new posts" is 0 for several runs in a row, scraping may be
echo stuck (e.g. Instagram temporarily blocking it) - open option 4 for
echo the full details, or ask Claude to look into it.
echo.
pause
goto menu

:web
start https://github.com/Poochi2011/instagram-content-automation/actions
goto menu

:end
