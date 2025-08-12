import json
import os
import requests

from django.apps import apps
from django.db import transaction
from django.core.exceptions import ObjectDoesNotExist

from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from .start_carwash import start_car_wash 



BASE_DIR = Path(__file__).resolve().parent.parent
env_file = BASE_DIR / ".env"

try:
    PRICE_PING = os.getenv("PRICE_PING")
    DSCLOUD_IP = os.getenv("DSCLOUD_IP")
    DSCLOUD_PORT = os.getenv("DSCLOUD_PORT")
    DSCLOUD_API_KEY = os.getenv("DSCLOUD_API_KEY")
    print(f"DSCLOUD_IP: {DSCLOUD_IP}, DSCLOUD_PORT: {DSCLOUD_PORT}, DSCLOUD_API_KEY: {DSCLOUD_API_KEY}")
except Exception as e:
    print(f"Ошибка при загрузке переменных окружения: {e}")


def send_data_to_dscloud():
    """
    Отправляет данные с текущего состояния терминала на сервер DScloud.
    Все переменные передаются через один заголовок 'data'.
    Возвращает JSON-ответ от DScloud или None в случае ошибки.
    """
    try:
        TerminalStatus = apps.get_model('orders', 'TerminalStatus')
        ts = TerminalStatus.objects.first()
        if not ts:
            print("[DS] Нет записи в TerminalStatus — отправка невозможна.")
            return None
        identifier = ts.identifier or 0
        url = f"http://{DSCLOUD_IP}:{DSCLOUD_PORT}/api/v1/external/device/write/{identifier}"

        # Формируем строку data (как раньше)
        data_string = (
            f"GVLSum:{int(ts.gvl_sum)},"
            f"GVLErr:{int(ts.gvl_err)},"
            f"GVLTime:{int(ts.gvl_time)},"
            f"GVLCardNum:{int(ts.gvl_cardnum)},"
            f"GVLCardSum:{int(ts.gvl_cardsum)},"
            f"GVLSource:{int(ts.gvl_source)}"
        )
        headers = {
            "akey": DSCLOUD_API_KEY,
            "data": data_string
        }
        print(f"[DS] Отправлено на {url} с headers: {headers}")

        with requests.Session() as session:
            response = session.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            response_data = response.json()
            print(f"[DS] Ответ от DScloud: {response_data}")
            return response_data
    except requests.exceptions.RequestException as e:
        print(f"[DS] Ошибка сети/HTTP при отправке на DScloud: {e}")
        return None
    except ValueError as e:
        print(f"[DS] Ошибка парсинга JSON ответа от DScloud: {e}. Ответ: {response.text if 'response' in locals() else 'Нет ответа'}")
        return None
    except Exception as e:
        print(f"[DS] Неожиданная ошибка при отправке на DScloud: {e}")
        return None


def send_prices_to_dscloud():
    """
    Отправляет данные о ценах программ на сервер DScloud.
    Данные отправляются раз в минуту.
    """
    try:
        TerminalStatus = apps.get_model('orders', 'TerminalStatus')
        Program = apps.get_model('orders', 'Program')
        
        ts = TerminalStatus.objects.first()
        if not ts:
            print("[DS-PRICES] Нет записи в TerminalStatus — отправка цен невозможна.")
            return None
            
        car_wash_id = ts.car_wash_identifier
        
        programs = Program.objects.all()
        
        if not programs.exists():
            print("[DS-PRICES] Нет программ для отправки.")
            price_data = {}
        else:
            price_data = {str(program.id_service): str(int(program.price)) for program in programs}
        
        data_json_string = json.dumps(price_data, separators=(',', ':'))
        
        url = f"http://{DSCLOUD_IP}:{DSCLOUD_PORT}/api/v1/external/price/write/{car_wash_id}"
        headers = {
            "akey": DSCLOUD_API_KEY,
            "data": data_json_string
        }
        print(f"[DS-PRICES] Отправлено на {url} с headers: {headers}")

        with requests.Session() as session:
            response = session.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            print(f"[DS-PRICES] Ответ от DScloud: Status {response.status_code}")
            return response.status_code
    except requests.exceptions.RequestException as e:
        print(f"[DS-PRICES] Ошибка сети/HTTP при отправке цен на DScloud: {e}")
        return None
    except ObjectDoesNotExist as e:
        print(f"[DS-PRICES] Ошибка доступа к данным: {e}")
        return None
    except Exception as e:
        print(f"[DS-PRICES] Неожиданная ошибка при отправке цен на DScloud: {e}")
        return None


