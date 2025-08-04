# orders/apps.py
from django.apps import AppConfig
import logging

logger = logging.getLogger(__name__)

class OrdersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'orders'

    def ready(self):
        from django.db.models.signals import post_migrate
        from .startup import handle_processing_orders_on_startup
        post_migrate.connect(handle_processing_orders_on_startup_signal, sender=self)

        import sys
        running_migrations = 'migrate' in sys.argv
        running_tests = 'test' in sys.argv

        if not running_migrations and not running_tests:
            try:
                from .ping_dscloud import start_dscloud_scheduler
                start_dscloud_scheduler()
            except Exception as e:
                logger.error(f"[DS] Ошибка при запуске APScheduler: {e}", exc_info=True)
        else:
             logger.info("[DS] APScheduler не запускается во время миграций или тестов.")

def handle_processing_orders_on_startup_signal(sender, **kwargs):
    """
    Обработчик сигнала post_migrate. Вызывает основную логику.
    """
    from .startup import handle_processing_orders_on_startup
    handle_processing_orders_on_startup()
