# orders/ping_dscloud.py

import os
import requests
import json
import time
import uuid # Для генерации transaction_id для мобильного приложения
import environ
from pathlib import Path
from django.db import transaction
from django.apps import apps
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist

BASE_DIR = Path(__file__).resolve().parent.parent
env_file = BASE_DIR / ".env"
env = environ.Env()
environ.Env.read_env(env_file)

try:
    DSCLOUD_IP = env("DSCLOUD_IP")
    DSCLOUD_PORT = env("DSCLOUD_PORT")
    DSCLOUD_API_KEY = env("DSCLOUD_API_KEY")
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

# Глобальные переменные состояния для задачи APScheduler
_gvl_sent_for = None
_last_processing_order_id = None

# --- НОВАЯ ГЛОБАЛЬНАЯ ПЕРЕМЕННАЯ для отслеживания последнего обработанного gvl_cardsum ---
_last_processed_cardsum = 0
# ----------------------------------------------------------------------------------------

def dscloud_job():
    """
    Основная фоновая задача для APScheduler.
    Отправляет данные состояния терминала каждые 5 секунд.
    Обрабатывает оплату через мобильное приложение.
    """
    global _gvl_sent_for, _last_processing_order_id, _last_processed_cardsum
    
    max_retries = 3 

    try:
        WashOrder = apps.get_model('orders', 'WashOrder')
        TerminalStatus = apps.get_model('orders', 'TerminalStatus')
        Program = apps.get_model('orders', 'Program') # Нужно для поиска программы по цене

        processing_order = WashOrder.objects.filter(status=WashOrder.Status.PROCESSING).first()
        ts = TerminalStatus.objects.first()

        if not ts:
            print("[DS] TerminalStatus отсутствует, создаём с нулями.")
            with transaction.atomic():
                 if not TerminalStatus.objects.exists():
                     ts = TerminalStatus.objects.create(
                         identifier=9999,
                         name="DS Terminal",
                         bay_number=1,
                         car_wash_identifier=9999,
                         gvl_cardnum=0,
                         gvl_cardsum=0,
                         gvl_sum=0,
                         gvl_err=0,
                         gvl_time=0,
                         gvl_source=0
                     )
                 else:
                     ts = TerminalStatus.objects.first()
            
            send_data_to_dscloud()
            return

        # --- ОСНОВНОЙ ПИНГ DScloud ---
        # Отправляем данные и получаем ответ
        response_data = send_data_to_dscloud()
        
        # --- ОБРАБОТКА ОПЛАТЫ ЧЕРЕЗ МОБИЛЬНОЕ ПРИЛОЖЕНИЕ ---
        if response_data:
            gvl_cardsum = int(response_data.get('GVLCardSum', 0))
            gvl_cardnum = int(response_data.get('GVLCardNum', 0))
            gvl_source = int(response_data.get('GVLSource', 0))
            
            # Проверяем, есть ли новая оплата (gvl_cardsum > 0 и не равна последней обработанной)
            if gvl_cardsum > 0 and gvl_cardsum != _last_processed_cardsum:
                print(f"[DS-MOBILE] Обнаружена оплата через мобильное приложение: сумма {gvl_cardsum}, карта {gvl_cardnum}, источник {gvl_source}")
                
                # Проверяем, свободна ли мойка
                if not processing_order:
                    # Ищем программу с соответствующей ценой
                    try:
                        program = Program.objects.get(price=gvl_cardsum)
                        print(f"[DS-MOBILE] Найдена программа '{program.name}' для суммы {gvl_cardsum}")
                        
                        # Создаем заказ
                        transaction_id_for_mobile = f"mobile_app_{uuid.uuid4()}"
                        with transaction.atomic():
                            new_order = WashOrder.objects.create(
                                program=program,
                                program_price=gvl_cardsum, # Цена из DScloud
                                transaction_id=transaction_id_for_mobile, # Специальный ID
                                status=WashOrder.Status.PROCESSING,
                                ucn=str(gvl_cardnum) if gvl_cardnum else "", # Записываем номер карты
                                payment_type=WashOrder.PaymentType.MOBILE_APP,
                                gvl_source=gvl_source, # Записываем источник
                                # queue_number и qr_code остаются NULL/пустыми
                            )
                            print(f"[DS-MOBILE] Создан заказ для мобильного приложения: ID={new_order.transaction_id}, Программа={program.name}")
                            
                            # Обновляем TerminalStatus, чтобы сбросить gvl_cardsum
                            # Это может помочь избежать повторной обработки, хотя по условию DScloud это не должно происходить
                            ts.gvl_cardsum = 0
                            ts.save()
                            print(f"[DS-MOBILE] Сброшено gvl_cardsum в TerminalStatus для предотвращения повторной обработки.")
                        
                        # Обновляем глобальную переменную
                        _last_processed_cardsum = gvl_cardsum
                        
                    except Program.DoesNotExist:
                        print(f"[DS-MOBILE] ОШИБКА: Не найдена программа с ценой {gvl_cardsum}. Оплата проигнорирована.")
                        # Можно также сбросить gvl_cardsum в TerminalStatus здесь, если нужно сообщить об ошибке DScloud
                        # ts.gvl_cardsum = 0
                        # ts.save()
                else:
                    print(f"[DS-MOBILE] Мойка занята (заказ {_last_processing_order_id}). Оплата через мобильное приложение отклонена DScloud.")
            elif gvl_cardsum > 0 and gvl_cardsum == _last_processed_cardsum:
                # Это может быть повторный ответ с тем же значением, игнорируем
                print(f"[DS-MOBILE] Получено повторное значение gvl_cardsum ({gvl_cardsum}), игнорируем.")
            # else: gvl_cardsum == 0, ничего не делаем
        # --- КОНЕЦ ОБРАБОТКИ ОПЛАТЫ ---

        # --- СТАНДАРТНАЯ ЛОГИКА ОБРАБОТКИ ЗАКАЗОВ ---
        current_processing_order_id = str(processing_order.transaction_id) if processing_order else None

        if processing_order and current_processing_order_id != _last_processing_order_id:
             print(f"[DS] Новый или измененный заказ в статусе PROCESSING: {current_processing_order_id}")
             expected_sum = int(processing_order.program_price)

             with transaction.atomic():
                 ts.gvl_sum = expected_sum
                 ts.save()
                 ts.refresh_from_db()

             print(f"[DS] GVL_SUM обновлён в БД на сумму заказа: {expected_sum}")

             confirmed = False
             retries = 0
             while not confirmed and retries < max_retries:
                 response_data = send_data_to_dscloud()
                 if response_data and response_data.get('GVLSum') == str(expected_sum):
                     print(f"[DS] Подтверждение получения суммы {expected_sum} от DScloud получено.")
                     confirmed = True
                     _gvl_sent_for = current_processing_order_id
                     _last_processing_order_id = current_processing_order_id
                 else:
                     print(f"[DS] Ожидание подтверждения суммы {expected_sum} от DScloud... (Попытка {retries + 1}/{max_retries})")
                     if response_data:
                         print(f"[DS] Получен ответ: {response_data}")
                     retries += 1
                     if retries == max_retries:
                         print(f"[DS] ОШИБКА: Не удалось получить подтверждение суммы {expected_sum} от DScloud после {max_retries} попыток.")

        elif processing_order and current_processing_order_id == _last_processing_order_id:
            print(f"[DS] Заказ {_last_processing_order_id} всё ещё в статусе PROCESSING. Ожидание завершения.")
            pass

        elif not processing_order and _gvl_sent_for:
            print(f"[DS] Заказ {_gvl_sent_for} завершён. Обнуляем GVL_SUM в БД.")

            with transaction.atomic():
                ts.gvl_sum = 0
                ts.save()
                ts.refresh_from_db()

            print(f"[DS] GVL_SUM обнулён в БД.")

            confirmed_zero = False
            retries = 0
            while not confirmed_zero and retries < max_retries:
                response_data = send_data_to_dscloud()
                if response_data and response_data.get('GVLSum') == '0':
                    print(f"[DS] Подтверждение обнуления суммы от DScloud получено.")
                    confirmed_zero = True
                    _gvl_sent_for = None
                    _last_processing_order_id = None
                else:
                    print(f"[DS] Ожидание подтверждения обнуления суммы от DScloud... (Попытка {retries + 1}/{max_retries})")
                    if response_data:
                        print(f"[DS] Получен ответ: {response_data}")
                    retries += 1
                    if retries == max_retries:
                         print(f"[DS] ОШИБКА: Не удалось получить подтверждение обнуления суммы от DScloud после {max_retries} попыток.")

        else:
            # Нет активного заказа и нет завершенного заказа для обнуления
            # Отправляем данные в любом случае (DScloud требует постоянный пинг)
            # print("[DS] Нет активного заказа. Отправка данных для поддержания соединения.")
            # send_data_to_dscloud() - уже отправили в начале функции
            pass
            
    except Exception as e:
        print(f"[DS] Критическая ошибка в задаче dscloud_job: {e}")

def dscloud_prices_job():
    """
    Фоновая задача для APScheduler.
    Отправляет данные о ценах программ каждую минуту.
    """
    print("[DS-PRICES] Запуск задачи отправки цен.")
    send_prices_to_dscloud()
    print("[DS-PRICES] Задача отправки цен завершена.")


def start_dscloud_scheduler():
    """
    Инициализирует и запускает APScheduler для задач DScloud.
    """
    scheduler = BackgroundScheduler()
    
    scheduler.add_job(
        func=dscloud_job,
        trigger=IntervalTrigger(seconds=5),
        id='dscloud_ping_job',
        name='DScloud Ping Job (State)',
        replace_existing=True,
    )
    
    scheduler.add_job(
        func=dscloud_prices_job,
        trigger=IntervalTrigger(minutes=1), #hours=1
        id='dscloud_prices_ping_job',
        name='DScloud Ping Job (Prices)',
        replace_existing=True,
    )
    
    scheduler.start()
    print("[DS] APScheduler для DScloud запущен (State ping: 5s, Prices ping: 60min).")
