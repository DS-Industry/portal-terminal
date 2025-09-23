#!/usr/bin/env python3
"""
Simple Modbus TCP client for OWEN PLC
Car wash program and price reader
"""

import logging
from typing import List, Dict, Optional
from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ModbusException
from django.conf import settings

# Import configuration
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from modbus_config import FUNCTIONS, REGISTERS, DEFAULT_HOST, DEFAULT_PORT, DEFAULT_TIMEOUT

logger = logging.getLogger(__name__)


class ModbusClient:
    """Simple Modbus client for PLC communication"""
    
    def __init__(self, host: str = None, port: int = None, timeout: int = None):
        self.host = host or getattr(settings, 'MODBUS_HOST', DEFAULT_HOST)
        self.port = port or getattr(settings, 'MODBUS_PORT', DEFAULT_PORT)
        self.timeout = timeout or getattr(settings, 'MODBUS_TIMEOUT', DEFAULT_TIMEOUT)
        self.client = None
        self.connected = False
        
    def connect(self) -> bool:
        """Connect to PLC"""
        try:
            logger.info(f"Connecting to PLC {self.host}:{self.port}")
            self.client = ModbusTcpClient(
                host=self.host,
                port=self.port,
                timeout=self.timeout
            )
            
            if self.client.connect():
                self.connected = True
                logger.info("Connected to PLC")
                return True
            else:
                logger.error("Failed to connect to PLC")
                return False
                
        except Exception as e:
            logger.error(f"Connection error: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from PLC"""
        if self.client and self.connected:
            self.client.close()
            self.connected = False
            logger.info("Disconnected from PLC")
    
    def read_register(self, address: int) -> Optional[int]:
        """Read single register"""
        if not self.connected:
            logger.error("Not connected to PLC")
            return None
            
        try:
            result = self.client.read_input_registers(address, 1)
            if result.isError():
                logger.error(f"Error reading register {address}")
                return None
            return result.registers[0]
        except Exception as e:
            logger.error(f"Error reading register {address}: {e}")
            return None
    
    def read_registers(self, start_address: int, count: int) -> Optional[List[int]]:
        """Read multiple registers"""
        if not self.connected:
            logger.error("Not connected to PLC")
            return None
            
        try:
            result = self.client.read_input_registers(start_address, count)
            if result.isError():
                logger.error(f"Error reading registers {start_address}-{start_address+count-1}")
                return None
            return result.registers
        except Exception as e:
            logger.error(f"Error reading registers: {e}")
            return None
    
    def read_program(self, program_name: str) -> Optional[Dict]:
        """Read car wash program"""
        if program_name not in REGISTERS:
            logger.error(f"Unknown program: {program_name}")
            return None
        
        program_info = REGISTERS[program_name]
        
        if 'count' not in program_info:
            logger.error(f"{program_name} is not a program")
            return None
        
        values = self.read_registers(program_info['address'], program_info['count'])
        if values is None:
            return None
        
        # Convert values to functions
        functions = []
        for i, value in enumerate(values, 1):
            function_name = FUNCTIONS.get(value, 'Unknown')
            if function_name != FUNCTIONS.get(0):
                if (i == 1):
                    function_name = 'Мойка-днища'
                functions.append({
                    'step': i,
                    'value': value,
                    'function': function_name
                })
        
        return {
            'program_name': program_name,
            'functions': functions
        }
    
    def read_program_price(self, program_number: int) -> Optional[Dict]:
        """Read program prices"""
        if program_number not in range(1, 6):
            logger.error(f"Invalid program number: {program_number}")
            return None
        
        price_key = f'Price{program_number}'
        loyalty_key = f'LoyaltyPrice{program_number}'
        
        if price_key not in REGISTERS or loyalty_key not in REGISTERS:
            logger.error(f"Price registers not found for program {program_number}")
            return None
        
        regular_price = self.read_register(REGISTERS[price_key]['address'])
        loyalty_price = self.read_register(REGISTERS[loyalty_key]['address'])
        
        if regular_price is None or loyalty_price is None:
            logger.error(f"Failed to read prices for program {program_number}")
            return None
        
        return {
            'program_number': program_number,
            'regular_price': regular_price,
            'loyalty_price': loyalty_price
        }
    
    def read_all_programs(self) -> Dict:
        """Read all programs"""
        logger.info("Reading all car wash programs")
        all_data = {}
        
        for i in range(1, 6):
            program_name = f'Program{i}'
            data = self.read_program(program_name)
            if data:
                all_data[program_name] = data
                logger.info(f"Read {program_name}: {len(data['functions'])} steps")
            else:
                logger.error(f"Failed to read {program_name}")
        
        return all_data
    
    def read_all_prices(self) -> Dict:
        """Read all program prices"""
        logger.info("Reading all program prices")
        all_prices = {}
        
        for i in range(1, 6):
            price_data = self.read_program_price(i)
            if price_data:
                all_prices[f'Program{i}'] = price_data
                logger.info(f"Program {i}: regular={price_data['regular_price']}, loyalty={price_data['loyalty_price']}")
            else:
                logger.error(f"Failed to read prices for program {i}")
        
        return all_prices
    
    def test_connection(self) -> bool:
        """Test PLC connection"""
        try:
            if not self.connect():
                return False
            
            test_value = self.read_register(0)
            if test_value is not None:
                logger.info("Connection test successful")
                return True
            else:
                logger.error("Connection test failed")
                return False
                
        except Exception as e:
            logger.error(f"Connection test error: {e}")
            return False
        finally:
            self.disconnect()


def test_modbus_connection(host: str = None, port: int = None) -> bool:
    """Test Modbus connection"""
    client = ModbusClient(host, port)
    return client.test_connection()
