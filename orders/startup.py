# orders/startup.py
from django.core.management.color import no_style
from django.db import connection, OperationalError
from django.db.utils import ProgrammingError
from django.apps import apps

def handle_processing_orders_on_startup(**kwargs):
    """
    При старте сервера (после миграций) проверяет заказы в статусе 'processing'.
    Если таковые найдены — меняет их статус на 'failed'.
    Это помогает восстановиться после отключения питания или аварийного завершения.
    """
    try:
        if not apps.ready: 
             print("[INIT] Приложение ещё не готово.")
             return

        WashOrder = apps.get_model('orders', 'WashOrder')
        try:
           
            with connection.cursor() as cursor:
                 cursor.execute("SELECT 1 FROM orders_washorder LIMIT 1")
        except ProgrammingError as e:
            print(f"[INIT] Таблица orders_washorder не существует или ошибка запроса: {e}")
            return
        except OperationalError as e:
            print(f"[INIT] Ошибка доступа к таблице orders_washorder: {e}")
            return

        processing_orders = WashOrder.objects.filter(status=WashOrder.Status.PROCESSING)
        count = processing_orders.count()

        if count > 0:
            print(f"[INIT] Найдено {count} заказ(ов) в статусе 'processing'. Обновляем статус на 'failed'...")
            updated_count = processing_orders.update(status=WashOrder.Status.FAILED)
            print(f"[INIT] Обновлено {updated_count} заказ(ов) на статус 'failed'.")
        else:
            print("[INIT] Активных заказов в статусе 'processing' не найдено.")

    except Exception as e:
        print(f"[INIT] Неожиданная ошибка при проверке заказов 'processing': {e}")
