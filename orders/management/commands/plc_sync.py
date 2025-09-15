#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Django management команда для управления PLC синхронизацией
Упрощенная версия по образцу ping_dscloud.py
"""

from django.core.management.base import BaseCommand, CommandError
from orders.plc_sync import (
    start_plc_scheduler, 
    stop_plc_scheduler,
    get_plc_scheduler_status,
    run_plc_job_manually
)


class Command(BaseCommand):
    help = 'Управление PLC синхронизацией'

    def add_arguments(self, parser):
        subparsers = parser.add_subparsers(dest='action', help='Доступные действия')
        
        # Команда запуска
        subparsers.add_parser('start', help='Запустить планировщик')
        
        # Команда остановки
        subparsers.add_parser('stop', help='Остановить планировщик')
        
        # Команда статуса
        subparsers.add_parser('status', help='Показать статус планировщика')
        
        # Команда запуска задачи
        run_parser = subparsers.add_parser('run', help='Запустить задачу вручную')
        run_parser.add_argument(
            'job_name',
            choices=['programs', 'prices', 'status'],
            help='Имя задачи для запуска'
        )

    def handle(self, *args, **options):
        action = options.get('action')
        
        if not action:
            self.stdout.write(self.style.ERROR('Не указано действие. Используйте --help для справки.'))
            return
        
        if action == 'start':
            self.handle_start()
        elif action == 'stop':
            self.handle_stop()
        elif action == 'status':
            self.handle_status()
        elif action == 'run':
            self.handle_run(options)
        else:
            self.stdout.write(self.style.ERROR(f'Неизвестное действие: {action}'))

    def handle_start(self):
        """Обработка команды запуска"""
        self.stdout.write('🔄 Запуск PLC планировщика...')
        start_plc_scheduler()
        self.stdout.write(self.style.SUCCESS('✅ PLC планировщик запущен'))

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
        
        # Задачи
        if status['jobs']:
            self.stdout.write('\n📋 Задачи:')
            for job in status['jobs']:
                next_run = job['next_run'] or 'не запланировано'
                self.stdout.write(f"  {job['name']}: {next_run}")
        else:
            self.stdout.write('\n📋 Задачи: нет активных задач')

    def handle_run(self, options):
        """Обработка команды запуска задачи"""
        job_name = options['job_name']
        
        self.stdout.write(f'🔄 Запуск задачи {job_name}...')
        run_plc_job_manually(job_name)
        self.stdout.write(self.style.SUCCESS(f'✅ Задача {job_name} выполнена'))
