#!/usr/bin/env python3
"""
Modbus TCP Server Emulator for OWEN PLC
Simulates a car wash PLC with programs, prices, and status registers
"""
import logging
import threading
import time
import os
from typing import Dict, Optional
from pymodbus.server import StartTcpServer
from pymodbus.datastore import ModbusSequentialDataBlock, ModbusSlaveContext, ModbusServerContext
from pymodbus.transaction import ModbusSocketFramer

# Import configuration
try:
    from config import PLCConfig
except ImportError:
    # Fallback if config not found
    class PLCConfig:
        HOST = os.getenv('PLC_HOST', '0.0.0.0')
        PORT = int(os.getenv('PLC_PORT', '502'))
        UNIT_ID = int(os.getenv('PLC_UNIT_ID', '1'))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class CarWashPLCEmulator:
    """Emulates OWEN PLC for car wash system"""
    
    def __init__(self, host: str = None, port: int = None, unit_id: int = None):
        # Handle None values and ensure proper types
        self.host = host if host is not None else PLCConfig.HOST
        try:
            self.port = int(port) if port is not None else PLCConfig.PORT
        except (ValueError, TypeError):
            logger.warning(f"Invalid port value: {port}, using config default: {PLCConfig.PORT}")
            self.port = PLCConfig.PORT
        
        try:
            self.unit_id = int(unit_id) if unit_id is not None else PLCConfig.UNIT_ID
        except (ValueError, TypeError):
            logger.warning(f"Invalid unit_id value: {unit_id}, using config default: {PLCConfig.UNIT_ID}")
            self.unit_id = PLCConfig.UNIT_ID
        self.server = None
        self.running = False
        
        # Initialize Modbus data blocks
        self._init_data_store()
        
    def _init_data_store(self):
        """Initialize Modbus data store with car wash values from config"""
        
        # Get configuration
        programs = PLCConfig.PROGRAMS
        prices = PLCConfig.PRICES
        register_map = PLCConfig.REGISTER_MAP
        
        # Calculate max address needed
        max_address = max(
            register_map['programs']['max_address'],
            register_map['prices']['max_address'],
            register_map['cash']['address'],
            register_map['coils']['max_address']
        )
        
        # Input registers (0-9999) - Programs and prices (read-only)
        input_registers = [0] * (max_address + 50)  # Extra buffer
        
        # Populate programs
        for prog_num, program in programs.items():
            start_addr = register_map['programs']['start_addresses'][prog_num]
            steps = program['steps']
            for i, step in enumerate(steps):
                if start_addr + i < len(input_registers):
                    input_registers[start_addr + i] = step
        
        # Populate prices
        for price_key, price_addr in register_map['prices']['addresses'].items():
            if 'Price' in price_key and not 'Loyalty' in price_key:
                # Regular price
                prog_num = int(price_key.replace('Price', ''))
                if prog_num in prices:
                    input_registers[price_addr] = prices[prog_num]['regular']
            elif 'LoyaltyPrice' in price_key:
                # Loyalty price
                prog_num = int(price_key.replace('LoyaltyPrice', ''))
                if prog_num in prices:
                    input_registers[price_addr] = prices[prog_num]['loyalty']
        
        input_block = ModbusSequentialDataBlock(0, input_registers)
        
        # Holding registers (0-9999) - Control and cash (read-write)
        holding_size = register_map['cash']['address'] + 10
        holding_registers = [0] * holding_size
        holding_block = ModbusSequentialDataBlock(0, holding_registers)
        
        # Coils (0-9999) - Start commands (read-write)
        coil_size = register_map['coils']['max_address'] + 10
        coils = [False] * coil_size
        coil_block = ModbusSequentialDataBlock(0, coils)
        
        # Discrete inputs (0-9999) - Status (read-only)
        discrete_size = register_map['discrete_inputs']['max_address'] + 10
        discrete_inputs = [False] * discrete_size
        discrete_block = ModbusSequentialDataBlock(0, discrete_inputs)
        
        # Create slave context
        slave_context = ModbusSlaveContext(
            di=discrete_block,      # Discrete inputs
            co=coil_block,          # Coils
            hr=holding_block,       # Holding registers
            ir=input_block          # Input registers
        )
        
        # Create server context
        self.context = ModbusServerContext(slaves={self.unit_id: slave_context}, single=False)
        
        # Store references for runtime updates
        self._coils = coils
        self._discrete_inputs = discrete_inputs
        self._holding_registers = holding_registers
        self._input_registers = input_registers
        self._register_map = register_map
        
        logger.info(f"Modbus data store initialized with {len(programs)} programs")
        logger.info(f"Server will listen on {self.host}:{self.port} (Unit ID: {self.unit_id})")
    
    def start(self):
        """Start the Modbus TCP server"""
        if self.running:
            logger.warning("Server is already running")
            return
        
        try:
            logger.info(f"Starting Modbus TCP server on {self.host}:{self.port}")
            self.running = True
            
            # Start server in a separate thread
            server_thread = threading.Thread(
                target=self._run_server,
                daemon=True
            )
            server_thread.start()
            
            # Wait a bit for server to start
            time.sleep(1)
            logger.info(f"✅ Modbus TCP server started on {self.host}:{self.port}")
            
        except Exception as e:
            logger.error(f"Failed to start server: {e}")
            self.running = False
            raise
    
    def _run_server(self):
        """Run the Modbus server (blocking)"""
        try:
            StartTcpServer(
                context=self.context,
                address=(self.host, self.port),
                framer=ModbusSocketFramer
            )
        except Exception as e:
            logger.error(f"Server error: {e}")
            self.running = False
    
    def stop(self):
        """Stop the Modbus TCP server"""
        if not self.running:
            return
        
        logger.info("Stopping Modbus TCP server...")
        self.running = False
    
    def simulate_wash_start(self, program_number: int):
        """Simulate starting a wash program"""
        coil_addresses = self._register_map['coils']['start_addresses']
        if program_number not in coil_addresses:
            logger.error(f"Invalid program number: {program_number}")
            return
        
        address = coil_addresses[program_number]
        self._coils[address] = True
        logger.info(f"Simulated start of Program {program_number} (coil {address})")
        
        # Update discrete input to show washing in progress
        status_addr = self._register_map['discrete_inputs']['wash_status']
        self._discrete_inputs[status_addr] = True
    
    def simulate_wash_complete(self):
        """Simulate wash completion"""
        status_addr = self._register_map['discrete_inputs']['wash_status']
        self._discrete_inputs[status_addr] = False
        
        # Reset all start coils
        for addr in self._register_map['coils']['start_addresses'].values():
            self._coils[addr] = False
        logger.info("Simulated wash completion")
    
    def simulate_cash_inserted(self, amount: int):
        """Simulate cash being inserted into bill acceptor"""
        cash_addr = self._register_map['cash']['address']
        self._holding_registers[cash_addr] = amount
        logger.info(f"Simulated cash inserted: {amount} rubles")
    
    def get_status(self) -> Dict:
        """Get current emulator status"""
        status_addr = self._register_map['discrete_inputs']['wash_status']
        return {
            'running': self.running,
            'host': self.host,
            'port': self.port,
            'unit_id': self.unit_id,
            'wash_in_progress': self._discrete_inputs[status_addr] if self._discrete_inputs else False
        }


