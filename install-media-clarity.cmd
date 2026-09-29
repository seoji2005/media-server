@echo off
setlocal DisableDelayedExpansion
chcp 65001 >nul
set "PYTHONUTF8=1"
cd /d "%~dp0"
where py >nul 2>&1
if errorlevel 1 goto python_on_path
py -3.12 scripts/install_runtime.py %*
goto finished
:python_on_path
python scripts/install_runtime.py %*
:finished
set "MEDIA_CLARITY_EXIT=%ERRORLEVEL%"
if "%MEDIA_CLARITY_EXIT%"=="0" exit /b 0
echo Python 3.12와 FFmpeg 설치 상태 및 진단 코드를 확인해 주세요.
pause
exit /b %MEDIA_CLARITY_EXIT%
