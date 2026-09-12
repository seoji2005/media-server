@echo off
setlocal DisableDelayedExpansion
call "%~dp0start-media-clarity.cmd" --prompt-gemini-key %*
exit /b %ERRORLEVEL%
