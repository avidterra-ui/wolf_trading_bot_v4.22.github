@echo off
title Wolf Trading Bot v4.0
color 0B

echo.
echo  ============================================
echo   Wolf Trading Bot v4.0
echo   Telegram to BingX Auto-Trading System
echo  ============================================
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

REM Check if .env exists
if not exist ".env" (
    echo [WARNING] .env file not found!
    echo Please copy .env.example to .env and configure your API keys.
    pause
)

REM Run the bot
python -m src.main

REM Keep window open on error
if errorlevel 1 (
    echo.
    echo [ERROR] Bot exited with error!
    pause
)
