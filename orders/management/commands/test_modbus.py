#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Django management команда для тестирования Modbus TCP подключения
"""

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from orders.modbus_client import OwenPLCCarWash
from orders.modbus_integration_example import test_modbus_integration


class Command(BaseCommand):
    help = 'Тестирование Modbus TCP подключения к OWEN PLC'

    def add_arguments(self, parser):
        parser.add_argument(
            '--host',
            type=str,
            default=getattr(settings, 'MODBUS_HOST', '192.168.1.100'),
            help='IP-адрес OWEN PLC (по умолчанию: 192.168.1.100)'
        )
        parser.add_argument(
            '--port',
            type=int,
            default=getattr(settings, 'MODBUS_PORT', 502),
            help='Порт Modbus (по умолчанию: 502)'
        )
        parser.add_argument(
            '--timeout',
            type=int,
            default=getattr(settings, 'MODBUS_TIMEOUT', 10),
            help='Таймаут подключения в секундах (по умолчанию: 10)'
        )
        parser.add_argument(
            '--full-test',
            action='store_true',
            help='Выполнить полный тест с чтением всех данных'
        )

    def handle(self, *args, **options):
        host = options['host']
        port = options['port']
        timeout = options['timeout']
        full_test = options['full_test']

        self.stdout.write(
            self.style.SUCCESS(f'🧪 Тестирование Modbus TCP подключения к {host}:{port}')
        )
        self.stdout.write('=' * 60)

        # Создаем экземпляр PLC клиента
        plc = OwenPLCCarWash(host, port, timeout)

        try:
            # Тест 1: Базовое подключение
            self.stdout.write('🔌 Тест 1: Базовое подключение...')
            if not plc.connect():
                raise CommandError('❌ Не удалось подключиться к OWEN PLC')
            
            self.stdout.write(
                self.style.SUCCESS('✅ Подключение к PLC установлено')
            )

            # Тест 2: Чтение статуса
            self.stdout.write('\n📊 Тест 2: Чтение статуса мойки...')
            status = plc.get_wash_status()
            if status:
                self.stdout.write(f'   Статус: {status["status_text"]} (код: {status["status_code"]})')
                self.stdout.write(f'   Текущая программа: {status["current_program"]}')
                self.stdout.write(f'   Прогресс: {status["progress"]}%')
            else:
                self.stdout.write(self.style.WARNING('   ⚠️ Не удалось получить статус'))

            # Тест 3: Проверка занятости
            self.stdout.write('\n🔍 Тест 3: Проверка занятости мойки...')
            is_busy = plc.is_wash_busy()
            self.stdout.write(f'   Мойка занята: {"Да" if is_busy else "Нет"}')

            # Тест 4: Полный тест (если запрошен)
            if full_test:
                self.stdout.write('\n📋 Тест 4: Полное чтение данных...')
                try:
                    all_data = plc.read_all_programs()
                    self.stdout.write(f'   Прочитано {len(all_data)} блоков данных')
                    
                    # Показываем программы
                    for key, data in all_data.items():
                        if 'functions' in data:
                            self.stdout.write(f'   {key}: {len(data["functions"])} шагов')
                        elif 'value' in data:
                            self.stdout.write(f'   {key}: {data["value"]}')
                    
                except Exception as e:
                    self.stdout.write(
                        self.style.WARNING(f'   ⚠️ Ошибка при полном тесте: {e}')
                    )

            # Тест 5: Интеграция с системой
            self.stdout.write('\n🔗 Тест 5: Интеграция с системой...')
            try:
                from orders.modbus_integration_example import get_car_wash_controller
                controller = get_car_wash_controller()
                controller.plc = plc  # Используем уже подключенный клиент
                controller.connected = True
                
                # Тестируем методы интеграции
                busy_status = controller.is_car_wash_busy()
                self.stdout.write(f'   Интеграция работает: {"Да" if busy_status is not None else "Нет"}')
                
            except Exception as e:
                self.stdout.write(
                    self.style.WARNING(f'   ⚠️ Ошибка интеграции: {e}')
                )

            self.stdout.write(
                self.style.SUCCESS('\n🎉 Все тесты завершены успешно!')
            )
            self.stdout.write(
                'Modbus клиент готов к использованию в системе автомойки.'
            )

        except Exception as e:
            raise CommandError(f'❌ Ошибка при тестировании: {e}')

        finally:
            plc.disconnect()
            self.stdout.write('\n🔌 Подключение к PLC закрыто')

    def handle_legacy(self, *args, **options):
        """
        Альтернативный способ тестирования через модуль интеграции
        """
        self.stdout.write('🧪 Запуск тестирования через модуль интеграции...')
        
        try:
            success = test_modbus_integration()
            if success:
                self.stdout.write(
                    self.style.SUCCESS('✅ Тестирование завершено успешно!')
                )
            else:
                raise CommandError('❌ Тестирование завершилось с ошибками')
                
        except Exception as e:
            raise CommandError(f'❌ Ошибка при тестировании: {e}')
