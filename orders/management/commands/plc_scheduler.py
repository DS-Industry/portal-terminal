#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Django management команда для управления PLC планировщиком
"""

from django.core.management.base import BaseCommand, CommandError
from orders.plc_scheduler import (
    get_plc_scheduler, 
    start_plc_scheduler, 
    stop_plc_scheduler,
    get_plc_scheduler_status,
    run_plc_job_manually
)


class Command(BaseCommand):
    help = 'Управление PLC планировщиком синхронизации'

    def add_arguments(self, parser):
        subparsers = parser.add_subparsers(dest='action', help='Доступные действия')
        
        # Команда запуска
        start_parser = subparsers.add_parser('start', help='Запустить планировщик')
        start_parser.add_argument(
            '--foreground',
            action='store_true',
            help='Запустить в foreground режиме'
        )
        
        # Команда остановки
        subparsers.add_parser('stop', help='Остановить планировщик')
        
        # Команда статуса
        subparsers.add_parser('status', help='Показать статус планировщика')
        
        # Команда запуска задачи
        run_parser = subparsers.add_parser('run', help='Запустить задачу вручную')
        run_parser.add_argument(
            'job_name',
            choices=['programs', 'prices', 'status', 'health'],
            help='Имя задачи для запуска'
        )
        
        # Команда конфигурации
        config_parser = subparsers.add_parser('config', help='Показать конфигурацию')
        config_parser.add_argument(
            '--set',
            nargs=2,
            metavar=('KEY', 'VALUE'),
            help='Установить значение конфигурации'
        )

    def handle(self, *args, **options):
        action = options.get('action')
        
        if not action:
            self.stdout.write(self.style.ERROR('Не указано действие. Используйте --help для справки.'))
            return
        
        if action == 'start':
            self.handle_start(options)
        elif action == 'stop':
            self.handle_stop()
        elif action == 'status':
            self.handle_status()
        elif action == 'run':
            self.handle_run(options)
        elif action == 'config':
            self.handle_config(options)
        else:
            self.stdout.write(self.style.ERROR(f'Неизвестное действие: {action}'))

    def handle_start(self, options):
        """Обработка команды запуска"""
        foreground = options.get('foreground', False)
        
        self.stdout.write('🔄 Запуск PLC планировщика...')
        
        if start_plc_scheduler():
            self.stdout.write(self.style.SUCCESS('✅ PLC планировщик запущен'))
            
            if foreground:
                self.stdout.write('Запуск в foreground режиме...')
                self.stdout.write('Нажмите Ctrl+C для остановки')
                
                import time
                import signal
                import sys
                
                def signal_handler(sig, frame):
                    self.stdout.write('\n⏹️ Получен сигнал остановки...')
                    stop_plc_scheduler()
                    self.stdout.write('👋 PLC планировщик остановлен')
                    sys.exit(0)
                
                signal.signal(signal.SIGINT, signal_handler)
                signal.signal(signal.SIGTERM, signal_handler)
                
                try:
                    while True:
                        time.sleep(60)
                except KeyboardInterrupt:
                    pass
            else:
                self.stdout.write('Планировщик запущен в фоновом режиме')
        else:
            self.stdout.write(self.style.ERROR('❌ Не удалось запустить PLC планировщик'))

    def handle_stop(self):
        """Обработка команды остановки"""
        self.stdout.write('⏹️ Остановка PLC планировщика...')
        stop_plc_scheduler()
        self.stdout.write(self.style.SUCCESS('✅ PLC планировщик остановлен'))

    def handle_status(self):
        """Обработка команды статуса"""
        status = get_plc_scheduler_status()
        
        self.stdout.write('📊 Статус PLC планировщика:')
        self.stdout.write('=' * 40)
        
        # Общий статус
        self.stdout.write(f"Включен: {'✅' if status['enabled'] else '❌'}")
        self.stdout.write(f"Запущен: {'✅' if status['running'] else '❌'}")
        
        # Конфигурация
        self.stdout.write('\n⚙️ Конфигурация:')
        config = status['config']
        self.stdout.write(f"  Программы: каждые {config['programs_interval']} мин")
        self.stdout.write(f"  Цены: каждые {config['prices_interval']} мин")
        self.stdout.write(f"  Статус: каждые {config['status_interval']} мин")
        self.stdout.write(f"  Проверка здоровья: каждые {config['health_check_interval']} мин")
        self.stdout.write(f"  Макс. попыток: {config['max_retries']}")
        
        # Статус задач
        self.stdout.write('\n📋 Статус задач:')
        for job_name, job_status in status['jobs'].items():
            self.stdout.write(f"  {job_name}:")
            
            if job_status['last_success']:
                from datetime import datetime
                last_success = datetime.fromtimestamp(job_status['last_success'])
                self.stdout.write(f"    Последний успех: {last_success.strftime('%Y-%m-%d %H:%M:%S')}")
            else:
                self.stdout.write(f"    Последний успех: никогда")
            
            if job_status['last_error']:
                from datetime import datetime
                last_error = datetime.fromtimestamp(job_status['last_error'])
                self.stdout.write(f"    Последняя ошибка: {last_error.strftime('%Y-%m-%d %H:%M:%S')}")
            else:
                self.stdout.write(f"    Последняя ошибка: нет")
            
            self.stdout.write(f"    Подряд ошибок: {job_status['consecutive_failures']}")

    def handle_run(self, options):
        """Обработка команды запуска задачи"""
        job_name = options['job_name']
        
        self.stdout.write(f'🔄 Запуск задачи {job_name}...')
        
        result = run_plc_job_manually(job_name)
        
        if result.get('success', False):
            self.stdout.write(self.style.SUCCESS(f'✅ Задача {job_name} выполнена успешно'))
            
            # Показываем детали результата
            if 'created' in result:
                self.stdout.write(f"  Создано: {result['created']}")
            if 'updated' in result:
                self.stdout.write(f"  Обновлено: {result['updated']}")
            if 'error' in result:
                self.stdout.write(f"  Ошибок: {result['error']}")
        else:
            error_msg = result.get('error', 'Неизвестная ошибка')
            self.stdout.write(self.style.ERROR(f'❌ Ошибка выполнения задачи {job_name}: {error_msg}'))

    def handle_config(self, options):
        """Обработка команды конфигурации"""
        if options.get('set'):
            key, value = options['set']
            self.stdout.write(f'Установка {key} = {value}')
            # TODO: Реализовать изменение конфигурации
            self.stdout.write('Функция изменения конфигурации в разработке')
        else:
            self.stdout.write('📋 Текущая конфигурация PLC планировщика:')
            self.stdout.write('=' * 50)
            
            import os
            config_vars = [
                'PLC_SYNC_ENABLED',
                'PLC_PROGRAMS_INTERVAL_MINUTES',
                'PLC_PRICES_INTERVAL_MINUTES',
                'PLC_STATUS_INTERVAL_MINUTES',
                'PLC_HEALTH_CHECK_INTERVAL_MINUTES',
                'PLC_MAX_RETRIES',
                'PLC_RETRY_DELAY_SECONDS',
                'PLC_LOG_LEVEL',
                'PLC_LOG_TO_FILE',
                'PLC_LOG_FILE',
                'PLC_NOTIFY_ON_ERROR',
                'PLC_NOTIFY_EMAIL',
                'PLC_SYNC_ON_STARTUP',
                'MODBUS_HOST',
                'MODBUS_PORT',
                'MODBUS_TIMEOUT'
            ]
            
            for var in config_vars:
                value = os.getenv(var, 'не установлено')
                self.stdout.write(f"  {var}: {value}")
            
            self.stdout.write('\n💡 Для изменения конфигурации установите переменные окружения')
            self.stdout.write('   или используйте --set KEY VALUE (в разработке)')
