#!/bin/bash
# Helper script to start hardware emulators

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "🚀 Starting Hardware Emulators..."
echo ""

# Check if Docker is available
if command -v docker &> /dev/null && command -v docker-compose &> /dev/null; then
    echo "Using Docker Compose..."
    cd "$PROJECT_DIR"
    docker-compose -f docker-compose-emulators.yml up -d
    
    echo ""
    echo "✅ Emulators started!"
    echo ""
    echo "PLC Emulator:    localhost:5020 (or plc-emulator:502 in Docker network)"
    echo "POS Emulator:    localhost:4001 (or pos-emulator:4001 in Docker network)"
    echo ""
    echo "View logs:       docker-compose -f docker-compose-emulators.yml logs -f"
    echo "Stop emulators:  docker-compose -f docker-compose-emulators.yml down"
    
elif command -v python3 &> /dev/null; then
    echo "Using standalone Python..."
    echo ""
    
    # Check if pymodbus is installed
    if ! python3 -c "import pymodbus" 2>/dev/null; then
        echo "⚠️  pymodbus not found. Installing..."
        pip install pymodbus==3.5.2
    fi
    
    # Start PLC emulator
    echo "Starting PLC emulator on port 5020..."
    cd "$PROJECT_DIR"
    python3 emulators/modbus_plc_emulator.py --host 0.0.0.0 --port 5020 > /tmp/plc-emulator.log 2>&1 &
    PLC_PID=$!
    echo "PLC Emulator PID: $PLC_PID"
    
    # Start POS emulator
    echo "Starting POS emulator on port 4001..."
    python3 emulators/vendotek_pos_emulator.py --host 0.0.0.0 --port 4001 > /tmp/pos-emulator.log 2>&1 &
    POS_PID=$!
    echo "POS Emulator PID: $POS_PID"
    
    echo ""
    echo "✅ Emulators started!"
    echo ""
    echo "PLC Emulator:    localhost:5020 (PID: $PLC_PID)"
    echo "POS Emulator:    localhost:4001 (PID: $POS_PID)"
    echo ""
    echo "View logs:"
    echo "  PLC: tail -f /tmp/plc-emulator.log"
    echo "  POS: tail -f /tmp/pos-emulator.log"
    echo ""
    echo "Stop emulators:"
    echo "  kill $PLC_PID $POS_PID"
    echo ""
    echo "PIDs saved to: /tmp/emulator-pids.txt"
    echo "$PLC_PID" > /tmp/emulator-pids.txt
    echo "$POS_PID" >> /tmp/emulator-pids.txt
    
else
    echo "❌ Error: Neither Docker nor Python3 found!"
    echo "Please install Docker or Python3 to run emulators."
    exit 1
fi

