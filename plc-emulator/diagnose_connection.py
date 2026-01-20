#!/usr/bin/env python3
"""
Connection Diagnostic Script
Helps troubleshoot Modbus connection issues when ping works but connection fails
"""

import sys
import socket
import subprocess
import platform

def test_ping(host):
    """Test if host is reachable via ping"""
    print(f"Test 1: Testing ping to {host}...")
    
    try:
        # Use appropriate ping command for OS
        if platform.system().lower() == 'windows':
            result = subprocess.run(['ping', '-n', '1', host], 
                                 capture_output=True, timeout=5)
        else:
            result = subprocess.run(['ping', '-c', '1', host], 
                                 capture_output=True, timeout=5)
        
        if result.returncode == 0:
            print("✅ SUCCESS: Ping works")
            return True
        else:
            print("❌ FAILED: Ping failed")
            return False
    except Exception as e:
        print(f"⚠️  Could not test ping: {e}")
        return None

def test_port_connection(host, port, timeout=5):
    """Test if port is accessible"""
    print(f"Test 2: Testing port {port} on {host}...")
    
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()
        
        if result == 0:
            print(f"✅ SUCCESS: Port {port} is open and accessible")
            return True
        else:
            print(f"❌ FAILED: Port {port} is not accessible (error code: {result})")
            print(f"   This means the port is blocked or nothing is listening")
            return False
    except socket.gaierror as e:
        print(f"❌ FAILED: DNS/hostname resolution error: {e}")
        return False
    except socket.timeout:
        print(f"❌ FAILED: Connection timeout (port might be blocked by firewall)")
        return False
    except Exception as e:
        print(f"❌ FAILED: Error: {e}")
        return False

def test_modbus_connection(host, port):
    """Test actual Modbus connection"""
    print(f"Test 3: Testing Modbus connection to {host}:{port}...")
    
    try:
        from pymodbus.client import ModbusTcpClient
    except ImportError:
        print("❌ ERROR: pymodbus not installed")
        print("   Install with: pip install pymodbus")
        return False
    
    try:
        client = ModbusTcpClient(host=host, port=port, timeout=5)
        
        if client.connect():
            print("✅ SUCCESS: Modbus connection established")
            
            # Try a simple read
            try:
                result = client.read_input_registers(0, 1)
                if not result.isError():
                    print(f"✅ SUCCESS: Can read registers (test read: {result.registers[0]})")
                else:
                    print("⚠️  WARNING: Connected but read failed")
            except Exception as e:
                print(f"⚠️  WARNING: Connected but read error: {e}")
            
            client.close()
            return True
        else:
            print("❌ FAILED: Could not establish Modbus connection")
            return False
            
    except Exception as e:
        print(f"❌ FAILED: Modbus connection error: {e}")
        return False

def check_firewall_suggestions(host, port):
    """Provide firewall troubleshooting suggestions"""
    print()
    print("=" * 60)
    print("FIREWALL TROUBLESHOOTING")
    print("=" * 60)
    print()
    print("If ping works but port connection fails, it's likely a firewall issue.")
    print()
    print("On Mac (where PLC emulator is running):")
    print("  1. Check macOS Firewall:")
    print("     System Preferences → Security & Privacy → Firewall")
    print()
    print("  2. Allow Python/Docker through firewall:")
    print("     Firewall Options → Add Python or Docker")
    print()
    print("  3. Or temporarily disable firewall for testing:")
    print("     sudo /usr/libexec/ApplicationFirewall/socketfilterfw --setglobalstate off")
    print()
    print("  4. Check if port is actually listening:")
    print(f"     lsof -i :{port}")
    print(f"     netstat -an | grep {port}")
    print()
    print("On Windows (where you're connecting from):")
    print("  1. Check Windows Firewall:")
    print("     Control Panel → Windows Defender Firewall")
    print()
    print("  2. Allow Python through firewall if needed")
    print()
    print("Router/Network:")
    print("  - Some routers block inter-device communication")
    print("  - Check router firewall settings")
    print("  - Ensure both devices are on same network/VLAN")
    print()

def check_emulator_running(host, port):
    """Check if emulator appears to be running"""
    print()
    print("=" * 60)
    print("EMULATOR STATUS CHECK")
    print("=" * 60)
    print()
    print("On the Mac where PLC emulator should be running:")
    print()
    print("  1. Check if emulator process is running:")
    print("     ps aux | grep plc_emulator")
    print("     # or if using Docker:")
    print("     docker ps | grep plc-emulator")
    print()
    print("  2. Check if port is listening:")
    print(f"     lsof -i :{port}")
    print(f"     # Should show Python or Docker process")
    print()
    print("  3. Check emulator logs:")
    print("     # If standalone:")
    print("     # Check terminal where emulator is running")
    print("     # If Docker:")
    print("     docker-compose logs plc-emulator")
    print()
    print("  4. Verify emulator is bound to 0.0.0.0:")
    print("     # Check config.py: PLC_HOST should be '0.0.0.0'")
    print("     # Or check docker-compose.yml environment")
    print()

def main():
    """Main diagnostic function"""
    print("=" * 60)
    print("Modbus Connection Diagnostic Tool")
    print("=" * 60)
    print()
    
    # Get host and port
    if len(sys.argv) < 2:
        print("Usage: python diagnose_connection.py <host> [port]")
        print("Example: python diagnose_connection.py 192.168.1.100 5020")
        sys.exit(1)
    
    host = sys.argv[1]
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 5020
    
    print(f"Diagnosing connection to {host}:{port}")
    print()
    
    # Run tests
    ping_ok = test_ping(host)
    print()
    
    port_ok = test_port_connection(host, port)
    print()
    
    if port_ok:
        modbus_ok = test_modbus_connection(host, port)
        print()
    else:
        modbus_ok = False
        print("Skipping Modbus test (port not accessible)")
        print()
    
    # Summary
    print("=" * 60)
    print("DIAGNOSTIC SUMMARY")
    print("=" * 60)
    print()
    
    if ping_ok:
        print("✅ Ping: Working")
    else:
        print("❌ Ping: Failed")
    
    if port_ok:
        print(f"✅ Port {port}: Accessible")
    else:
        print(f"❌ Port {port}: NOT accessible (FIREWALL ISSUE LIKELY)")
    
    if modbus_ok:
        print("✅ Modbus: Working")
        print()
        print("🎉 Everything is working! Your connection should work.")
    else:
        print("❌ Modbus: Failed")
        print()
        print("🔧 Troubleshooting needed:")
        
        if not ping_ok:
            print("  - Fix network connectivity first")
        elif not port_ok:
            print("  - Port is blocked (firewall or not listening)")
            check_firewall_suggestions(host, port)
            check_emulator_running(host, port)
        else:
            print("  - Port is open but Modbus protocol issue")
            check_emulator_running(host, port)
    
    print()

if __name__ == "__main__":
    main()


