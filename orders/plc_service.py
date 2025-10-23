#!/usr/bin/env python3
"""
Simple PLC service for syncing programs from OWEN PLC to database
"""

import logging
from typing import Dict, List, Optional
from django.db import transaction
from .modbus_client import ModbusClient
from .models import Program

logger = logging.getLogger(__name__)
from modbus_config import DEFAULT_HOST_PLC, DEFAULT_PORT_PLC, DEFAULT_TIMEOUT_PLC, WASH_STATUS_REGISTER


class PLCService:
    """Simple PLC service for program synchronization"""

    def __init__(self, host: str, port: int, timeout: int):
        self.client = ModbusClient(host, port, timeout)
        self.connected = False

    def connect(self) -> bool:
        """Connect to PLC"""
        self.connected = self.client.connect()
        if self.connected:
            logger.info("Connected to PLC")
        else:
            logger.error("Failed to connect to PLC")
        return self.connected

    def disconnect(self):
        """Disconnect from PLC"""
        if self.connected:
            self.client.disconnect()
            self.connected = False
            logger.info("Disconnected from PLC")

    def sync_programs(self) -> Dict:
        """Sync all programs from PLC to database"""
        if not self.connected:
            logger.error("PLC not connected")
            return {'success': False, 'error': 'PLC not connected'}

        try:
            logger.info("Starting program sync from PLC")

            # Get all programs from PLC
            programs_data = self.client.read_all_programs()

            if not programs_data:
                logger.warning("No programs received from PLC")
                return {'success': False, 'error': 'No programs received from PLC'}

            # Get all prices from PLC
            prices_data = self.client.read_all_prices()

            results = {
                'success': True,
                'total_programs': len(programs_data),
                'created': 0,
                'updated': 0,
                'errors': 0
            }

            # Process each program
            for program_name, program_data in programs_data.items():
                try:
                    # Get price for this program
                    program_number = int(program_name.replace('Program', ''))
                    price_data = prices_data.get(program_name, {})
                    regular_price = price_data.get('regular_price', 0)

                    result = self._sync_program(program_data, regular_price)
                    if result['status'] == 'created':
                        results['created'] += 1
                    elif result['status'] == 'updated':
                        results['updated'] += 1
                    else:
                        results['errors'] += 1

                except Exception as e:
                    logger.error(f"Error syncing program {program_name}: {e}")
                    results['errors'] += 1

            logger.info(
                f"Sync completed: created={results['created']}, updated={results['updated']}, errors={results['errors']}")
            return results

        except Exception as e:
            logger.error(f"Critical sync error: {e}")
            return {'success': False, 'error': str(e)}

    def _sync_program(self, program_data: Dict, price: float = 0) -> Dict:
        """Sync single program to database"""
        program_number = int(program_data['program_name'].replace('Program', ''))
        program_name = f"Program {program_number}"

        try:
            with transaction.atomic():
                # Extract function names from steps (functions is array of objects)
                functions_list = self._extract_functions(program_data['functions'])
                functions_string = ', '.join(functions_list) if functions_list else ''

                # Create or update program
                program, created = Program.objects.get_or_create(
                    id_service=program_number,
                    defaults={
                        'name': program_name,
                        'price': price,
                        'description': f"Program {program_number} from PLC",
                        'duration': len(functions_list),
                        'functions': functions_string
                    }
                )

                if created:
                    logger.info(f"Created new program: {program_name} (price: {price})")
                    status = 'created'
                else:
                    # Update existing program with new price and functions
                    program.price = price
                    program.functions = functions_string
                    program.save()
                    logger.info(f"Updated program: {program_name} (price: {price})")
                    status = 'updated'

                return {
                    'program_name': program_name,
                    'program_number': program_number,
                    'status': status,
                    'price': price,
                    'functions': functions_list
                }

        except Exception as e:
            logger.error(f"Error saving program {program_name}: {e}")
            return {
                'program_name': program_name,
                'program_number': program_number,
                'status': 'error',
                'error': str(e)
            }

    def _extract_functions(self, functions: List[Dict]) -> List[str]:
        """Extract functions from program steps (preserving order and duplicates)"""
        functions_list = []
        for func in functions:
            if 'function' in func and func['function'] and func['function'] != 'Unknown':
                function_name = func['function']
                functions_list.append(function_name)
        return functions_list

    def get_program_by_number(self, program_number: int) -> Optional[Program]:
        """Get program by number"""
        try:
            return Program.objects.get(id=program_number)
        except Program.DoesNotExist:
            return None

    def get_all_programs(self) -> List[Program]:
        """Get all programs from database"""
        return Program.objects.all().order_by('id_service')

    def get_status(self) -> Dict:
        """Get PLC connection status"""
        return {
            'connected': self.connected,
            'host': self.client.host,
            'port': self.client.port
        }
    
    def start_program(self, program) -> bool:
        try:

            address = program.plc_start_write_address
            if address is None:
                logger.error(
                    f"Program {program.id} has invalid plc_start_write_address: {address}"
                )
                return False

            return self.client.write_coil(address, True)
        except Exception as e:
            logger.error(f"Error starting program {program.id}: {e}")
            return False

    def get_wash_status(self) -> Optional[bool]:
        """

        Returns:
            bool: True - мойка идет, False - мойка завершена
            None: ошибка чтения
        """
        if not self.connected:
            logger.error("Not connected to PLC")
            return None

        try:
            register_value_a = self.client.read_coil(2991)
            print(f"[WASH] WASH_STATUS_REGISTER={2991} на {register_value_a}")

            register_value_b = self.client.read_coil(2993)
            print(f"[WASH] WASH_STATUS_REGISTER={2993} на {register_value_b}")

            register_value_c = self.client.read_coil(374)
            print(f"[WASH] WASH_STATUS_REGISTER={374} на {register_value_c}")

            register_value_d = self.client.read_coil(374*8)
            print(f"[WASH] WASH_STATUS_REGISTER={374*8} на {register_value_d}")

            if register_value_a is None:
                logger.error(f"Failed to read wash status from register {375}")
                return None

            wash_in_progress = (register_value_a & 0x01) == 1

            print(f"[WASH] Holding register 375 value: {register_value_a} (binary: {bin(register_value_a)}), WorkProgramm (bit0): {wash_in_progress}")
            return wash_in_progress

        except Exception as e:
            logger.error(f"Error reading wash status: {e}")
            return None


def sync_programs_from_plc() -> Dict:
    """Sync programs from PLC to database"""
    service = PLCService(DEFAULT_HOST_PLC, DEFAULT_PORT_PLC, DEFAULT_TIMEOUT_PLC)

    if not service.connect():
        return {'success': False, 'error': 'Failed to connect to PLC'}

    try:
        return service.sync_programs()
    finally:
        service.disconnect()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