_gvl_sent_for = None
_last_processing_order_id = None
_last_processed_cardsum = 0
_mobile_order_confirmed = False
_mobile_in_progress = False 


def _get_ts():
    TerminalStatus = apps.get_model('orders', 'TerminalStatus')
    return TerminalStatus.objects.first()


def _get_models():
    WashOrder = apps.get_model('orders', 'WashOrder')
    TerminalStatus = apps.get_model('orders', 'TerminalStatus')
    Program = apps.get_model('orders', 'Program')
    return WashOrder, TerminalStatus, Program


def _set_ts_gvl_sum(ts, value: int):
    with transaction.atomic():
        ts.gvl_sum = int(value)
        ts.save()
        ts.refresh_from_db()


def _confirm_sum(expected: int, max_retries: int = 3, label: str = "CONFIRM"):
    retries = 0
    while retries < max_retries:
        resp = send_data_to_dscloud()
        if resp and resp.get('GVLSum') == str(expected):
            print(f"[DS-{label}] Подтверждение суммы {expected} от DScloud получено.")
            return True
        print(f"[DS-{label}] Ожидание подтверждения {expected}... (Попытка {retries + 1}/{max_retries})")
        if resp:
            print(f"[DS-{label}] Ответ: {resp}")
        retries += 1
    print(f"[DS-{label}] ОШИБКА: Нет подтверждения суммы {expected} после {max_retries} попыток.")
    return False


def _confirm_zero(max_retries: int = 3, label: str = "CLEANUP"):
    retries = 0
    while retries < max_retries:
        resp = send_data_to_dscloud()
        if resp and resp.get('GVLSum') == '0':
            print(f"[DS-{label}] Подтверждение обнуления суммы от DScloud получено.")
            return True
        print(f"[DS-{label}] Ожидание подтверждения обнуления... (Попытка {retries + 1}/{max_retries})")
        if resp:
            print(f"[DS-{label}] Ответ: {resp}")
        retries += 1
    print(f"[DS-{label}] ОШИБКА: Не удалось подтвердить обнуление после {max_retries} попыток.")
    return False


def _next_payed_in_queue(WashOrder):
    # смещаем позиции и берём того, у кого позиция 0
    from .queue_option import update_queue_positions_after_start
    update_queue_positions_after_start()  # [LOG] Очередь обновлена... уже логируется внутри
    return WashOrder.objects.filter(
        status=WashOrder.Status.PAYED,
        queue_position=0
    ).order_by("id").first()


