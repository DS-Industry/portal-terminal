import time

from .models import (
    WashOrder,
    WashSettings,
    )


def start_car_wash(order):
    """
    Запускает мойку: статус processing → completed через 120 сек.
    После завершения мойки — запускает следующий заказ (если есть).
    """
    print(f"[LOG] Запуск мойки по программе: {order.program.name}")
    order.status = WashOrder.Status.PROCESSING
    order.save()

    time.sleep(60)

    order.status = WashOrder.Status.COMPLETED
    order.queue_position = None
    order.queue_number = None
    order.save()
    print(f"[LOG] Мойка завершена. Статус заказа {order.transaction_id} обновлён: completed")

    # Переход к следующему заказу
    delay = WashSettings.objects.first().delay_between_washes if WashSettings.objects.exists() else 5
    print(f"[LOG] Начало следующей мойки через {delay} сек...")
    time.sleep(delay)
    
    # ЛЕНИВЫЙ импорт
    from .queue_option import try_run_next_car_wash
    try_run_next_car_wash()
