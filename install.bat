@echo off
title Wolf Trading Bot - Installation
color 0E

echo.
echo  ============================================
echo   Wolf Trading Bot v4.0 - Installation
echo  ============================================
echo.

cd /d "%~dp0"

REM Check Python
echo [1/5] Checking Python installation...
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found!
    echo Please install Python 3.10+ from https://python.org
    pause
    exit /b 1
)

python --version
echo.

REM Check Tesseract
echo [2/5] Checking Tesseract OCR...
tesseract --version >nul 2>&1
if errorlevel 1 (
    echo [WARNING] Tesseract OCR not found!
    echo Please install from: https://github.com/UB-Mannheim/tesseract/wiki
    echo Add to PATH: C:\Program Files\Tesseract-OCR
    echo.
    echo Press any key to continue anyway...
    pause >nul
) else (
    tesseract --version 2>&1 | findstr /C:"tesseract"
)
echo.

REM Create virtual environment
echo [3/5] Creating virtual environment...
if exist "venv" (
    echo Virtual environment already exists.
) else (
    python -m venv venv
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment!
        pause
        exit /b 1
    )
    echo Virtual environment created.
)
echo.

REM Activate and install dependencies
echo [4/5] Installing dependencies...
call venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt

if errorlevel 1 (
    echo [ERROR] Failed to install dependencies!
    pause
    exit /b 1
)
echo.

REM Setup configuration
echo [5/5] Setting up configuration...
if not exist "config\config.yaml" (
    copy "config\config.example.yaml" "config\config.yaml"
    echo Created config\config.yaml from example.
) else (
    echo config\config.yaml already exists.
)

if not exist ".env" (
    copy ".env.example" ".env"
    echo Created .env from example.
    echo.
    echo [IMPORTANT] Please edit .env file with your API keys:
    echo   - TELEGRAM_API_ID
    echo   - TELEGRAM_API_HASH
    echo   - BINGX_API_KEY
    echo   - BINGX_API_SECRET
) else (
    echo .env already exists.
)
echo.

REM Create logs directory
if not exist "logs" mkdir logs

echo  ============================================
echo   Installation Complete!
echo  ============================================
echo.
echo Next steps:
echo   1. Edit .env with your API keys
echo   2. Run auth.bat to authenticate with Telegram
echo   3. Run run_bot.bat to start the bot
echo.

pause