def _handle_mobile_when_free(response_data, Program, TerminalStatus, WashOrder, max_retries: int) -> bool:
    """
    Возвращает True, если мобилка обработана (были действия или явный отказ),
    чтобы dscloud_job() мог завершить текущую итерацию и не запускать CLEANUP.
    """
    global _mobile_in_progress

    if not response_data:
        return False

    gvl_cardsum = int(response_data.get('GVLCardSum', 0))
    gvl_cardnum = int(response_data.get('GVLCardNum', 0))
    gvl_source = int(response_data.get('GVLSource', 0))
    if gvl_cardsum <= 0:
        return False

    _mobile_in_progress = True  # <--- ставим флаг до всех действий
    try:
        program = Program.objects.get(price=gvl_cardsum)
        ts = _get_ts()
        if ts:
            _set_ts_gvl_sum(ts, gvl_cardsum)

        # ждём подтверждения суммы от DScloud
        if not _confirm_sum(gvl_cardsum, max_retries, "MOBILE"):
            # не подтверждено — аккуратно откатываем только cardsum, но НЕ триггерим cleanup
            if ts:
                ts.gvl_cardsum = 0
                ts.save()
            return True  # обработали мобилку в этом тике; остальные ветки пропускаем
        # подтверждено — создаём заказ и стартуем
        import uuid as _uuid
        new_order = WashOrder.objects.create(
            program=program,
            program_price=gvl_cardsum,
            transaction_id=f"mobile_app_{_uuid.uuid4()}",
            status=WashOrder.Status.PROCESSING,
            ucn=str(gvl_cardnum) if gvl_cardnum else "",
            payment_type=WashOrder.PaymentType.MOBILE_APP,
            gvl_source=gvl_source,
            is_mobile_payment=True,
        )
        if ts:
            ts.gvl_cardsum = 0
            ts.save()
        print(f"[DS-MOBILE] Немедленный запуск мойки для заказа {new_order.transaction_id}")
        start_car_wash(new_order)
        return True  # в этот тик ничего больше не делаем
    except Program.DoesNotExist:
        print(f"[DS-MOBILE] ОШИБКА: Не найдена программа с ценой {gvl_cardsum}.")
        ts = _get_ts()
        if ts:
            ts.gvl_cardsum = 0
            ts.save()
        return True
    finally:
        _mobile_in_progress = False

def _start_payed_without_queue(payed_order, TerminalStatus, max_retries: int):
    expected_sum = int(payed_order.program_price)
    if payed_order.payment_type == payed_order.PaymentType.LOYALTY_CARD:
        print(f"[DS-PAYED] Заказ {payed_order.transaction_id} оплачен картой лояльности. Ждём 5 сек.")
        import time as _t; _t.sleep(5)
    ts = TerminalStatus.objects.first()
    if ts:
        _set_ts_gvl_sum(ts, expected_sum)
    if not _confirm_sum(expected_sum, max_retries, "PAYED"):
        if ts:
            _set_ts_gvl_sum(ts, 0)  # как в текущем коде при неуспехе подтверждения
        return
    print(f"[DS-PAYED] Старт мойки для заказа {payed_order.transaction_id}")
    start_car_wash(payed_order)

def _handover_between_washes(WashOrder, TerminalStatus, max_retries: int):
    """
    Стык моек: если есть очередь — НЕ обнуляем, а сразу шлём сумму следующего и стартуем;
    если очереди нет — обнуляем.
    """
    # очередь?
    next_order = _next_payed_in_queue(WashOrder)
    ts = TerminalStatus.objects.first()
    if next_order:
        expected = int(next_order.program_price)
        if ts:
            _set_ts_gvl_sum(ts, expected)
        if _confirm_sum(expected, max_retries, "HANDOVER"):
            print(f"[DS-HANDOVER] Старт мойки для заказа {next_order.transaction_id} без перехода в Free")
            start_car_wash(next_order)
        else:
            # важно: НЕ обнуляем gvl_sum, как ты просил
            print("[DS-HANDOVER] Подтверждение не пришло. GVL_SUM НЕ обнуляем. Повторит следующая итерация.")
        return

    # очереди нет — обнуляем и подтверждаем 0
    if ts and ts.gvl_sum != 0:
        print(f"[DS-CLEANUP] Очереди нет. Обнуляем GVL_SUM (было {ts.gvl_sum}).")
        _set_ts_gvl_sum(ts, 0)
        _confirm_zero(max_retries, "CLEANUP")


