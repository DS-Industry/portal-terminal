# orders/apps.py
from django.apps import AppConfig
from django.core import management
from django.db import connection
import logging

logger = logging.getLogger(__name__)

class OrdersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'orders'

    def ready(self):

        from django.db.models.signals import post_migrate
        post_migrate.connect(handle_processing_orders_on_startup_signal, sender=self)
        print("[INIT] Сигнал post_migrate подключен.")


        import sys
        running_migrations = 'migrate' in sys.argv
        running_tests = 'test' in sys.argv

        if not running_migrations and not running_tests:
            import threading
            timer = threading.Timer(0.1, self._delayed_startup_tasks)
            timer.daemon = True
            timer.start()
            print("[INIT-APP] Запланирован отложенный запуск задач инициализации.")
        else:
             print("[INIT-APP] Отложенные задачи инициализации не запускаются во время миграций или тестов.")

    def _delayed_startup_tasks(self):
        """
        Выполняет задачи инициализации, которые требуют полностью загруженных моделей.
        Вызывается с небольшой задержкой после ready().
        """
        try:
            print("[INIT-APP-DELAYED] Начало выполнения отложенных задач инициализации...")
            
            print("[INIT-APP-DELAYED] Вызов обработчика заказов PROCESSING...")
            from .startup import handle_processing_orders_on_startup
            handle_processing_orders_on_startup()
            print("[INIT-APP-DELAYED] Обработчик заказов PROCESSING завершен.")

            print("[DS-DELAYED] Попытка запуска APScheduler...")
            from .ping_dscloud import start_dscloud_scheduler
            start_dscloud_scheduler()
            print("[DS-DELAYED] Запуск APScheduler завершен.")
            
            print("[INIT-APP-DELAYED] Все отложенные задачи инициализации завершены.")
            
        except Exception as e:
            logger.error(f"[INIT-APP-DELAYED] Критическая ошибка в отложенных задачах: {e}", exc_info=True)

def handle_processing_orders_on_startup_signal(sender, **kwargs):
    """
    Обработчик сигнала post_migrate. Вызывает основную логику.
    """
    print("[INIT-SIGNAL] Получен сигнал post_migrate, запуск обработчика заказов PROCESSING...")
    from .startup import handle_processing_orders_on_startup
    handle_processing_orders_on_startup()
    print("[INIT-SIGNAL] Обработчик заказов PROCESSING завершен.")
