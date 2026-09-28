#!/usr/bin/env python3
"""
Modbus TCP Server Emulator for OWEN PLC
Simulates a car wash PLC with programs, prices, and status registers
"""
import logging
import threading
import time
from typing import Dict, Optional
from pymodbus.server import StartTcpServer
from pymodbus.datastore import ModbusSequentialDataBlock, ModbusSlaveContext, ModbusServerContext
from pymodbus.transaction import ModbusRtuFramer, ModbusSocketFramer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CarWashPLCEmulator:
    """Emulates OWEN PLC for car wash system"""
    
    def __init__(self, host: str = "0.0.0.0", port: int = 502):
        self.host = host
        self.port = port
        self.server = None
        self.running = False
        
        # Initialize Modbus data blocks
        # Input registers (read-only) - programs and prices
        # Holding registers (read-write) - control registers
        # Coils (read-write) - discrete outputs
        # Discrete inputs (read-only) - status inputs
        
        # Initialize with default values
        self._init_data_store()
        
    def _init_data_store(self):
        """Initialize Modbus data store with default car wash values"""
        
        # Input registers (0-9999) - Programs and prices
        # Programs: 0-14 (Program1), 35-49 (Program2), 70-84 (Program3), 105-119 (Program4), 140-154 (Program5)
        # Prices: 30, 31, 65, 66, 100, 101, 135, 136, 170, 171
        input_registers = [0] * 200
        
        # Program 1: Basic wash (Химия 1, Ополаскивание, Сушка)
        input_registers[0:3] = [1, 4, 7]  # Химия 1, Ополаскивание, Сушка
        input_registers[30] = 200  # Price1 = 200 rubles
        input_registers[31] = 180  # LoyaltyPrice1 = 180 rubles
        
        # Program 2: Standard wash
        input_registers[35:40] = [1, 3, 4, 5, 7]  # Химия 1, Пена, Ополаскивание, Осмос, Сушка
        input_registers[65] = 300  # Price2
        input_registers[66] = 270  # LoyaltyPrice2
        
        # Program 3: Premium wash
        input_registers[70:77] = [1, 2, 3, 4, 5, 6, 7]  # All functions
        input_registers[100] = 500  # Price3
        input_registers[101] = 450  # LoyaltyPrice3
        
        # Program 4: Express wash
        input_registers[105:107] = [1, 4]  # Химия 1, Ополаскивание
        input_registers[135] = 150  # Price4
        input_registers[136] = 135  # LoyaltyPrice4
        
        # Program 5: Deluxe wash
        input_registers[140:148] = [1, 2, 3, 4, 5, 6, 7, 1]  # All functions + repeat
        input_registers[170] = 700  # Price5
        input_registers[171] = 630  # LoyaltyPrice5
        
        # Cash register (address 16388) - simulate as input register
        # We'll use holding register for this since it's at high address
        
        input_block = ModbusSequentialDataBlock(0, input_registers)
        
        # Holding registers (0-9999) - Control and status
        # Address 16388 for cash (we'll map this to a lower address for simplicity)
        # In real PLC, this might be at high address, but we'll simulate at address 200
        holding_registers = [0] * 300
        holding_block = ModbusSequentialDataBlock(0, holding_registers)
        
        # Coils (0-9999) - Start commands
        # Address 0 = StartProgram1, 1 = StartProgram2, 3 = StartProgram3, 4 = StartProgram4, 5 = StartProgram5
        coils = [False] * 100
        coil_block = ModbusSequentialDataBlock(0, coils)
        
        # Discrete inputs (0-9999) - Status
        # Address 0 = WorkProgramm (washing in progress)
        discrete_inputs = [False] * 100
        discrete_block = ModbusSequentialDataBlock(0, discrete_inputs)
        
        # Create slave context
        slave_context = ModbusSlaveContext(
            di=discrete_block,      # Discrete inputs
            co=coil_block,          # Coils
            hr=holding_block,       # Holding registers
            ir=input_block          # Input registers
        )
        
        # Create server context (single slave, unit ID = 1)
        self.context = ModbusServerContext(slaves={1: slave_context}, single=False)
        
        # Store references for runtime updates
        self._coils = coils
        self._discrete_inputs = discrete_inputs
        self._holding_registers = holding_registers
        self._input_registers = input_registers
        
        logger.info("Modbus data store initialized with default car wash programs")
    
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
        # Note: pymodbus server doesn't have a clean stop method
        # In production, you'd need to implement proper shutdown
    
    def simulate_wash_start(self, program_number: int):
        """Simulate starting a wash program"""
        if program_number < 1 or program_number > 5:
            logger.error(f"Invalid program number: {program_number}")
            return
        
        # Map program numbers to coil addresses
        coil_addresses = {1: 0, 2: 1, 3: 3, 4: 4, 5: 5}
        address = coil_addresses[program_number]
        
        # Set start coil
        self._coils[address] = True
        logger.info(f"Simulated start of Program {program_number} (coil {address})")
        
        # Update discrete input to show washing in progress
        self._discrete_inputs[0] = True
        
        # In a real scenario, you'd update the context
        # For now, this is a simplified simulation
    
    def simulate_wash_complete(self):
        """Simulate wash completion"""
        self._discrete_inputs[0] = False
        # Reset all start coils
        for addr in [0, 1, 3, 4, 5]:
            self._coils[addr] = False
        logger.info("Simulated wash completion")
    
    def simulate_cash_inserted(self, amount: int):
        """Simulate cash being inserted into bill acceptor"""
        # Map to holding register address 200 (simulating address 16388)
        self._holding_registers[200] = amount
        logger.info(f"Simulated cash inserted: {amount} rubles")
    
    def get_status(self) -> Dict:
        """Get current emulator status"""
        return {
            'running': self.running,
            'host': self.host,
            'port': self.port,
            'wash_in_progress': self._discrete_inputs[0] if self._discrete_inputs else False
        }


def main():
    """Main entry point for standalone execution"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Modbus PLC Emulator for Car Wash')
    parser.add_argument('--host', default='0.0.0.0', help='Host to bind to')
    parser.add_argument('--port', type=int, default=502, help='Port to bind to')
    
    args = parser.parse_args()
    
    emulator = CarWashPLCEmulator(host=args.host, port=args.port)
    
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

