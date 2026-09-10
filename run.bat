@echo off
setlocal

echo ============================================
echo  Field Service Report Summarizer
echo ============================================
echo.

:: 1. Check Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python is not installed or not in PATH.
    echo.
    echo Install Python from https://www.python.org/downloads
    echo Make sure to check "Add Python to PATH" during installation.
    echo.
    pause
    exit /b 1
)

:: 2-4. Create venv and install dependencies if needed
if not exist "venv\Scripts\python.exe" (
    echo Creating virtual environment...
    python -m venv venv
    echo Installing dependencies...
    venv\Scripts\pip install -r requirements.txt
    echo.
) else (
    :: Check if google-genai is installed, reinstall deps if missing
    venv\Scripts\python -c "from google import genai" >nul 2>&1
    if %errorlevel% neq 0 (
        echo Installing dependencies...
        venv\Scripts\pip install -r requirements.txt
        echo.
    )
)

:: 5. Load API key from .env if not already set
if "%GOOGLE_API_KEY%"=="" (
    if exist ".env" (
        for /f "usebackq tokens=1,* delims==" %%a in (".env") do (
            if "%%a"=="GOOGLE_API_KEY" set "GOOGLE_API_KEY=%%b"
        )
    )
)

if "%GOOGLE_API_KEY%"=="" (
    echo ERROR: GOOGLE_API_KEY is not set.
    echo.
    echo Create a .env file in this folder with the following line:
    echo   GOOGLE_API_KEY=your-key-here
    echo.
    echo Get a free API key at https://aistudio.google.com/apikey
    echo.
    pause
    exit /b 1
)

:: 6. Launch the tool
echo Starting the tool...
venv\Scripts\python main.py
