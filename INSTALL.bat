@echo off
echo Installing Stock Signal Analyzer...
echo.
echo Step 1 - Installing Python dependencies...
cd backend
python -m venv venv
.\venv\Scripts\activate
pip install -r ..\requirements.txt
echo.
echo Step 2 - Installing Node dependencies...
cd ..\frontend
npm install
echo.
echo Installation complete!
echo Double-click START.bat to run the tool.
pause
