@echo off
setlocal DisableDelayedExpansion
chcp 65001 >nul
set "PYTHONUTF8=1"
cd /d "%~dp0"
py -3.12 scripts/install_runtime.py %*
set "MEDIA_CLARITY_EXIT=%ERRORLEVEL%"
if "%MEDIA_CLARITY_EXIT%"=="0" exit /b 0
echo Python 3.12와 FFmpeg 설치 상태 및 진단 코드를 확인해 주세요.
pause
exit /b %MEDIA_CLARITY_EXIT%
