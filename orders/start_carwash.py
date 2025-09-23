import time

from datetime import datetime, timezone as dt_timezone
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger
from .websocket_service import OrderWebSocketService

from django.apps import apps


_scheduler: Optional[BackgroundScheduler] = None

def _get_models():
    WashOrder = apps.get_model('orders', 'WashOrder')
    WashSettings = apps.get_model('orders', 'WashSettings')
    return WashOrder, WashSettings


def _ensure_scheduler():
    global _scheduler
    if _scheduler is None or not getattr(_scheduler, "running", False):
        _scheduler = BackgroundScheduler()
        _scheduler.start()
    return _scheduler


def _run_wash(order_id: int):
    """
    Фоновая задача «мойки».
    - Длительность мойки фиксированная: 60 сек (заглушка).
    - Пауза между мойками: WashSettings.delay_between_washes (сек), иначе 5 сек по умолчанию.
    """
    WashOrder, WashSettings = _get_models()
    try:
        order = WashOrder.objects.get(id=order_id)
    except WashOrder.DoesNotExist:
        print(f"[WASH] Заказ id={order_id} не найден.")
        return

    # Переводим в PROCESSING
    print(f"[WASH] Старт мойки (order={order.transaction_id})")
    order.status = WashOrder.Status.PROCESSING
    order.save()
    OrderWebSocketService.send_order_status_update(order)

    # 1) Собственно мойка — 60 сек
    time.sleep(60)

    # 2) Завершаем заказ
    order.status = WashOrder.Status.COMPLETED
    order.queue_position = None
    order.queue_number = None
    order.save()
    OrderWebSocketService.send_order_status_update(order)
    print(f"[WASH] Мойка завершена (order={order.transaction_id}) -> COMPLETED")

    # 3) Пауза между мойками
    try:
        ws = WashSettings.objects.first()
        pause_sec = int(ws.delay_between_washes) if ws and ws.delay_between_washes is not None else 5
    except Exception:
        pause_sec = 5

    time.sleep(pause_sec)

    # 4) Запуск следующего из очереди
    from .queue_option import try_run_next_car_wash
    try_run_next_car_wash()


def start_car_wash(order):
    """
    Публичный API: планируем немедленный запуск мойки для заказа в фоне.
    """
    scheduler = _ensure_scheduler()
    trigger = DateTrigger(run_date=datetime.now(dt_timezone.utc))  # сразу
    scheduler.add_job(
        func=_run_wash,
        trigger=trigger,
        kwargs={"order_id": order.id},
        replace_existing=False,
        name=f"run_wash_{order.id}",
    )
    print(f"[WASH] Задача мойки запланирована (order={order.transaction_id}).")
