#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PLC Sync - Простая синхронизация данных с OWEN PLC
Следует паттерну ping_dscloud.py
"""

import os
import time
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from .plc_service import sync_programs_from_plc

# Настройки из переменных окружения
try:
    PLC_SYNC_ENABLED = os.getenv("PLC_SYNC_ENABLED", "True").lower() == "true"
    PLC_PROGRAMS_INTERVAL = int(os.getenv("PLC_PROGRAMS_INTERVAL_MINUTES", "1"))
    PLC_PRICES_INTERVAL = int(os.getenv("PLC_PRICES_INTERVAL_MINUTES", "1"))
    PLC_STATUS_INTERVAL = int(os.getenv("PLC_STATUS_INTERVAL_MINUTES", "1"))
    print(f"PLC_SYNC_ENABLED: {PLC_SYNC_ENABLED}, Programs: {PLC_PROGRAMS_INTERVAL}min, Prices: {PLC_PRICES_INTERVAL}min")
except Exception as e:
    print(f"Ошибка при загрузке переменных окружения PLC: {e}")


def plc_programs_job():
    """
    Фоновая задача для синхронизации программ из PLC.
    """
    try:
        result = sync_programs_from_plc()
        if result['success']:
            print(f"Успешно: создано={result['created']}, обновлено={result['updated']}, ошибок={result['errors']}")
        else:
            print(f"[PLC-PROGRAMS] Ошибка: {result['error']}")
    except Exception as e:
        print(f"[PLC-PROGRAMS] Исключение: {e}")


def plc_prices_job():
    """
    Фоновая задача для синхронизации цен из PLC.
    """
    try:
        # TODO: Реализовать синхронизацию цен
        print("Синхронизация цен - функция в разработке")
    except Exception as e:
        print(f"[PLC-PRICES] Исключение: {e}")


def plc_status_job():
    """
    Фоновая задача для синхронизации статуса из PLC.
    """
    try:
        # TODO: Реализовать синхронизацию статуса
        print("Синхронизация статуса - функция в разработке")
    except Exception as e:
        print(f"[PLC-STATUS] Исключение: {e}")


_scheduler_instance = None


def start_plc_scheduler():
    """
    Инициализирует и запускает APScheduler для задач PLC.
    Гарантирует, что планировщик запускается только один раз.
    """
    global _scheduler_instance
    
    if not PLC_SYNC_ENABLED:
        return
    
    if _scheduler_instance is not None:
        if _scheduler_instance.running:
            print("[PLC] APScheduler уже запущен, повторный запуск пропущен.")
            return
        else:
            print("[PLC] APScheduler был остановлен, создаем новый экземпляр.")
    
    _scheduler_instance = BackgroundScheduler()
    
    # Задача синхронизации программ
    if PLC_PROGRAMS_INTERVAL > 0:
        _scheduler_instance.add_job(
            func=plc_programs_job,
            trigger=IntervalTrigger(minutes=PLC_PROGRAMS_INTERVAL),
            id='plc_programs_job',
            name='PLC Programs Sync Job',
            replace_existing=True,
        )

    # Задача синхронизации цен
    if PLC_PRICES_INTERVAL > 0:
        _scheduler_instance.add_job(
            func=plc_prices_job,
            trigger=IntervalTrigger(minutes=PLC_PRICES_INTERVAL),
            id='plc_prices_job',
            name='PLC Prices Sync Job',
            replace_existing=True,
        )

    # Задача синхронизации статуса
    if PLC_STATUS_INTERVAL > 0:
        _scheduler_instance.add_job(
            func=plc_status_job,
            trigger=IntervalTrigger(minutes=PLC_STATUS_INTERVAL),
            id='plc_status_job',
            name='PLC Status Sync Job',
            replace_existing=True,
        )

    _scheduler_instance.start()


def stop_plc_scheduler():
    """
    Останавливает APScheduler для задач PLC.
    """
    global _scheduler_instance
    
    if _scheduler_instance is not None:
        _scheduler_instance.shutdown()
        _scheduler_instance = None


def get_plc_scheduler_status():
    """
    Получает статус PLC планировщика.
    """
    global _scheduler_instance
    
    if _scheduler_instance is None:
        return {
            'running': False,
            'enabled': PLC_SYNC_ENABLED,
            'jobs': []
        }
    
    jobs = []
    for job in _scheduler_instance.get_jobs():
        jobs.append({
            'id': job.id,
            'name': job.name,
            'next_run': job.next_run_time.isoformat() if job.next_run_time else None
        })
    
    return {
        'running': _scheduler_instance.running,
        'enabled': PLC_SYNC_ENABLED,
        'jobs': jobs,
        'config': {
            'programs_interval': PLC_PROGRAMS_INTERVAL,
            'prices_interval': PLC_PRICES_INTERVAL,
            'status_interval': PLC_STATUS_INTERVAL
        }
    }


def run_plc_job_manually(job_name):
    """
    Запускает задачу PLC вручную.
    """
    if job_name == 'programs':
        plc_programs_job()
    elif job_name == 'prices':
        plc_prices_job()
    elif job_name == 'status':
        plc_status_job()
    else:
        print(f"[PLC] Неизвестная задача: {job_name}")


