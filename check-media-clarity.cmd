@echo off
setlocal DisableDelayedExpansion
chcp 65001 >nul
set "PYTHONUTF8=1"
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" goto setup_needed
".venv\Scripts\python.exe" scripts\check_setup.py %*
set "MEDIA_CLARITY_EXIT=%ERRORLEVEL%"
pause
exit /b %MEDIA_CLARITY_EXIT%
:setup_needed
echo 처음 실행 설정이 필요합니다. README.md의 Windows 설치 단계를 완료해 주세요.
pause
exit /b 1