def main():
    """Main entry point for standalone execution"""
    import argparse
    import sys
    
    parser = argparse.ArgumentParser(description='Modbus PLC Emulator for Car Wash')
    parser.add_argument('--host', default=None, help='Host to bind to (overrides config)')
    parser.add_argument('--port', type=int, default=None, help='Port to bind to (overrides config)')
    parser.add_argument('--unit-id', type=int, default=None, help='Modbus unit ID (overrides config)')
    
    # Parse only known arguments to avoid errors with environment variables
    # This is important for Windows Docker compatibility
    args, unknown = parser.parse_known_args()
    
    # Log any unknown arguments (for debugging, but don't fail)
    if unknown:
        logger.debug(f"Ignoring unknown arguments: {unknown}")
    
    # Ensure port is valid integer if provided
    port = None
    if args.port is not None:
        try:
            port = int(args.port)
        except (ValueError, TypeError):
            logger.warning(f"Invalid port value: {args.port}, using config default")
            port = None
    
    # Ensure unit_id is valid integer if provided
    unit_id = None
    if args.unit_id is not None:
        try:
            unit_id = int(args.unit_id)
        except (ValueError, TypeError):
            logger.warning(f"Invalid unit_id value: {args.unit_id}, using config default")
            unit_id = None
    
    emulator = CarWashPLCEmulator(
        host=args.host,
        port=port,
        unit_id=unit_id
    )
    
    try:
        emulator.start()
        logger.info("Emulator running. Press Ctrl+C to stop.")
        while emulator.running:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Stopping emulator...")
        emulator.stop()


if __name__ == "__main__":
    main()

