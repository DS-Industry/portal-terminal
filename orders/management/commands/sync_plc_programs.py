#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Django management команда для синхронизации программ из PLC
"""

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from orders.plc_service import get_plc_service, sync_programs_from_plc


class Command(BaseCommand):
    help = 'Синхронизация программ мойки из OWEN PLC с базой данных'

    def add_arguments(self, parser):
        parser.add_argument(
            '--host',
            type=str,
            default=getattr(settings, 'MODBUS_HOST', '192.168.53.120'),
            help='IP-адрес OWEN PLC'
        )
        parser.add_argument(
            '--port',
            type=int,
            default=getattr(settings, 'MODBUS_PORT', 502),
            help='Порт Modbus'
        )
        parser.add_argument(
            '--timeout',
            type=int,
            default=getattr(settings, 'MODBUS_TIMEOUT', 10),
            help='Таймаут подключения в секундах'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Только показать что будет синхронизировано, не сохранять в БД'
        )

    def handle(self, *args, **options):
        host = options['host']
        port = options['port']
        timeout = options['timeout']
        dry_run = options['dry_run']

        self.stdout.write(
            self.style.SUCCESS(f'🔄 Синхронизация программ из PLC {host}:{port}')
        )
        self.stdout.write('=' * 60)

        # Получаем сервис
        service = get_plc_service()
        service.plc.host = host
        service.plc.port = port
        service.plc.timeout = timeout

        try:
            # Подключаемся к PLC
            if not service.connect():
                raise CommandError('❌ Не удалось подключиться к PLC')

            self.stdout.write(
                self.style.SUCCESS('✅ Подключение к PLC установлено')
            )

            if dry_run:
                # Режим dry-run - только показываем что будет синхронизировано
                self.stdout.write('🔍 Режим dry-run - данные не будут сохранены')
                
                # Получаем программы из PLC
                programs_json = service.plc.get_all_programs_json()
                
                if not programs_json:
                    self.stdout.write(
                        self.style.WARNING('⚠️ Не удалось получить программы из PLC')
                    )
                    return
                
                self.stdout.write(f'📋 Найдено {len(programs_json)} программ в PLC:')
                
                for program_name, program_data in programs_json.items():
                    self.stdout.write(f'  {program_name}:')
                    self.stdout.write(f'    Описание: {program_data["description"]}')
                    self.stdout.write(f'    Шагов: {program_data["step_count"]}')
                    self.stdout.write(f'    Длительность: {len([s for s in program_data["steps"] if s["value"] != 0])} мин')
                    
                    # Показываем первые несколько шагов
                    active_steps = [s for s in program_data["steps"] if s["value"] != 0][:3]
                    for step in active_steps:
                        self.stdout.write(f'      Шаг {step["step"]}: {step["function"]}')
                    
                    if len(active_steps) > 3:
                        self.stdout.write(f'      ... и еще {len(active_steps) - 3} шагов')
                
                self.stdout.write('\n💡 Для реальной синхронизации запустите без --dry-run')
                
            else:
                # Реальная синхронизация
                self.stdout.write('🔄 Начинаем синхронизацию...')
                
                result = service.sync_programs_from_plc()
                
                if result['success']:
                    self.stdout.write(
                        self.style.SUCCESS('✅ Синхронизация завершена успешно!')
                    )
                    self.stdout.write(f'📊 Статистика:')
                    self.stdout.write(f'  Всего программ: {result["total_programs"]}')
                    self.stdout.write(f'  Создано: {result["created"]}')
                    self.stdout.write(f'  Обновлено: {result["updated"]}')
                    self.stdout.write(f'  Ошибок: {result["errors"]}')
                    
                    # Показываем детали по программам
                    if result['programs']:
                        self.stdout.write('\n📋 Детали программ:')
                        for program in result['programs']:
                            status_style = self.style.SUCCESS if program['status'] in ['created', 'updated'] else self.style.ERROR
                            self.stdout.write(
                                f'  {program["program_name"]}: {status_style(program["status"])}'
                            )
                            if program['status'] == 'error':
                                self.stdout.write(f'    Ошибка: {program["error"]}')
                            else:
                                self.stdout.write(f'    Длительность: {program["duration"]} мин, шагов: {program["step_count"]}')
                    
                    # Показываем программы в БД
                    self.stdout.write('\n🗄️ Программы в базе данных:')
                    programs = service.get_all_programs_from_db()
                    for program in programs:
                        self.stdout.write(f'  {program.name} (ID: {program.id_service}) - {program.duration} мин')
                
                else:
                    self.stdout.write(
                        self.style.ERROR(f'❌ Ошибка синхронизации: {result["error"]}')
                    )

        except Exception as e:
            raise CommandError(f'❌ Критическая ошибка: {e}')

        finally:
            service.disconnect()
            self.stdout.write('\n🔌 Подключение к PLC закрыто')
