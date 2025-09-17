#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Modbus TCP клиент для связи с OWEN PLC
Роботизированная автомойка - чтение программ и цен
"""

import time
import logging
from typing import List, Dict, Optional
from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ModbusException
from django.conf import settings

# Импортируем конфигурацию из отдельного файла
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from modbus_config import FUNCTIONS, REGISTERS, DEFAULT_HOST, DEFAULT_PORT, DEFAULT_TIMEOUT

logger = logging.getLogger(__name__)


class OwenPLCCarWash:
    """Класс для работы с OWEN PLC через Modbus TCP"""
    
    def __init__(self, host: str = None, port: int = None, timeout: int = None):
        """
        Инициализация подключения к OWEN PLC
        
        Args:
            host: IP-адрес PLC (если None, берется из настроек)
            port: Порт Modbus (если None, берется из настроек)
            timeout: Таймаут подключения в секундах
        """
        self.host = host or getattr(settings, 'MODBUS_HOST', DEFAULT_HOST)
        self.port = port or getattr(settings, 'MODBUS_PORT', DEFAULT_PORT)
        self.timeout = timeout or getattr(settings, 'MODBUS_TIMEOUT', DEFAULT_TIMEOUT)
        self.client = None
        self.connected = False
        
    def connect(self) -> bool:
        """Подключение к PLC"""
        try:
            logger.info(f"🔌 Подключение к OWEN PLC {self.host}:{self.port}...")
            self.client = ModbusTcpClient(
                host=self.host,
                port=self.port,
                timeout=self.timeout
            )
            
            if self.client.connect():
                self.connected = True
                logger.info(f"✅ Подключение к PLC установлено")
                return True
            else:
                logger.error(f"❌ Не удалось подключиться к PLC")
                return False
                
        except Exception as e:
            logger.error(f"❌ Ошибка подключения: {e}")
            return False
    
    def disconnect(self):
        """Отключение от PLC"""
        if self.client and self.connected:
            self.client.close()
            self.connected = False
            logger.info("🔌 Отключение от PLC")
    
    def read_register(self, address: int) -> Optional[int]:
        """
        Чтение одного регистра
        
        Args:
            address: Адрес регистра
            
        Returns:
            Значение регистра или None при ошибке
        """
        if not self.connected:
            logger.error("❌ Нет подключения к PLC")
            return None
            
        try:
            result = self.client.read_input_registers(address, 1)
            if result.isError():
                logger.error(f"❌ Ошибка чтения регистра {address}: {result}")
                return None
            
            value = result.registers[0]
            logger.debug(f"📖 Регистр {address}: {value}")
            return value
            
        except ModbusException as e:
            logger.error(f"❌ Modbus ошибка при чтении регистра {address}: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ Общая ошибка при чтении регистра {address}: {e}")
            return None
    
    def read_registers(self, start_address: int, count: int) -> Optional[List[int]]:
        """
        Чтение нескольких регистров
        
        Args:
            start_address: Начальный адрес
            count: Количество регистров
            
        Returns:
            Список значений регистров или None при ошибке
        """
        if not self.connected:
            logger.error("❌ Нет подключения к PLC")
            return None
            
        try:
            logger.debug(f"📖 Чтение {count} регистров начиная с {start_address}...")
            result = self.client.read_input_registers(start_address, count)
            if result.isError():
                logger.error(f"❌ Ошибка чтения регистров {start_address}-{start_address+count-1}: {result}")
                return None
            
            values = result.registers
            logger.debug(f"✅ Прочитано {len(values)} регистров")
            return values
            
        except ModbusException as e:
            logger.error(f"❌ Modbus ошибка при чтении регистров: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ Общая ошибка при чтении регистров: {e}")
            return None
    
    def read_program(self, program_name: str) -> Optional[Dict]:
        """
        Чтение программы мойки
        
        Args:
            program_name: Имя программы (например, 'Program1')
            
        Returns:
            JSON-совместимый словарь с данными программы или None при ошибке
        """
        if program_name not in REGISTERS:
            logger.error(f"❌ Неизвестная программа: {program_name}")
            return None
        
        program_info = REGISTERS[program_name]
        
        if 'count' not in program_info:
            logger.error(f"❌ {program_name} не является программой (нет count)")
            return None
        
        # Читаем массив регистров программы
        values = self.read_registers(
            program_info['address'], 
            program_info['count']
        )
        
        if values is None:
            return None
        
        # Преобразуем значения в функции
        functions = []
        for i, value in enumerate(values, 1):
            if value in FUNCTIONS:
                functions.append({
                    'step': i,
                    'value': value,
                    'function': FUNCTIONS[value]
                })
            else:
                functions.append({
                    'step': i,
                    'value': value,
                    'function': 'Неизвестно'
                })
        
        return {
            'program_name': program_name,
            'description': program_info['description'],
            'address': program_info['address'],
            'count': program_info['count'],
            'functions': functions,
            'raw_values': values
        }
    
    def get_program_price(self, program_number: int) -> Optional[Dict]:
        """
        Получение цены программы
        
        Args:
            program_number: Номер программы (1-5)
            
        Returns:
            JSON-совместимый словарь с ценами программы или None при ошибке
        """
        if program_number not in range(1, 6):
            logger.error(f"❌ Неверный номер программы: {program_number}. Допустимые значения: 1-5")
            return None
        
        price_key = f'Price{program_number}'
        loyalty_key = f'LoyaltyPrice{program_number}'
        
        if price_key not in REGISTERS or loyalty_key not in REGISTERS:
            logger.error(f"❌ Не найдены регистры для программы {program_number}")
            return None
        
        # Читаем цены
        regular_price = self.read_register(REGISTERS[price_key]['address'])
        loyalty_price = self.read_register(REGISTERS[loyalty_key]['address'])
        
        if regular_price is None or loyalty_price is None:
            logger.error(f"❌ Не удалось прочитать цены для программы {program_number}")
            return None
        
        return {
            'program_number': program_number,
            'regular_price': regular_price,
            'loyalty_price': loyalty_price,
            'price_address': REGISTERS[price_key]['address'],
            'loyalty_address': REGISTERS[loyalty_key]['address']
        }
    
    def read_all_programs(self) -> Dict:
        """Чтение всех программ мойки"""
        logger.info("🚗 Чтение всех программ автомойки из OWEN PLC")
        
        all_data = {}
        
        # Читаем все программы
        for i in range(1, 6):
            program_name = f'Program{i}'
            logger.info(f"📋 Чтение {program_name}...")
            
            data = self.read_program(program_name)
            if data:
                all_data[program_name] = data
                logger.info(f"✅ {program_name}: {len(data['functions'])} шагов")
            else:
                logger.error(f"❌ Не удалось прочитать {program_name}")
        
        return all_data
    
    def read_all_prices(self) -> Dict:
        """Чтение всех цен программ"""
        logger.info("💰 Чтение всех цен программ")
        
        all_prices = {}
        
        # Читаем цены всех программ
        for i in range(1, 6):
            price_data = self.get_program_price(i)
            if price_data:
                all_prices[f'Program{i}'] = price_data
                logger.info(f"✅ Программа {i}: обычная={price_data['regular_price']}, лояльность={price_data['loyalty_price']}")
            else:
                logger.error(f"❌ Не удалось прочитать цены программы {i}")
        
        return all_prices
    
    def get_program_json(self, program_name: str) -> Optional[Dict]:
        """
        Получение программы в JSON формате для сохранения в БД
        
        Args:
            program_name: Имя программы (например, 'Program1')
            
        Returns:
            JSON-совместимый словарь для сохранения в БД
        """
        program_data = self.read_program(program_name)
        if not program_data:
            return None
        
        # Извлекаем номер программы из имени
        program_number = int(program_name.replace('Program', ''))
        
        return {
            'program_number': program_number,
            'program_name': program_name,
            'description': program_data['description'],
            'address': program_data['address'],
            'step_count': program_data['count'],
            'steps': program_data['functions'],
            'raw_values': program_data['raw_values'],
            'created_at': None,  # Будет установлено при сохранении в БД
            'updated_at': None   # Будет установлено при сохранении в БД
        }
    
    def get_price_json(self, program_number: int) -> Optional[Dict]:
        """
        Получение цен программы в JSON формате для сохранения в БД
        
        Args:
            program_number: Номер программы (1-5)
            
        Returns:
            JSON-совместимый словарь для сохранения в БД
        """
        price_data = self.get_program_price(program_number)
        if not price_data:
            return None
        
        return {
            'program_number': program_number,
            'regular_price': price_data['regular_price'],
            'loyalty_price': price_data['loyalty_price'],
            'price_address': price_data['price_address'],
            'loyalty_address': price_data['loyalty_address'],
            'created_at': None,  # Будет установлено при сохранении в БД
            'updated_at': None   # Будет установлено при сохранении в БД
        }
    
    def get_all_programs_json(self) -> Dict:
        """
        Получение всех программ в JSON формате для сохранения в БД
        
        Returns:
            Словарь с JSON-данными всех программ
        """
        all_programs = {}
        
        for i in range(1, 6):
            program_name = f'Program{i}'
            program_json = self.get_program_json(program_name)
            if program_json:
                all_programs[program_name] = program_json
                logger.info(f"✅ {program_name}: {program_json['step_count']} шагов")
            else:
                logger.error(f"❌ Не удалось получить JSON для {program_name}")
        
        return all_programs
    
    def get_all_prices_json(self) -> Dict:
        """
        Получение всех цен в JSON формате для сохранения в БД
        
        Returns:
            Словарь с JSON-данными всех цен
        """
        all_prices = {}
        
        for i in range(1, 6):
            price_json = self.get_price_json(i)
            if price_json:
                all_prices[f'Program{i}'] = price_json
                logger.info(f"✅ Программа {i}: обычная={price_json['regular_price']}, лояльность={price_json['loyalty_price']}")
            else:
                logger.error(f"❌ Не удалось получить JSON цен для программы {i}")
        
        return all_prices
    
    def test_connection(self) -> bool:
        """
        Тест подключения к PLC
        
        Returns:
            True если подключение работает, False при ошибке
        """
        try:
            if not self.connect():
                return False
            
            # Пробуем прочитать первый регистр
            test_value = self.read_register(0)
            if test_value is not None:
                logger.info("✅ Тест подключения успешен")
                return True
            else:
                logger.error("❌ Тест подключения не удался - не удалось прочитать регистр")
                return False
                
        except Exception as e:
            logger.error(f"❌ Ошибка при тесте подключения: {e}")
            return False
        finally:
            self.disconnect()


def test_modbus_connection(host: str = None, port: int = None) -> bool:
    """
    Функция для тестирования Modbus подключения
    
    Args:
        host: IP-адрес PLC
        port: Порт Modbus
        
    Returns:
        True если подключение работает
    """
    plc = OwenPLCCarWash(host, port)
    return plc.test_connection()
