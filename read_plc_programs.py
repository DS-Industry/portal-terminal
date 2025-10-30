#!/usr/bin/env python3
"""
Simple PLC Register Reader
Connects to OWEN PLC and reads car wash program registers
"""

from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ModbusException

# Car wash functions mapping
FUNCTIONS = {
    0: "Нет",
    1: "Химия 1", 
    2: "Химия 2",
    3: "Пена",
    4: "Ополаскивание",
    5: "Осмос",
    6: "Воск",
    7: "Сушка"
}

# Register addresses for programs
PROGRAM_ADDRESSES = {
    'Program1': {'address': 0, 'count': 15},
    'Program2': {'address': 35, 'count': 15},
    'Program3': {'address': 70, 'count': 15},
    'Program4': {'address': 105, 'count': 15},
    'Program5': {'address': 140, 'count': 15}
}

# Price register addresses
PRICE_ADDRESSES = {
    'Price1': 30,
    'LoyaltyPrice1': 31,
    'Price2': 65,
    'LoyaltyPrice2': 66,
    'Price3': 100,
    'LoyaltyPrice3': 101,
    'Price4': 135,
    'LoyaltyPrice4': 136,
    'Price5': 170,
    'LoyaltyPrice5': 171
}

def connect_to_plc(host, port=502):
    """Connect to PLC and return client"""
    print(f"Connecting to PLC {host}:{port}...")
    client = ModbusTcpClient(host=host, port=port, timeout=10)
    
    if client.connect():
        print("✅ Connected to PLC")
        return client
    else:
        print("❌ Failed to connect to PLC")
        return None

def read_register(client, address):
    """Read single register"""
    try:
        result = client.read_input_registers(address, 1)
        if result.isError():
            print(f"❌ Error reading register {address}")
            return None
        return result.registers[0]
    except Exception as e:
        print(f"❌ Error reading register {address}: {e}")
        return None

def read_registers(client, start_address, count):
    """Read multiple registers"""
    try:
        result = client.read_input_registers(start_address, count)
        if result.isError():
            print(f"❌ Error reading registers {start_address}-{start_address+count-1}")
            return None
        return result.registers
    except Exception as e:
        print(f"❌ Error reading registers: {e}")
        return None

def read_program(client, program_name, address, count):
    """Read car wash program steps"""
    print(f"\n📋 Reading {program_name}...")
    values = read_registers(client, address, count)
    
    if values is None:
        print(f"❌ Failed to read {program_name}")
        return
    
    print(f"Program: {program_name} (Address: {address}, Steps: {count})")
    print("-" * 40)
    
    for i, value in enumerate(values, 1):

        function_name = FUNCTIONS.get(value, f"Unknown ({value})")

        if (function_name != FUNCTIONS.get(0)):
            if (i == 1):
                function_name = 'Мойка-днища'
            print(f"  Step {i:2d}: {function_name} (code: {value})")
    

def read_prices(client):
    """Read all program prices"""
    print(f"\n💰 Reading prices...")
    print("-" * 40)
    
    for price_name, address in PRICE_ADDRESSES.items():
        value = read_register(client, address)
        if value is not None:
            print(f"  {price_name}: {value}")
        else:
            print(f"  ❌ Failed to read {price_name}")

def main():
    """Main function"""
    print("🏗️ OWEN PLC Register Reader")
    print("=" * 50)
    
    # PLC connection details - change IP as needed
    PLC_HOST = "192.168.53.120"  # Change this to your PLC IP
    PLC_PORT = 502
    
    # Connect to PLC
    client = connect_to_plc(PLC_HOST, PLC_PORT)
    if not client:
        return
    
    try:
        # Read all programs
        for program_name, info in PROGRAM_ADDRESSES.items():
            read_program(client, program_name, info['address'], info['count'])
        
        # Read prices
        read_prices(client)
        
        print(f"\n✅ Reading completed!")
        
    except KeyboardInterrupt:
        print("\n⏹️ Interrupted by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
    finally:
        client.close()
        print("🔌 Disconnected from PLC")

if __name__ == "__main__":
    main()
