from typing import Tuple

from .models import WashOrder


def is_car_wash_busy() -> bool:
    """
    Проверяет, занята ли мойка (есть заказ со статусом PROCESSING).
    """
    return WashOrder.objects.filter(status=WashOrder.Status.PROCESSING).exists()


def reset_queue_if_needed():
    """
    Сбрасывает очередь, если все заказы завершены.
    """
    active_statuses = [
        WashOrder.Status.CREATED,
        WashOrder.Status.WAITING_PAYMENT,
        WashOrder.Status.PAYED,
        WashOrder.Status.PROCESSING,
    ]
    if not WashOrder.objects.filter(status__in=active_statuses).exists():
        WashOrder.objects.update(queue_number=None, queue_position=None)
        print("[LOG] Очередь сброшена — мойка и очередь пусты.")


def get_next_queue_number() -> str:
    """
    Возвращает следующий уникальный номер очереди в формате A-<номер>.
    """
    existing = WashOrder.objects.exclude(queue_number__isnull=True).values_list('queue_number', flat=True)
    max_num = 0
    for q in existing:
        try:
            num = int(q.split("-")[1])
            max_num = max(max_num, num)
        except (IndexError, ValueError):
            continue
    return f"A-{max_num + 1}"


def assign_queue_number_and_position() -> Tuple[str, int]:
    """
    Назначает queue_number и queue_position новому заказу.

    Возвращает:
        (queue_number, queue_position)
    """
    queue = WashOrder.objects.filter(
        queue_number__isnull=False,
        status__in=[
            WashOrder.Status.CREATED,
            WashOrder.Status.WAITING_PAYMENT,
            WashOrder.Status.PAYED,
        ]
    ).order_by("id")

    if queue.count() >= 5:
        raise ValueError("Очередь переполнена")

    return get_next_queue_number(), queue.count() + 1


def update_queue_positions_after_start():
    """
    После запуска мойки сдвигает позиции заказов в очереди.
    """
    queue = WashOrder.objects.filter(queue_position__isnull=False).order_by("queue_position")
    for order in queue:
        if order.queue_position == 1:
            order.queue_position = 0
        elif order.queue_position is not None and order.queue_position > 1:
            order.queue_position -= 1
        order.save()
    print("[LOG] Очередь обновлена после запуска мойки.")


def try_run_next_car_wash():
    """
    Если мойка свободна и есть заказ с позицией 0 и статусом PAYED — запускает мойку.
    Если есть очередь, перед запуском обновляет позиции.
    """
    if is_car_wash_busy():
        return

    # Сначала обновим позиции: 1 → 0, 2 → 1 и т.д.
    update_queue_positions_after_start()

    # И только потом ищем того, у кого позиция = 0
    next_order = WashOrder.objects.filter(
        status=WashOrder.Status.PAYED,
        queue_position=0
    ).order_by("id").first()

    if next_order:
        print(f"[LOG] Заказ {next_order.transaction_id} запускается с позиции 0.")
        
        # ЛЕНИВЫЙ импорт
        from .start_carwash import start_car_wash
        start_car_wash(next_order)
