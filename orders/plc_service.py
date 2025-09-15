#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Сервис для работы с PLC данными
Читает программы из OWEN PLC и сохраняет их в базу данных
"""

import logging
from typing import Dict, List, Optional, Tuple
from django.db import transaction
from django.utils import timezone
from .modbus_client import OwenPLCCarWash
from .models import Program

logger = logging.getLogger(__name__)


class PLCDataService:
    """Сервис для работы с данными PLC"""
    
    def __init__(self, host: str = None, port: int = None, timeout: int = None):
        """
        Инициализация сервиса
        
        Args:
            host: IP-адрес PLC
            port: Порт Modbus
            timeout: Таймаут подключения
        """
        self.plc = OwenPLCCarWash(host, port, timeout)
        self.connected = False
    
    def connect(self) -> bool:
        """Подключение к PLC"""
        self.connected = self.plc.connect()
        if self.connected:
            logger.info("✅ PLC сервис подключен")
        else:
            logger.error("❌ Не удалось подключиться к PLC")
        return self.connected
    
    def disconnect(self):
        """Отключение от PLC"""
        if self.connected:
            self.plc.disconnect()
            self.connected = False
            logger.info("🔌 PLC сервис отключен")
    
    def sync_programs_from_plc(self) -> Dict[str, any]:
        """
        Синхронизация программ из PLC с базой данных
        
        Returns:
            Словарь с результатами синхронизации
        """
        if not self.connected:
            logger.error("❌ PLC не подключен")
            return {'success': False, 'error': 'PLC не подключен'}
        
        try:
            logger.info("🔄 Начинаем синхронизацию программ из PLC")
            
            # Получаем все программы из PLC
            programs_json = self.plc.get_all_programs_json()
            
            if not programs_json:
                logger.warning("⚠️ Не удалось получить программы из PLC")
                return {'success': False, 'error': 'Не удалось получить программы из PLC'}
            
            results = {
                'success': True,
                'total_programs': len(programs_json),
                'created': 0,
                'updated': 0,
                'errors': 0,
                'programs': []
            }
            
            # Обрабатываем каждую программу
            for program_name, program_data in programs_json.items():
                try:
                    result = self._sync_single_program(program_data)
                    results['programs'].append(result)
                    
                    if result['status'] == 'created':
                        results['created'] += 1
                    elif result['status'] == 'updated':
                        results['updated'] += 1
                    else:
                        results['errors'] += 1
                        
                except Exception as e:
                    logger.error(f"❌ Ошибка синхронизации программы {program_name}: {e}")
                    results['programs'].append({
                        'program_name': program_name,
                        'status': 'error',
                        'error': str(e)
                    })
                    results['errors'] += 1
            
            logger.info(f"✅ Синхронизация завершена: создано={results['created']}, обновлено={results['updated']}, ошибок={results['errors']}")
            return results
            
        except Exception as e:
            logger.error(f"❌ Критическая ошибка синхронизации: {e}")
            return {'success': False, 'error': str(e)}
    
    def _sync_single_program(self, program_data: Dict) -> Dict:
        """
        Синхронизация одной программы
        
        Args:
            program_data: JSON данные программы из PLC
            
        Returns:
            Результат синхронизации
        """
        program_number = program_data['program_number']
        program_name = f"Программа {program_number}"
        
        try:
            with transaction.atomic():
                # Ищем существующую программу по номеру
                program, created = Program.objects.get_or_create(
                    id_service=program_number,
                    defaults={
                        'name': program_name,
                        'price': 0,  # Цена будет обновлена отдельно
                        'description': program_data['description'],
                        'duration': self._calculate_duration(program_data['steps'])
                    }
                )
                
                if created:
                    logger.info(f"✅ Создана новая программа: {program_name}")
                    status = 'created'
                else:
                    # Обновляем существующую программу
                    program.name = program_name
                    program.description = program_data['description']
                    program.duration = self._calculate_duration(program_data['steps'])
                    program.save()
                    
                    logger.info(f"🔄 Обновлена программа: {program_name}")
                    status = 'updated'
                
                # Сохраняем детали программы в JSON поле (если есть)
                # Можно добавить JSONField в модель для хранения steps
                
                return {
                    'program_name': program_name,
                    'program_number': program_number,
                    'status': status,
                    'duration': program.duration,
                    'step_count': program_data['step_count']
                }
                
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения программы {program_name}: {e}")
            return {
                'program_name': program_name,
                'program_number': program_number,
                'status': 'error',
                'error': str(e)
            }
    
    def _calculate_duration(self, steps: List[Dict]) -> int:
        """
        Вычисляет длительность программы на основе шагов
        
        Args:
            steps: Список шагов программы
            
        Returns:
            Длительность в минутах
        """
        # Простая логика: каждый шаг = 1 минута
        # В реальности можно сделать более сложную логику
        active_steps = [step for step in steps if step['value'] != 0]
        return len(active_steps)
    
    def get_program_by_number(self, program_number: int) -> Optional[Program]:
        """
        Получение программы по номеру
        
        Args:
            program_number: Номер программы
            
        Returns:
            Объект Program или None
        """
        try:
            return Program.objects.get(id_service=program_number)
        except Program.DoesNotExist:
            return None
    
    def get_all_programs_from_db(self) -> List[Program]:
        """
        Получение всех программ из базы данных
        
        Returns:
            Список всех программ
        """
        return Program.objects.all().order_by('id_service')
    
    def sync_program_prices_from_plc(self) -> Dict[str, any]:
        """
        Синхронизация цен программ из PLC (будущая функциональность)
        
        Returns:
            Результат синхронизации цен
        """
        # TODO: Реализовать синхронизацию цен
        logger.info("💰 Синхронизация цен - функция в разработке")
        return {'success': False, 'error': 'Функция в разработке'}
    
    def get_plc_status(self) -> Dict:
        """
        Получение статуса PLC подключения
        
        Returns:
            Словарь со статусом
        """
        return {
            'connected': self.connected,
            'host': self.plc.host,
            'port': self.plc.port,
            'timeout': self.plc.timeout
        }


# Глобальный экземпляр сервиса
_plc_service = None


def get_plc_service() -> PLCDataService:
    """
    Получение глобального экземпляра PLC сервиса
    
    Returns:
        Экземпляр PLCDataService
    """
    global _plc_service
    if _plc_service is None:
        _plc_service = PLCDataService()
    return _plc_service


def sync_programs_from_plc() -> Dict[str, any]:
    """
    Функция для синхронизации программ из PLC
    
    Returns:
        Результат синхронизации
    """
    service = get_plc_service()
    
    if not service.connected:
        if not service.connect():
            return {'success': False, 'error': 'Не удалось подключиться к PLC'}
    
    try:
        return service.sync_programs_from_plc()
    finally:
        # Не отключаемся, оставляем соединение для повторного использования
        pass


if __name__ == "__main__":
    # Настройка логирования
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
