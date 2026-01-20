#!/usr/bin/env python3
"""
Modbus Connection Test Script
Tests connection to PLC emulator from Windows PC

Usage:
    python test_modbus_connection.py [host] [port]

Example:
    python test_modbus_connection.py 192.168.1.100 5020
    python test_modbus_connection.py localhost 5020
"""

import sys
import os

def test_modbus_connection(host='localhost', port=5020):
    """Test Modbus TCP connection to PLC emulator"""
    
    print("=" * 60)
    print("Modbus Connection Test")
    print("=" * 60)
    print(f"Target: {host}:{port}")
    print()
    
    try:
        from pymodbus.client import ModbusTcpClient
    except ImportError:
        print("❌ ERROR: pymodbus not installed!")
        print()
        print("Install it with:")
        print("  pip install pymodbus")
        print()
        return False
    
    # Test 1: Connection
    print("Test 1: Connecting to PLC emulator...")
    try:
        client = ModbusTcpClient(host=host, port=port, timeout=5)
        
        if not client.connect():
            print(f"❌ FAILED: Could not connect to {host}:{port}")
            print()
            print("Troubleshooting:")
            print(f"  1. Check if PLC emulator is running on {host}")
            print(f"  2. Verify port {port} is correct")
            print(f"  3. Check firewall settings (most common issue!)")
            print(f"  4. Test with: ping {host}")
            print(f"  5. Test port with: python diagnose_connection.py {host} {port}")
            print()
            print("Common issue: Ping works but port is blocked by firewall")
            print("  - On Mac: Check System Preferences → Security → Firewall")
            print("  - Allow Python/Docker through firewall")
            print("  - Or temporarily disable firewall for testing")
            return False
        
        print("✅ SUCCESS: Connected!")
        print()
        
    except Exception as e:
        print(f"❌ FAILED: Connection error: {e}")
        return False
    
    # Test 2: Read Program 1 (Input Registers 0-14)
    print("Test 2: Reading Program 1 (registers 0-14)...")
    try:
        result = client.read_input_registers(0, 15)
        
        if result.isError():
            print("❌ FAILED: Error reading registers")
            client.close()
            return False
        
        registers = result.registers
        # Filter out zeros to show actual program steps
        steps = [r for r in registers if r != 0]
        print(f"✅ SUCCESS: Read {len(registers)} registers")
        print(f"   Program steps: {steps}")
        print()
        
    except Exception as e:
        print(f"❌ FAILED: Error reading registers: {e}")
        client.close()
        return False
    
    # Test 3: Read Price (Input Register 30)
    print("Test 3: Reading Program 1 price (register 30)...")
    try:
        result = client.read_input_registers(30, 1)
        
        if result.isError():
            print("❌ FAILED: Error reading price")
            client.close()
            return False
        
        price = result.registers[0]
        print(f"✅ SUCCESS: Price = {price} rubles")
        print()
        
    except Exception as e:
        print(f"❌ FAILED: Error reading price: {e}")
        client.close()
        return False
    
    # Test 4: Read Wash Status (Discrete Input 0)
    print("Test 4: Reading wash status (discrete input 0)...")
    try:
        result = client.read_discrete_inputs(0, 1)
        
        if result.isError():
            print("❌ FAILED: Error reading status")
            client.close()
            return False
        
        status = "In Progress" if result.bits[0] else "Idle"
        print(f"✅ SUCCESS: Wash status = {status}")
        print()
        
    except Exception as e:
        print(f"❌ FAILED: Error reading status: {e}")
        client.close()
        return False
    
    # Test 5: Write Coil (Start Command)
    print("Test 5: Testing write coil (start Program 1)...")
    try:
        result = client.write_coil(0, True)
        
        if result.isError():
            print("❌ FAILED: Error writing coil")
            client.close()
            return False
        
        print("✅ SUCCESS: Write command sent")
        
        # Reset it back
        client.write_coil(0, False)
        print("   (Reset coil back to False)")
        print()
        
    except Exception as e:
        print(f"❌ FAILED: Error writing coil: {e}")
        client.close()
        return False
    
    # Close connection
    client.close()
    
    print("=" * 60)
    print("✅ ALL TESTS PASSED!")
    print("=" * 60)
    print()
    print("Your Modbus connection is working correctly.")
    print(f"You can now use {host}:{port} in your application.")
    print()
    
    return True


def main():
    """Main entry point"""
    # Get host and port from command line or use defaults
    host = 'localhost'
    port = 5020
    
    if len(sys.argv) > 1:
        host = sys.argv[1]
    
    if len(sys.argv) > 2:
        try:
            port = int(sys.argv[2])
        except ValueError:
            print(f"❌ ERROR: Invalid port number: {sys.argv[2]}")
            print()
            print("Usage: python test_modbus_connection.py [host] [port]")
            print("Example: python test_modbus_connection.py 192.168.1.100 5020")
            sys.exit(1)
    
    # Check if host is an IP or hostname
    if host == 'localhost' or host == '127.0.0.1':
        print("ℹ️  Using localhost - testing local connection")
        print("   For remote connection, use: python test_modbus_connection.py <IP> <PORT>")
        print()
    
    success = test_modbus_connection(host, port)
    
    if not success:
        print("=" * 60)
        print("❌ TESTS FAILED")
        print("=" * 60)
        print()
        print("Common issues:")
        print("  1. PLC emulator not running")
        print("  2. Wrong IP address or port")
        print("  3. Firewall blocking connection")
        print("  4. Network connectivity issues")
        print()
        print("Troubleshooting:")
        print(f"  - Ping test: ping {host}")
        print(f"  - Port test: telnet {host} {port} (if available)")
        print(f"  - Check PLC emulator logs")
        sys.exit(1)
    
    sys.exit(0)


if __name__ == "__main__":
    main()