def dscloud_job():
    global _gvl_sent_for, _last_processing_order_id, _last_processed_cardsum, _mobile_order_confirmed, _mobile_in_progress

    max_retries = 3
    try:
        WashOrder, TerminalStatus, Program = _get_models()

        processing_order = WashOrder.objects.filter(status=WashOrder.Status.PROCESSING).first()
        if processing_order:
            print(f"[DS] Мойка занята (заказ {processing_order.transaction_id}). Пинг отключен до завершения.")
            _gvl_sent_for = str(processing_order.transaction_id)
            _last_processing_order_id = str(processing_order.transaction_id)
            return

        print("[DS] Мойка свободна. Выполняем пинг и обработку оплат/запусков.")
        response_data = send_data_to_dscloud()

        # --- 1) MOBILE: если пришла сумма из мобилки — обрабатываем и выходим из этого тика ---
        if _handle_mobile_when_free(response_data, Program, TerminalStatus, WashOrder, max_retries):
            return  # <--- ВАЖНО: не даём зайти в CLEANUP и прочие ветки в эту же итерацию

        # --- 2) PAYED без очереди ---
        payed_no_queue = WashOrder.objects.filter(
            status=WashOrder.Status.PAYED,
            queue_position=None
        ).order_by("id").first()
        if payed_no_queue:
            print(f"[DS-PAYED] Обнаружен PAYED без очереди: {payed_no_queue.transaction_id}")
            _start_payed_without_queue(payed_no_queue, TerminalStatus, max_retries)
            return

        # --- 3) HANDOVER между мойками ---
        if _gvl_sent_for and not processing_order:
            print(f"[DS-HANDOVER] Заказ {_gvl_sent_for} завершён. Обрабатываем переход.")
            _handover_between_washes(WashOrder, TerminalStatus, max_retries)
            _gvl_sent_for = None
            _last_processing_order_id = None
            _mobile_order_confirmed = False
            return

        # --- 4) CLEANUP: обнуляем только если НЕТ мобилки в процессе и НЕТ «сырых» данных от мобилки ---
        ts = _get_ts()
        if ts and ts.gvl_sum != 0:
            # если есть очередь — ничего не трогаем
            has_queue = WashOrder.objects.filter(
                status__in=[WashOrder.Status.CREATED, WashOrder.Status.WAITING_PAYMENT, WashOrder.Status.PAYED],
                queue_position__isnull=False
            ).exists()
            # блокируем cleanup при любом мобильном «хвосте»
            if not has_queue and not _mobile_in_progress and int(ts.gvl_cardsum or 0) == 0:
                print(f"[DS-CLEANUP] Нет активных заказов и очереди. Обнуляем GVL_SUM (было {ts.gvl_sum}).")
                _set_ts_gvl_sum(ts, 0)
                _confirm_zero(max_retries, "CLEANUP")

    except Exception as e:
        print(f"[DS] Критическая ошибка в dscloud_job: {e}")



def dscloud_prices_job():
    """
    Фоновая задача для APScheduler.
    Отправляет данные о ценах программ каждую минуту.
    """
    print("[DS-PRICES] Запуск задачи отправки цен.")
    send_prices_to_dscloud()
    print("[DS-PRICES] Задача отправки цен завершена.")

_scheduler_instance = None

def start_dscloud_scheduler():
    """
    Инициализирует и запускает APScheduler для задач DScloud.
    Гарантирует, что планировщик запускается только один раз.
    """
    global _scheduler_instance
    
    if _scheduler_instance is not None:
        if _scheduler_instance.running:
            print("[DS] APScheduler уже запущен, повторный запуск пропущен.")
            return
        else:
            print("[DS] APScheduler был остановлен, создаем новый экземпляр.")
    
    print("[DS] Инициализация APScheduler для DScloud...")
    _scheduler_instance = BackgroundScheduler()
    
    _scheduler_instance.add_job(
        func=dscloud_job,
        trigger=IntervalTrigger(seconds=5),
        id='dscloud_ping_job',
        name='DScloud Ping Job (State)',
        replace_existing=True,
    )
    
    _scheduler_instance.add_job(
        func=dscloud_prices_job,
        trigger=IntervalTrigger(hours=int(PRICE_PING)), #minutes=1
        id='dscloud_prices_ping_job',
        name='DScloud Ping Job (Prices)',
        replace_existing=True,
    )
    
    _scheduler_instance.start()
    print("[DS] APScheduler для DScloud успешно запущен (State ping: 5s, Prices ping: 1min).")
