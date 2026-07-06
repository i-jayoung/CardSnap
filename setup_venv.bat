@echo off
echo ========================================
echo   CardSnap - Creating Virtual Environment
echo ========================================
echo.
echo Creating virtual environment...
python -m venv .venv
call .venv\Scripts\activate.bat
echo Installing dependencies...
pip install -r requirements.txt
echo.
echo ========================================
echo   Done! Run 'run.bat' to start the app.
echo ========================================
pause
