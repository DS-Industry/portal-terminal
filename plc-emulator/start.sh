#!/bin/bash
# Quick start script for PLC Emulator

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "🚀 Starting PLC Emulator..."
echo ""

# Check if Docker is available
if command -v docker &> /dev/null && command -v docker-compose &> /dev/null; then
    echo "Using Docker Compose..."
    
    # Check if .env exists
    if [ ! -f .env ]; then
        echo "⚠️  .env file not found. Creating from env.example..."
        if [ -f env.example ]; then
            cp env.example .env
            echo "✅ Created .env file. Please review and edit if needed."
        fi
    fi
    
    docker-compose up -d
    
    echo ""
    echo "✅ PLC Emulator started!"
    echo ""
    echo "Status:    docker-compose ps"
    echo "Logs:      docker-compose logs -f"
    echo "Stop:      docker-compose down"
    echo ""
    echo "Emulator is available on:"
    echo "  - localhost:5020 (from host)"
    echo "  - plc-emulator:502 (from Docker network)"
    
elif command -v python3 &> /dev/null; then
    echo "Using standalone Python..."
    echo ""
    
    # Check if pymodbus is installed
    if ! python3 -c "import pymodbus" 2>/dev/null; then
        echo "⚠️  pymodbus not found. Installing..."
        pip install -r requirements.txt
    fi
    
    echo "Starting PLC emulator..."
    python3 plc_emulator.py
    
else
    echo "❌ Error: Neither Docker nor Python3 found!"
    echo "Please install Docker or Python3 to run the emulator."
    exit 1
fi

