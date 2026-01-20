# Modbus Connection Test Script for Windows PowerShell
# Tests connection to PLC emulator

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Modbus Connection Test" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if Python is installed
try {
    $pythonVersion = python --version 2>&1
    Write-Host "Python found: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "ERROR: Python is not installed or not in PATH" -ForegroundColor Red
    Write-Host "Please install Python 3.x" -ForegroundColor Yellow
    Read-Host "Press Enter to exit"
    exit 1
}

# Check if pymodbus is installed
try {
    python -c "import pymodbus" 2>&1 | Out-Null
    Write-Host "pymodbus found" -ForegroundColor Green
} catch {
    Write-Host "pymodbus not found. Installing..." -ForegroundColor Yellow
    pip install pymodbus
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Failed to install pymodbus" -ForegroundColor Red
        Read-Host "Press Enter to exit"
        exit 1
    }
}

# Get host and port from command line or use defaults
$host = "localhost"
$port = 5020

if ($args.Count -gt 0) {
    $host = $args[0]
}

if ($args.Count -gt 1) {
    try {
        $port = [int]$args[1]
    } catch {
        Write-Host "ERROR: Invalid port number: $($args[1])" -ForegroundColor Red
        Write-Host ""
        Write-Host "Usage: .\test_modbus.ps1 [host] [port]"
        Write-Host "Example: .\test_modbus.ps1 192.168.1.100 5020"
        Read-Host "Press Enter to exit"
        exit 1
    }
}

Write-Host "Testing connection to ${host}:${port}" -ForegroundColor Cyan
Write-Host ""

# Run the test script
python test_modbus_connection.py $host $port

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Red
    Write-Host "Test failed!" -ForegroundColor Red
    Write-Host "========================================" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
} else {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "Test completed successfully!" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
    Read-Host "Press Enter to exit"
    exit 0
}


