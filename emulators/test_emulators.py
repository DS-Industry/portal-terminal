#!/usr/bin/env python3
"""
Test script to verify hardware emulators are working correctly
"""
import sys
import time
import socket

def test_plc_emulator(host='localhost', port=5020):
    """Test PLC emulator connection and basic operations"""
    print(f"\n🔧 Testing PLC Emulator at {host}:{port}...")
    
    try:
        from pymodbus.client import ModbusTcpClient
        
        client = ModbusTcpClient(host=host, port=port, timeout=5)
        
        if not client.connect():
            print("❌ Failed to connect to PLC emulator")
            return False
        
        print("✅ Connected to PLC emulator")
        
        # Test reading program 1
        result = client.read_input_registers(0, 15)
        if result.isError():
            print("❌ Failed to read program 1")
            return False
        print(f"✅ Program 1 read: {result.registers[:5]}... (first 5 registers)")
        
        # Test reading price
        result = client.read_input_registers(30, 1)
        if result.isError():
            print("❌ Failed to read price")
            return False
        print(f"✅ Price 1: {result.registers[0]} rubles")
        
        # Test reading discrete input (wash status)
        result = client.read_discrete_inputs(0, 1)
        if result.isError():
            print("❌ Failed to read wash status")
            return False
        print(f"✅ Wash status: {'In progress' if result.bits[0] else 'Idle'}")
        
        # Test writing coil (start program)
        result = client.write_coil(0, True)
        if result.isError():
            print("❌ Failed to write start coil")
            return False
        print("✅ Start command sent")
        
        client.close()
        print("✅ PLC emulator test passed!\n")
        return True
        
    except ImportError:
        print("❌ pymodbus not installed. Install with: pip install pymodbus")
        return False
    except Exception as e:
        print(f"❌ PLC emulator test failed: {e}")
        return False


def test_pos_emulator(host='localhost', port=4001):
    """Test POS emulator connection"""
    print(f"\n💳 Testing POS Emulator at {host}:{port}...")
    
    try:
        # Test TCP connection
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex((host, port))
        sock.close()
        
        if result != 0:
            print(f"❌ Failed to connect to POS emulator (error code: {result})")
            return False
        
        print("✅ Connected to POS emulator")
        
        # Test with actual Vendotek client if available
        try:
            sys.path.insert(0, '..')
            from orders.vendotek import VendotekClient
            
            client = VendotekClient(ip_address=host, port=port, timeout=5)
            
            if not client.connect():
                print("❌ Failed to establish Vendotek connection")
                return False
            
            print("✅ Vendotek client connected")
            
            # Test IDL message
            response = client.send_idl()
            if not response.success:
                print(f"❌ IDL message failed: {response.error_message}")
                client.disconnect()
                return False
            
            print(f"✅ IDL response received: operation_number={response.operation_number}")
            
            client.disconnect()
            print("✅ POS emulator test passed!\n")
            return True
            
        except ImportError:
            print("⚠️  Vendotek client not available, but TCP connection works")
            print("✅ POS emulator test passed (basic connection)!\n")
            return True
            
    except Exception as e:
        print(f"❌ POS emulator test failed: {e}")
        return False


def main():
    """Run all emulator tests"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Test hardware emulators')
    parser.add_argument('--plc-host', default='localhost', help='PLC emulator host')
    parser.add_argument('--plc-port', type=int, default=5020, help='PLC emulator port')
    parser.add_argument('--pos-host', default='localhost', help='POS emulator host')
    parser.add_argument('--pos-port', type=int, default=4001, help='POS emulator port')
    parser.add_argument('--plc-only', action='store_true', help='Test only PLC emulator')
    parser.add_argument('--pos-only', action='store_true', help='Test only POS emulator')
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("Hardware Emulator Test Suite")
    print("=" * 60)
    
    results = []
    
    if not args.pos_only:
        results.append(('PLC', test_plc_emulator(args.plc_host, args.plc_port)))
    
    if not args.plc_only:
        results.append(('POS', test_pos_emulator(args.pos_host, args.pos_port)))
    
    print("=" * 60)
    print("Test Results:")
    print("=" * 60)
    
    all_passed = True
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{name:10} {status}")
        if not passed:
            all_passed = False
    
    print("=" * 60)
    
    if all_passed:
        print("🎉 All tests passed!")
        sys.exit(0)
    else:
        print("⚠️  Some tests failed. Check emulator logs.")
        sys.exit(1)


if __name__ == "__main__":
    main()

