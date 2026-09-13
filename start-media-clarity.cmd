@echo off
setlocal DisableDelayedExpansion
chcp 65001 >nul
set "PYTHONUTF8=1"
cd /d "%~dp0"
set "MEDIA_CLARITY_PYTHON=.venv\Scripts\python.exe"
if not exist "%MEDIA_CLARITY_PYTHON%" set "MEDIA_CLARITY_PYTHON=.venv-viewing\Scripts\python.exe"
if not exist "%MEDIA_CLARITY_PYTHON%" goto setup_needed
"%MEDIA_CLARITY_PYTHON%" -m media_clarity --open-browser %*
set "MEDIA_CLARITY_EXIT=%ERRORLEVEL%"
if "%MEDIA_CLARITY_EXIT%"=="0" exit /b 0
echo 앱을 실행하지 못했습니다. 이미 실행 중인 창과 README.md의 설치 안내를 확인해 주세요.
pause
exit /b %MEDIA_CLARITY_EXIT%
:setup_needed
echo 처음 실행 설정이 필요합니다. 감상부터 시작하려면 install-media-clarity.cmd --viewing-only 를 실행하세요.
pause
exit /b 1
