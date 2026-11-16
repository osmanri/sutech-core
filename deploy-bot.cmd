@echo off
REM Double-click to publish the Telegram bot (Windows). Needs Git, Node.js 22 and a filled bot\.env
cd /d "%~dp0"
git fetch origin && git checkout claude/project-competition-review-f8o9yv && git pull || goto :fail
git submodule update --init || goto :fail
if not exist bot\.env (echo bot\.env not found - put your keys there first & goto :fail)
cd serverless
call npm ci || goto :fail
call npm run deploy || goto :fail
echo.
echo DONE. Open the bot in Telegram: the Demo button must be on the home screen.
pause
exit /b 0
:fail
echo.
echo SOMETHING FAILED - send a screenshot of this window.
pause
exit /b 1
