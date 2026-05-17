@echo off
echo Stopping Stock Signal Analyzer...
taskkill /F /IM python.exe >nul 2>&1
taskkill /F /IM node.exe >nul 2>&1
echo All servers stopped!
pause
