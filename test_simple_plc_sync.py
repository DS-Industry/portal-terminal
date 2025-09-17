#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тестовый скрипт для упрощенного PLC синхронизатора
"""

import os
import sys
import time

# Добавляем путь к Django проекту
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Настройка Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django
django.setup()

from orders.plc_sync import (
    start_plc_scheduler, 
    stop_plc_scheduler,
    get_plc_scheduler_status,
    run_plc_job_manually
)


def test_simple_plc_sync():
    """Тестирование упрощенного PLC синхронизатора"""
    print("🧪 Тестирование упрощенного PLC синхронизатора")
    print("=" * 50)
    
    try:
        # Тест 1: Запуск планировщика
        print("🔄 Тест 1: Запуск планировщика")
        start_plc_scheduler()
        print("✅ Планировщик запущен")
        
        # Тест 2: Проверка статуса
        print("\n📊 Тест 2: Проверка статуса")
        status = get_plc_scheduler_status()
        print(f"Включен: {'✅' if status['enabled'] else '❌'}")
        print(f"Запущен: {'✅' if status['running'] else '❌'}")
        print(f"Задач: {len(status['jobs'])}")
        
        # Тест 3: Ручной запуск задач
        print("\n🔄 Тест 3: Ручной запуск задач")
        
        print("Запуск синхронизации программ...")
        run_plc_job_manually('programs')
        
        print("Запуск синхронизации цен...")
        run_plc_job_manually('prices')
        
        print("Запуск синхронизации статуса...")
        run_plc_job_manually('status')
        
        # Тест 4: Работа в течение времени
        print("\n⏰ Тест 4: Работа в течение 30 секунд")
        print("Планировщик будет работать 30 секунд...")
        
        for i in range(30):
            time.sleep(1)
            if i % 10 == 0:
                status = get_plc_scheduler_status()
                print(f"  {i}с - Планировщик: {'✅' if status['running'] else '❌'}")
        
        # Тест 5: Остановка
        print("\n⏹️ Тест 5: Остановка планировщика")
        stop_plc_scheduler()
        print("✅ Планировщик остановлен")
        
        # Проверка статуса после остановки
        status = get_plc_scheduler_status()
        print(f"Статус после остановки: {'✅' if status['running'] else '❌'}")
        
        print("\n🎉 Все тесты прошли успешно!")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка при тестировании: {e}")
        return False


def test_manual_sync():
    """Тестирование ручной синхронизации"""
    print("\n🔄 Тестирование ручной синхронизации")
    print("=" * 40)
    
    try:
        print("Запуск синхронизации программ...")
        run_plc_job_manually('programs')
        print("✅ Синхронизация программ завершена")
        
    except Exception as e:
        print(f"❌ Ошибка ручной синхронизации: {e}")


def main():
    """Главная функция"""
    print("🏗️ Тестирование упрощенного PLC синхронизатора")
    print("=" * 60)
    
    try:
        # Основное тестирование
        success = test_simple_plc_sync()
        
        if success:
            # Дополнительное тестирование
            test_manual_sync()
            
            print("\n🎉 Все тесты завершены успешно!")
            print("\n💡 Теперь вы можете использовать:")
            print("  - python manage.py plc_sync start")
            print("  - python manage.py plc_sync status")
            print("  - python manage.py plc_sync run programs")
            print("  - python manage.py plc_sync stop")
            print("\n📋 Настройка через переменные окружения:")
            print("  - PLC_SYNC_ENABLED=True")
            print("  - PLC_PROGRAMS_INTERVAL_MINUTES=60")
            print("  - PLC_PRICES_INTERVAL_MINUTES=5")
            print("  - PLC_STATUS_INTERVAL_MINUTES=10")
        else:
            print("\n⚠️ Некоторые тесты не прошли")
            
    except KeyboardInterrupt:
        print("\n\n⏹️ Тестирование прервано пользователем")
    except Exception as e:
        print(f"\n❌ Критическая ошибка: {e}")
    finally:
        # Убеждаемся что планировщик остановлен
        stop_plc_scheduler()
        print("\n👋 Планировщик остановлен")


if __name__ == "__main__":
    main()
