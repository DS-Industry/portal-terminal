# orders/startup.py
from django.apps import apps
from django.db import connection, OperationalError
from django.db.utils import ProgrammingError


def handle_processing_orders_on_startup(**kwargs):
    """
    При старте сервера (после миграций) проверяет заказы в критических статусах.
    Если таковые найдены — меняет их статус на 'failed' и сбрасывает очередь.
    Это помогает восстановиться после отключения питания или аварийного завершения.
    Критические статусы: PROCESSING, WAITING_PAYMENT, PAYED
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

        # Определяем критические статусы
        critical_statuses = [
            WashOrder.Status.PROCESSING,
            WashOrder.Status.WAITING_PAYMENT,
            WashOrder.Status.PAYED
        ]
        
        # Находим заказы в критических статусах
        critical_orders = WashOrder.objects.filter(status__in=critical_statuses)
        count = critical_orders.count()

        if count > 0:
            print(f"[INIT] Найдено {count} заказ(ов) в критических статусах {critical_statuses}. Обновляем статус на 'failed'...")
            updated_count = critical_orders.update(status=WashOrder.Status.FAILED)
            print(f"[INIT] Обновлено {updated_count} заказ(ов) на статус 'failed'.")
        else:
            print("[INIT] Заказов в критических статусах не найдено.")
            
        # Всегда сбрасываем очередь (очищаем queue_number и queue_position)
        # Это необходимо для корректной работы после сбоев
        print("[INIT] Сброс значений очереди (queue_number, queue_position) для всех заказов...")
        reset_count = WashOrder.objects.exclude(
            queue_number__isnull=True, 
            queue_position__isnull=True
        ).update(queue_number=None, queue_position=None)
        
        if reset_count > 0:
            print(f"[INIT] Сброшено {reset_count} заказ(ов) из очереди.")
        else:
            print("[INIT] Нет заказов в очереди для сброса.")

    except Exception as e:
        print(f"[INIT] Неожиданная ошибка при проверке заказов: {e}")
