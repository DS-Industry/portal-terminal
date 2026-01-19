import time
import os

from datetime import datetime, timezone as dt_timezone
from typing import Optional
from pathlib import Path
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger
from .websocket_service import OrderWebSocketService
from .led_board import LedBoardManager

from django.apps import apps
from django.utils import timezone

from .encoder import EncodedParams
from .plc_service import PLCService

BASE_DIR = Path(__file__).resolve().parent.parent
env_file = BASE_DIR / ".env"

try:
    env_host = os.getenv("DEFAULT_HOST_PLC")
    env_port = os.getenv("DEFAULT_PORT_PLC")
    env_timeout = os.getenv("DEFAULT_TIMEOUT_PLC")

    if env_host:
        DEFAULT_HOST_PLC = env_host

    if env_port and env_port.isdigit():
        DEFAULT_PORT_PLC = int(env_port)

    if env_timeout and env_timeout.isdigit():
        DEFAULT_TIMEOUT_PLC = int(env_timeout)
except Exception as e:
    print(f"Ошибка при загрузке переменных окружения: {e}")


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
    order.mark_processing()
    start_dt = timezone.now()

    service = None
    try:
        service = PLCService(DEFAULT_HOST_PLC, DEFAULT_PORT_PLC, DEFAULT_TIMEOUT_PLC)
        if service.connect():
            started = service.start_program(order.program)
            if not started:
                print(f"[WASH] Не удалось стартовать программу id={order.program.id} на PLC")
        else:
            print("[WASH] Не удалось подключиться к PLC для запуска программы")

        # Ожидание завершения мойки
        if started:

            for i in range(30):
                time.sleep(1)
                wash_status = service.get_wash_status()

                if wash_status is None:
                    print("[WASH] Ошибка чтения статуса, продолжаем ждать...")
                    continue

                if wash_status:  # True → оборудование реально запустилось
                    print("[WASH] Оборудование подтвердило запуск — снимаем флаг...")
                    service.end_program(order.program)  # ✅ снимаем флаг сразу
                    LedBoardManager.set_busy()
                    break
            else:
                print("[WASH] Оборудование так и не подтвердило запуск")
                order.mark_failed()
                OrderWebSocketService.send_error(1004)
                service.end_program(order.program)
                return

            print(f"[WASH] Ожидание завершения мойки...")
            time.sleep(15)
            while True:
                time.sleep(1)

                # Получаем статус мойки
                wash_status = service.get_wash_status()

                if wash_status is None:
                    print(f"[WASH] Ошибка чтения статуса мойки, продолжаем ожидание...")
                    continue

                if not wash_status:  # False - мойка завершена
                    print(f"[WASH] Мойка завершена по статусу PLC")
                    LedBoardManager.set_free()
                    break

    except Exception as e:
        print(f"[WASH] Ошибка при работе с PLC: {e}")
    finally:
        if service:
            try:
                service.disconnect()
            except Exception:
                pass

    # 2) Завершаем заказ
    end_dt = timezone.now()
    order.status = WashOrder.Status.COMPLETED
    order.queue_position = None
    order.queue_number = None
    order.save(update_fields=["status", "queue_position", "queue_number"])
    OrderWebSocketService.send_order_status_update(order)
    print(f"[WASH] Мойка завершена (order={order.transaction_id}) -> COMPLETED")

    payment_type_to_digit = {
        WashOrder.PaymentType.CASH: 1,
        WashOrder.PaymentType.MOBILE_APP: 2,
        WashOrder.PaymentType.LOYALTY_CARD: 2,
        WashOrder.PaymentType.BANK_CARD: 3
    }

    first_digit = payment_type_to_digit.get(order.payment_type, 0)

    id_service = order.program.id_service

    data = first_digit * 100 + id_service

    # отправляем событие "Программа (в конце мойки)"
    try:
        TerminalStatus = apps.get_model('orders', 'TerminalStatus')
        ts = TerminalStatus.objects.first()
        device_id = int(ts.identifier) if ts and ts.identifier is not None else 0

        params = EncodedParams(
            oper=3,
            status=1,
            data=data,
            counter=0,
            localId=0,
            begDate=start_dt,
            endDate=end_dt,
            deviceId=device_id
        )
        results = params.send_hex_to_server()
        print(f"[ENCODER_MANAGE] Program finished sent (oper=3): {results}")
    except Exception as e:
        print(f"[ENCODER_MANAGE] Error sending program-finished event: {e}")
        
    # 3) Пауза между мойками
    try:
        ws = WashSettings.objects.first()
        pause_sec = int(ws.delay_between_washes) if ws and ws.delay_between_washes is not None else 5
    except Exception:
        pause_sec = 5

    time.sleep(pause_sec)
    WashOrder.try_run_next_car_wash()


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
