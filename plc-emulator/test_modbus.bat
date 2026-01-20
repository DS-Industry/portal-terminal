@echo off
REM Modbus Connection Test Script for Windows
REM Tests connection to PLC emulator

echo ========================================
echo Modbus Connection Test
echo ========================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.x
    pause
    exit /b 1
)

REM Check if pymodbus is installed
python -c "import pymodbus" >nul 2>&1
if errorlevel 1 (
    echo pymodbus not found. Installing...
    pip install pymodbus
    if errorlevel 1 (
        echo ERROR: Failed to install pymodbus
        pause
        exit /b 1
    )
)

REM Get host and port from command line or use defaults
set HOST=localhost
set PORT=5020

if not "%1"=="" set HOST=%1
if not "%2"=="" set PORT=%2

echo Testing connection to %HOST%:%PORT%
echo.

REM Run the test script
python test_modbus_connection.py %HOST% %PORT%

if errorlevel 1 (
    echo.
    echo ========================================
    echo Test failed!
    echo ========================================
    pause
    exit /b 1
) else (
    echo.
    echo ========================================
    echo Test completed successfully!
    echo ========================================
    pause
    exit /b 0
)


