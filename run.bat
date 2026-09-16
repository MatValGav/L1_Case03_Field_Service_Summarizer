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
    :: Check if groq is installed, reinstall deps if missing
    venv\Scripts\python -c "from groq import Groq" >nul 2>&1
    if %errorlevel% neq 0 (
        echo Installing dependencies...
        venv\Scripts\pip install -r requirements.txt
        echo.
    )
)

:: 5. Load API key from .env if not already set
if "%GROQ_API_KEY%"=="" (
    if exist ".env" (
        for /f "usebackq tokens=1,* delims==" %%a in (".env") do (
            if "%%a"=="GROQ_API_KEY" set "GROQ_API_KEY=%%b"
        )
    )
)

if "%GROQ_API_KEY%"=="" (
    echo ERROR: GROQ_API_KEY is not set.
    echo.
    echo Create a .env file in this folder with the following line:
    echo   GROQ_API_KEY=your-groq-key-here
    echo.
    echo Get a free API key at https://console.groq.com
    echo.
    pause
    exit /b 1
)

:: 6. Launch the tool
echo Starting the tool...
venv\Scripts\python main.py
