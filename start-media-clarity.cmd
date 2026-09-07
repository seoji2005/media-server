@echo off
setlocal DisableDelayedExpansion
chcp 65001 >nul
set "PYTHONUTF8=1"
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" goto setup_needed
".venv\Scripts\python.exe" -m media_clarity --open-browser %*
set "MEDIA_CLARITY_EXIT=%ERRORLEVEL%"
if "%MEDIA_CLARITY_EXIT%"=="0" exit /b 0
echo 앱을 실행하지 못했습니다. 이미 실행 중인 창과 README.md의 설치 안내를 확인해 주세요.
pause
exit /b %MEDIA_CLARITY_EXIT%
:setup_needed
echo 처음 실행 설정이 필요합니다. README.md의 Windows 설치 단계를 완료해 주세요.
pause
exit /b 1
