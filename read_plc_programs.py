#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Standalone скрипт для чтения программ автомойки из OWEN PLC
Работает независимо от Django сервера
"""

import time
import json
import logging
from datetime import datetime
from typing import List, Dict, Optional
from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ModbusException


class StandaloneOwenPLCReader:
    """Standalone класс для чтения данных из OWEN PLC"""
    
    # Константы функций автомойки
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
    
    # Адреса Modbus регистров
    REGISTERS = {
        'setProgramm1': {
            'start_address': 12,  # %QW12
            'count': 15,
            'description': 'Настройки программы 1'
        },
        'quantity_CeckleProgramm1': {
            'start_address': 27,  # %QW27
            'count': 15,
            'description': 'Количество повторений программы 1'
        },
        'setProgramm2': {
            'start_address': 47,  # %QW47
            'count': 15,
            'description': 'Настройки программы 2'
        },
        'GVL_Price1': {
            'start_address': 42,  # %QW42
            'description': 'Цена программы 1'
        },
        'LoyalityPrice1': {
            'start_address': 43,  # %QW43
            'description': 'Цена по программе лояльности'
        },
        'wash_status': {
            'start_address': 101,  # %QW101
            'description': 'Статус мойки'
        },
        'current_program': {
            'start_address': 102,  # %QW102
            'description': 'Текущая выполняемая программа'
        },
        'wash_progress': {
            'start_address': 103,  # %QW103
            'description': 'Прогресс выполнения мойки (%)'
        }
    }
    
    # Статусы мойки
    WASH_STATUS = {
        0: "Свободна",
        1: "Готовится к запуску",
        2: "Выполняется",
        3: "Завершена",
        4: "Ошибка",
        5: "Остановлена"
    }
    
    def __init__(self, host: str, port: int = 502, timeout: int = 10):
        """
        Инициализация подключения к OWEN PLC
        
        Args:
            host: IP-адрес PLC
            port: Порт Modbus (по умолчанию 502)
            timeout: Таймаут подключения в секундах
        """
        self.host = host
        self.port = port
        self.timeout = timeout
        self.client = None
        self.connected = False
        
    def connect(self) -> bool:
        """Подключение к PLC"""
        try:
            print(f"🔌 Подключение к OWEN PLC {self.host}:{self.port}...")
            self.client = ModbusTcpClient(
                host=self.host,
                port=self.port,
                timeout=self.timeout
            )
            
            if self.client.connect():
                self.connected = True
                print(f"✅ Подключение к PLC установлено")
                return True
            else:
                print(f"❌ Не удалось подключиться к PLC")
                return False
                
        except Exception as e:
            print(f"❌ Ошибка подключения: {e}")
            return False
    
    def disconnect(self):
        """Отключение от PLC"""
        if self.client and self.connected:
            self.client.close()
            self.connected = False
            print("🔌 Отключение от PLC")
    
    def read_register(self, address: int) -> Optional[int]:
        """
        Чтение одного регистра
        
        Args:
            address: Адрес регистра
            
        Returns:
            Значение регистра или None при ошибке
        """
        if not self.connected:
            print("❌ Нет подключения к PLC")
            return None
            
        try:
            result = self.client.read_input_registers(address, 1)
            if result.isError():
                print(f"❌ Ошибка чтения регистра {address}: {result}")
                return None
            
            value = result.registers[0]
            return value
            
        except ModbusException as e:
            print(f"❌ Modbus ошибка при чтении регистра {address}: {e}")
            return None
        except Exception as e:
            print(f"❌ Общая ошибка при чтении регистра {address}: {e}")
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
            print("❌ Нет подключения к PLC")
            return None
            
        try:
            result = self.client.read_input_registers(start_address, count)
            if result.isError():
                print(f"❌ Ошибка чтения регистров {start_address}-{start_address+count-1}: {result}")
                return None
            
            return result.registers
            
        except ModbusException as e:
            print(f"❌ Modbus ошибка при чтении регистров: {e}")
            return None
        except Exception as e:
            print(f"❌ Общая ошибка при чтении регистров: {e}")
            return None
    
    def read_program_settings(self, program_name: str) -> Optional[Dict]:
        """
        Чтение настроек программы
        
        Args:
            program_name: Имя программы (например, 'setProgramm1')
            
        Returns:
            Словарь с настройками программы или None при ошибке
        """
        if program_name not in self.REGISTERS:
            print(f"❌ Неизвестная программа: {program_name}")
            return None
        
        program_info = self.REGISTERS[program_name]
        
        if 'count' in program_info:
            # Массив регистров
            values = self.read_registers(
                program_info['start_address'], 
                program_info['count']
            )
            
            if values is None:
                return None
            
            # Преобразуем значения в функции
            functions = []
            for i, value in enumerate(values, 1):
                if value in self.FUNCTIONS:
                    functions.append({
                        'step': i,
                        'value': value,
                        'function': self.FUNCTIONS[value],
                        'description': self.FUNCTIONS[value]
                    })
                else:
                    functions.append({
                        'step': i,
                        'value': value,
                        'function': 'Неизвестно',
                        'description': f'Неизвестная функция: {value}'
                    })
            
            return {
                'program_name': program_name,
                'description': program_info['description'],
                'start_address': program_info['start_address'],
                'count': program_info['count'],
                'functions': functions,
                'raw_values': values
            }
        else:
            # Один регистр
            value = self.read_register(program_info['start_address'])
            if value is None:
                return None
            
            return {
                'program_name': program_name,
                'description': program_info['description'],
                'start_address': program_info['start_address'],
                'value': value
            }
    
    def get_wash_status(self) -> Optional[Dict]:
        """
        Получение текущего статуса мойки
        
        Returns:
            Словарь с информацией о статусе мойки
        """
        status_value = self.read_register(self.REGISTERS['wash_status']['start_address'])
        if status_value is None:
            return None
        
        current_program = self.read_register(self.REGISTERS['current_program']['start_address'])
        progress = self.read_register(self.REGISTERS['wash_progress']['start_address'])
        
        return {
            'status_code': status_value,
            'status_text': self.WASH_STATUS.get(status_value, 'Неизвестный статус'),
            'current_program': current_program,
            'progress': progress or 0,
            'timestamp': datetime.now().isoformat()
        }
    
    def read_all_programs(self) -> Dict:
        """Чтение всех программ и настроек"""
        print("🚗 Чтение всех программ автомойки из OWEN PLC")
        print("=" * 60)
        
        all_data = {}
        
        # Читаем основные программы
        programs = ['setProgramm1', 'setProgramm2']
        for program in programs:
            print(f"\n📋 Чтение {program}...")
            data = self.read_program_settings(program)
            if data:
                all_data[program] = data
                self.print_program_info(data)
            else:
                print(f"❌ Не удалось прочитать {program}")
        
        # Читаем количество повторений
        print(f"\n🔄 Чтение количества повторений...")
        quantity_data = self.read_program_settings('quantity_CeckleProgramm1')
        if quantity_data:
            all_data['quantity_CeckleProgramm1'] = quantity_data
            self.print_quantity_info(quantity_data)
        else:
            print(f"❌ Не удалось прочитать количество повторений")
        
        # Читаем цены
        print(f"\n💰 Чтение цен...")
        price_data = self.read_program_settings('GVL_Price1')
        if price_data:
            all_data['GVL_Price1'] = price_data
            print(f"   Цена программы 1: {price_data['value']}")
        else:
            print(f"   ❌ Не удалось прочитать цену программы 1")
        
        loyalty_data = self.read_program_settings('LoyalityPrice1')
        if loyalty_data:
            all_data['LoyalityPrice1'] = loyalty_data
            print(f"   Цена по программе лояльности: {loyalty_data['value']}")
        else:
            print(f"   ❌ Не удалось прочитать цену по программе лояльности")
        
        # Читаем текущий статус
        print(f"\n📊 Чтение текущего статуса...")
        status_data = self.get_wash_status()
        if status_data:
            all_data['current_status'] = status_data
            print(f"   Статус: {status_data['status_text']} (код: {status_data['status_code']})")
            print(f"   Текущая программа: {status_data['current_program']}")
            print(f"   Прогресс: {status_data['progress']}%")
        else:
            print(f"   ❌ Не удалось получить статус мойки")
        
        return all_data
    
    def print_program_info(self, program_data: Dict):
        """Вывод информации о программе"""
        print(f"📋 {program_data['description']}")
        print(f"   Адрес: %QW{program_data['start_address']}")
        print(f"   Количество шагов: {program_data['count']}")
        print("   Последовательность функций:")
        
        for func in program_data['functions']:
            print(f"     Шаг {func['step']:2d}: {func['function']} (код: {func['value']})")
    
    def print_quantity_info(self, quantity_data: Dict):
        """Вывод информации о количестве повторений"""
        print(f"🔄 {quantity_data['description']}")
        print(f"   Адрес: %QW{quantity_data['start_address']}")
        print("   Количество повторений по шагам:")
        
        for func in quantity_data['functions']:
            print(f"     Шаг {func['step']:2d}: {func['value']} повторений")
    
    def save_to_file(self, data: Dict, filename: str = None):
        """Сохранение данных в файл"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"plc_programs_{timestamp}.json"
        
        try:
            # Подготавливаем данные для JSON
            json_data = {
                'timestamp': datetime.now().isoformat(),
                'plc_host': self.host,
                'plc_port': self.port,
                'data': data
            }
            
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(json_data, f, ensure_ascii=False, indent=2)
            
            print(f"💾 Данные сохранены в файл: {filename}")
            
        except Exception as e:
            print(f"❌ Ошибка сохранения в файл: {e}")
    
    def save_to_text_file(self, data: Dict, filename: str = None):
        """Сохранение данных в текстовый файл"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"plc_programs_{timestamp}.txt"
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write("Данные OWEN PLC - Роботизированная автомойка\n")
                f.write("=" * 50 + "\n")
                f.write(f"Дата/время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"PLC: {self.host}:{self.port}\n\n")
                
                for key, value in data.items():
                    f.write(f"{key}:\n")
                    if isinstance(value, dict):
                        if 'functions' in value:
                            f.write(f"  {value['description']}\n")
                            f.write(f"  Адрес: %QW{value['start_address']}\n")
                            for func in value['functions']:
                                f.write(f"  Шаг {func['step']:2d}: {func['function']} (код: {func['value']})\n")
                        else:
                            f.write(f"  {value['description']}\n")
                            f.write(f"  Адрес: %QW{value['start_address']}\n")
                            f.write(f"  Значение: {value['value']}\n")
                    f.write("\n")
            
            print(f"💾 Данные сохранены в текстовый файл: {filename}")
            
        except Exception as e:
            print(f"❌ Ошибка сохранения в текстовый файл: {e}")


def main():
    """Главная функция"""
    print("🏗️ OWEN PLC Program Reader - Роботизированная автомойка")
    print("=" * 60)
    
    # Получаем параметры подключения
    host = input("Введите IP-адрес OWEN PLC (Enter для 192.168.1.100): ").strip()
    if not host:
        host = "192.168.1.100"
        print(f"Используется IP по умолчанию: {host}")
    
    port_input = input("Введите порт Modbus (Enter для 502): ").strip()
    if not port_input:
        port = 502
    else:
        try:
            port = int(port_input)
        except ValueError:
            print("❌ Неверный порт, используется 502")
            port = 502
    
    timeout_input = input("Введите таймаут в секундах (Enter для 10): ").strip()
    if not timeout_input:
        timeout = 10
    else:
        try:
            timeout = int(timeout_input)
        except ValueError:
            print("❌ Неверный таймаут, используется 10")
            timeout = 10
    
    # Создаем экземпляр
    plc = StandaloneOwenPLCReader(host, port, timeout)
    
    try:
        # Подключаемся
        if plc.connect():
            # Читаем все данные
            data = plc.read_all_programs()
            
            # Предлагаем сохранить данные
            save_option = input("\nСохранить данные в файл? (y/n): ").strip().lower()
            if save_option in ['y', 'yes', 'да', 'д']:
                format_option = input("Формат файла (json/txt/both) [json]: ").strip().lower()
                if not format_option:
                    format_option = 'json'
                
                if format_option in ['json', 'both']:
                    plc.save_to_file(data)
                if format_option in ['txt', 'both']:
                    plc.save_to_text_file(data)
            
            print("\n✅ Чтение данных завершено!")
            
        else:
            print("❌ Не удалось подключиться к PLC")
            
    except KeyboardInterrupt:
        print("\n\n⏹️ Программа прервана пользователем")
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
    finally:
        # Отключаемся
        plc.disconnect()
        print("\nНажмите Enter для выхода...")
        input()


if __name__ == "__main__":
    main()
