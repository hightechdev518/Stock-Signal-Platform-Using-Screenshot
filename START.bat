@echo off
echo Starting Stock Signal Analyzer...
echo.

:: Kill existing processes
taskkill /F /IM python.exe >nul 2>&1
taskkill /F /IM node.exe >nul 2>&1

:: Start Backend
start "Backend" cmd /k "cd /d d:\My_Work\trading\stock-signal-tool\backend && .\venv\Scripts\activate && uvicorn main:app --reload"

:: Wait 12 seconds for backend to start
timeout /t 12 /nobreak >nul

:: Start Frontend
start "Frontend" cmd /k "cd /d d:\My_Work\trading\stock-signal-tool\frontend && npm start"

:: Wait 5 seconds for frontend to start
timeout /t 5 /nobreak >nul

:: Open browser
start http://127.0.0.1:3000

echo.
echo Stock Signal Analyzer is running!
echo Backend:  http://127.0.0.1:8000
echo Frontend: http://127.0.0.1:3000
echo.
pause
