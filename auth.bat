@echo off
title Wolf Trading Bot - Telegram Authentication
color 0A

echo.
echo  ============================================
echo   Telegram Authentication
echo  ============================================
echo.
echo This will create a new Telegram session.
echo You will need to enter your phone number and
echo the verification code sent to your Telegram.
echo.

cd /d "%~dp0"

REM Check if virtual environment exists
if not exist "venv\Scripts\activate.bat" (
    echo [ERROR] Virtual environment not found!
    echo Please run install.bat first.
    pause
    exit /b 1
)

REM Activate virtual environment
call venv\Scripts\activate

REM Run authentication
python -m src.main auth

echo.
pause
