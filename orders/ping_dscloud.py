# orders/ping_dscloud.py

import os
import requests
import json
import time
import uuid
import environ
from pathlib import Path
from django.db import transaction
from django.apps import apps
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist

# Импортируем функцию запуска мойки из views
from .views import start_car_wash 

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
_last_processed_cardsum = 0
# --- НОВАЯ ГЛОБАЛЬНАЯ ПЕРЕМЕННАЯ для мобильной оплаты ---
# Флаг, сигнализирующий, что сумма для мобильного заказа была отправлена и подтверждена
_mobile_order_confirmed = False
# --------------------------------------------------------

def dscloud_job():
    """
    Основная фоновая задача для APScheduler.
    Отправляет данные состояния терминала каждые 5 секунд.
    Обрабатывает оплату через мобильное приложение.
    Обрабатывает заказы в статусе PAYED для отправки суммы и запуска.
    Эта задача НЕ ВЫПОЛНЯЕТСЯ, если мойка занята (любой заказ в PROCESSING).
    """
    global _gvl_sent_for, _last_processing_order_id, _last_processed_cardsum, _mobile_order_confirmed
    
    max_retries = 3 

    try:
        WashOrder = apps.get_model('orders', 'WashOrder')
        TerminalStatus = apps.get_model('orders', 'TerminalStatus')
        Program = apps.get_model('orders', 'Program')

        # --- ГЛАВНОЕ УСЛОВИЕ: ЕСЛИ МОЙКА ЗАНЯТА, НЕ ВЫПОЛНЯЕМ НИЧЕГО ---
        any_processing_order = WashOrder.objects.filter(status=WashOrder.Status.PROCESSING).first()
        
        if any_processing_order:
            print(f"[DS] Мойка занята (заказ {any_processing_order.transaction_id}). Основной пинг DScloud приостановлен.")
            # Сбрасываем флаг мобильной оплаты, если мойка занята
            _mobile_order_confirmed = False
            return
        # -----------------------------------------------------------------------

        print("[DS] Мойка свободна. Выполняем пинг и проверку оплаты.")

        # --- ОСНОВНОЙ ПИНГ DScloud ---
        response_data = send_data_to_dscloud()
        
        # --- ОБРАБОТКА ОПЛАТЫ ЧЕРЕЗ МОБИЛЬНОЕ ПРИЛОЖЕНИЕ ---
        if response_data:
            gvl_cardsum = int(response_data.get('GVLCardSum', 0))
            gvl_cardnum = int(response_data.get('GVLCardNum', 0))
            gvl_source = int(response_data.get('GVLSource', 0))
            
            if gvl_cardsum > 0 and gvl_cardsum != _last_processed_cardsum:
                print(f"[DS-MOBILE] Обнаружена оплата через мобильное приложение: сумма {gvl_cardsum}, карта {gvl_cardnum}, источник {gvl_source}")
                
                # Проверяем, свободна ли мойка (еще раз, на всякий случай)
                if not WashOrder.objects.filter(status=WashOrder.Status.PROCESSING).exists():
                    try:
                        program = Program.objects.get(price=gvl_cardsum)
                        print(f"[DS-MOBILE] Найдена программа '{program.name}' для суммы {gvl_cardsum}")
                        
                        # --- КРИТИЧЕСКИ ВАЖНЫЙ ЭТАП ---
                        # 1. Обновляем GVLSum в нашей БД
                        ts = TerminalStatus.objects.first()
                        if ts:
                            ts.gvl_sum = gvl_cardsum
                            ts.save()
                            print(f"[DS-MOBILE] GVL_SUM обновлён в БД на сумму заказа: {gvl_cardsum}")
                        
                        # 2. Отправляем сумму на DScloud и ЖДЕМ ПОДТВЕРЖДЕНИЯ
                        confirmed_sum = False
                        retries = 0
                        while not confirmed_sum and retries < max_retries:
                            # Отправляем текущее состояние (с обновленным gvl_sum)
                            confirm_response = send_data_to_dscloud() 
                            if confirm_response and confirm_response.get('GVLSum') == str(gvl_cardsum):
                                print(f"[DS-MOBILE] Подтверждение получения суммы {gvl_cardsum} от DScloud получено. DScloud должен показать статус Busy.")
                                confirmed_sum = True
                                _mobile_order_confirmed = True # Устанавливаем флаг
                            else:
                                print(f"[DS-MOBILE] Ожидание подтверждения суммы {gvl_cardsum} от DScloud... (Попытка {retries + 1}/{max_retries})")
                                if confirm_response:
                                    print(f"[DS-MOBILE] Получен ответ: {confirm_response}")
                                retries += 1
                        
                        if not confirmed_sum:
                             print(f"[DS-MOBILE] ОШИБКА: Не удалось получить подтверждение суммы {gvl_cardsum} от DScloud после {max_retries} попыток.")
                             # Откатываем gvl_sum в 0, чтобы не мешать дальнейшей работе
                             if ts:
                                ts.gvl_sum = 0
                                ts.save()
                                print(f"[DS-MOBILE] Откат: GVL_SUM обнулён в БД из-за ошибки подтверждения.")
                             # Сбрасываем gvl_cardsum в TerminalStatus
                             if ts:
                                ts.gvl_cardsum = 0
                                ts.save()
                                print(f"[DS-MOBILE] Сброшено gvl_cardsum в TerminalStatus из-за ошибки.")
                             _mobile_order_confirmed = False # Сбрасываем флаг
                             return # Прерываем обработку мобильной оплаты
                        # -------------------------------
                        
                        # 3. Создаем заказ и запускаем мойку только после подтверждения
                        transaction_id_for_mobile = f"mobile_app_{uuid.uuid4()}"
                        new_order = None
                        with transaction.atomic():
                            new_order = WashOrder.objects.create(
                                program=program,
                                program_price=gvl_cardsum,
                                transaction_id=transaction_id_for_mobile,
                                status=WashOrder.Status.PROCESSING, # Сразу в PROCESSING
                                ucn=str(gvl_cardnum) if gvl_cardnum else "",
                                payment_type=WashOrder.PaymentType.MOBILE_APP,
                                gvl_source=gvl_source,
                                is_mobile_payment=True, # Устанавливаем флаг
                            )
                            print(f"[DS-MOBILE] Создан заказ для мобильного приложения: ID={new_order.transaction_id}, Программа={program.name}")
                            # Поле 'date' будет заполнено автоматически
                            
                            # Сбрасываем gvl_cardsum в TerminalStatus, так как оплата обработана
                            if ts:
                                ts.gvl_cardsum = 0
                                ts.save()
                                print(f"[DS-MOBILE] Сброшено gvl_cardsum в TerminalStatus.")
                        
                        # Обновляем глобальную переменную
                        _last_processed_cardsum = gvl_cardsum
                        
                        # 4. Запуск мойки НЕМЕДЛЕННО (БЕЗ THREADING)
                        if new_order:
                            print(f"[DS-MOBILE] Немедленный запуск мойки для заказа {new_order.transaction_id}")
                            try:
                                start_car_wash(new_order)
                                print(f"[DS-MOBILE] Функция start_car_wash вызвана для заказа {new_order.transaction_id}")
                            except Exception as e:
                                print(f"[DS-MOBILE] ОШИБКА при вызове start_car_wash для заказа {new_order.transaction_id}: {e}")
                            
                    except Program.DoesNotExist:
                        print(f"[DS-MOBILE] ОШИБКА: Не найдена программа с ценой {gvl_cardsum}. Оплата проигнорирована.")
                        # Сбрасываем gvl_cardsum в TerminalStatus в случае ошибки
                        ts = TerminalStatus.objects.first()
                        if ts:
                            ts.gvl_cardsum = 0
                            ts.save()
                            print(f"[DS-MOBILE] Сброшено gvl_cardsum в TerminalStatus из-за ошибки.")
                        _mobile_order_confirmed = False # Сбрасываем флаг
                else:
                    print(f"[DS-MOBILE] Мойка стала занята. Оплата через мобильное приложение отклонена.")
            elif gvl_cardsum > 0 and gvl_cardsum == _last_processed_cardsum:
                # Это может быть повторный ответ с тем же значением, игнорируем
                # но если флаг не установлен, возможно, подтверждение не было получено ранее
                if not _mobile_order_confirmed:
                     print(f"[DS-MOBILE] Повторное значение gvl_cardsum ({gvl_cardsum}) без подтверждения. Возможно, ожидание подтверждения не завершено.")
                else:
                     print(f"[DS-MOBILE] Получено повторное значение gvl_cardsum ({gvl_cardsum}), игнорируем.")
            # else: gvl_cardsum == 0, ничего не делаем
        # --- КОНЕЦ ОБРАБОТКИ ОПЛАТЫ ЧЕРЕЗ МОБИЛЬНОЕ ПРИЛОЖЕНИЕ ---

        # --- ОБРАБОТКА ЗАКАЗОВ В СТАТУСЕ PAYED (cash/bank_card/loyalty_card) ---
        # Ищем заказы в статусе PAYED, которые нужно запустить
        # Для немедленного запуска (без очереди) ищем заказы с queue_position=None
        # Для запуска из очереди логика должна быть в try_run_next_car_wash или аналоге.
        # Здесь мы обрабатываем только немедленный запуск.
        
        payed_order_to_start = WashOrder.objects.filter(
            status=WashOrder.Status.PAYED,
            queue_position=None
        ).order_by("id").first()
        
        if payed_order_to_start:
             print(f"[DS-PAYED] Обнаружен заказ в статусе PAYED для немедленного запуска: {payed_order_to_start.transaction_id}")
             expected_sum = int(payed_order_to_start.program_price)

             # --- ОСОБАЯ ЛОГИКА ДЛЯ LOYALTY_CARD ---
             # Если это оплата по карте лояльности, добавляем 5-секундную задержку
             if payed_order_to_start.payment_type == WashOrder.PaymentType.LOYALTY_CARD:
                 print(f"[DS-PAYED] Заказ {payed_order_to_start.transaction_id} оплачен картой лояльности. Ожидание 5 секунд перед запуском.")
                 time.sleep(5) # Ждем 5 секунд как указано в ТЗ
                 print(f"[DS-PAYED] Завершено 5-секундное ожидание для заказа {payed_order_to_start.transaction_id}")
             # ---------------------------------------

             ts = TerminalStatus.objects.first()
             if ts:
                 # 1) Обновить поле gvl_sum в БД
                 with transaction.atomic():
                     ts.gvl_sum = expected_sum
                     ts.save()
                     ts.refresh_from_db()

                 print(f"[DS-PAYED] GVL_SUM обновлён в БД на сумму заказа: {expected_sum}")

                 # 2) Отправить данные на DScloud и дождаться подтверждения
                 confirmed = False
                 retries = 0
                 while not confirmed and retries < max_retries:
                     response_data = send_data_to_dscloud()
                     if response_data and response_data.get('GVLSum') == str(expected_sum):
                         print(f"[DS-PAYED] Подтверждение получения суммы {expected_sum} от DScloud получено.")
                         confirmed = True
                         # _gvl_sent_for используется для терминальных заказов, но здесь не критично
                         # _gvl_sent_for = str(payed_order_to_start.transaction_id) 
                         
                         # 3) После подтверждения - ЗАПУСКАЕМ МОЙКУ
                         print(f"[DS-PAYED] Немедленный запуск мойки для заказа {payed_order_to_start.transaction_id}")
                         try:
                             start_car_wash(payed_order_to_start)
                             print(f"[DS-PAYED] Функция start_car_wash вызвана для заказа {payed_order_to_start.transaction_id}")
                         except Exception as e:
                             print(f"[DS-PAYED] ОШИБКА при вызове start_car_wash для заказа {payed_order_to_start.transaction_id}: {e}")
                         
                     else:
                         print(f"[DS-PAYED] Ожидание подтверждения суммы {expected_sum} от DScloud... (Попытка {retries + 1}/{max_retries})")
                         if response_data:
                             print(f"[DS-PAYED] Получен ответ: {response_data}")
                         retries += 1
                         if retries == max_retries:
                             print(f"[DS-PAYED] ОШИБКА: Не удалось получить подтверждение суммы {expected_sum} от DScloud после {max_retries} попыток.")
                             # Откатываем gvl_sum в 0, чтобы не мешать дальнейшей работе
                             if ts:
                                ts.gvl_sum = 0
                                ts.save()
                                print(f"[DS-PAYED] Откат: GVL_SUM обнулён в БД из-за ошибки подтверждения.")
                             # Не запускаем мойку
                             
        # --- КОНЕЦ ОБРАБОТКИ ЗАКАЗОВ В СТАТУСЕ PAYED ---
            
        # --- ЛОГИКА ОБРАБОТКИ ЗАКАЗОВ В СТАТУСЕ PROCESSING (уже запущенных) ---
        # Эта логика срабатывает, если заказ был запущен НЕ через этот ping_dscloud.py
        # (например, напрямую в views.py, что теперь запрещено, но на случай race condition)
        processing_order = WashOrder.objects.filter(status=WashOrder.Status.PROCESSING).first()
        current_processing_order_id = str(processing_order.transaction_id) if processing_order else None

        if processing_order and current_processing_order_id != _last_processing_order_id:
             print(f"[DS-PROCESSING] Обнаружен заказ в статусе PROCESSING: {current_processing_order_id}")
             expected_sum = int(processing_order.program_price)

             ts = TerminalStatus.objects.first()
             if ts:
                 # 1) Обновить поле gvl_sum в БД
                 with transaction.atomic():
                     ts.gvl_sum = expected_sum
                     ts.save()
                     ts.refresh_from_db()

                 print(f"[DS-PROCESSING] GVL_SUM обновлён в БД на сумму заказа: {expected_sum}")

                 # 2) Отправить данные на DScloud и дождаться подтверждения
                 confirmed = False
                 retries = 0
                 while not confirmed and retries < max_retries:
                     response_data = send_data_to_dscloud()
                     if response_data and response_data.get('GVLSum') == str(expected_sum):
                         print(f"[DS-PROCESSING] Подтверждение получения суммы {expected_sum} от DScloud получено.")
                         confirmed = True
                         _gvl_sent_for = current_processing_order_id
                         _last_processing_order_id = current_processing_order_id
                     else:
                         print(f"[DS-PROCESSING] Ожидание подтверждения суммы {expected_sum} от DScloud... (Попытка {retries + 1}/{max_retries})")
                         if response_data:
                             print(f"[DS-PROCESSING] Получен ответ: {response_data}")
                         retries += 1
                         if retries == max_retries:
                             print(f"[DS-PROCESSING] ОШИБКА: Не удалось получить подтверждение суммы {expected_sum} от DScloud после {max_retries} попыток.")

        # --- КРИТИЧНО ВАЖНО: ПРОВЕРКА И ОБНУЛЕНИЕ GVL_SUM ПОСЛЕ ЗАВЕРШЕНИЯ ЛЮБОЙ МОЙКИ ---
        # Эта проверка должна выполняться всегда, когда мойка свободна.
        # Она обрабатывает случаи, когда мойка была запущена вне логики _gvl_sent_for.
        
        ts = TerminalStatus.objects.first()
        if ts and ts.gvl_sum != 0:
            # gvl_sum не равен 0, но активных заказов в PROCESSING нет.
            # Это означает, что предыдущая мойка завершена, но gvl_sum не был обнулён.
            print(f"[DS-CLEANUP] Нет активных заказов, но gvl_sum={ts.gvl_sum}. Обнуляем GVL_SUM в БД.")

            # Обнуляем в БД
            with transaction.atomic():
                ts.gvl_sum = 0
                ts.save()
                ts.refresh_from_db()

            print(f"[DS-CLEANUP] GVL_SUM обнулён в БД.")

            # Отправляем обнуленные данные и дожидаемся подтверждения от DScloud
            confirmed_zero = False
            retries = 0
            while not confirmed_zero and retries < max_retries:
                response_data = send_data_to_dscloud()
                if response_data and response_data.get('GVLSum') == '0':
                    print(f"[DS-CLEANUP] Подтверждение обнуления суммы от DScloud получено.")
                    confirmed_zero = True
                    # Сбрасываем флаги терминальных заказов, если они были установлены
                    _gvl_sent_for = None
                    _last_processing_order_id = None
                    # Сбрасываем флаг мобильной оплаты
                    _mobile_order_confirmed = False 
                else:
                    print(f"[DS-CLEANUP] Ожидание подтверждения обнуления суммы от DScloud... (Попытка {retries + 1}/{max_retries})")
                    if response_data:
                        print(f"[DS-CLEANUP] Получен ответ: {response_data}")
                    retries += 1
                    if retries == max_retries:
                         print(f"[DS-CLEANUP] ОШИБКА: Не удалось получить подтверждение обнуления суммы от DScloud после {max_retries} попыток.")
                         # Не сбрасываем флаги, попробуем снова на следующем шаге.
        # ----------------------------------------------------------------------------------

        # --- ОТПРАВКА ПИНГА, ЕСЛИ ВСЕ УСЛОВИЯ СОБЛЮДЕНЫ ---
        # Этот блок теперь выполняется только если gvl_sum уже 0 или был обнулён выше
        # и нет активных заказов. Логика отправки "пустого" пинга сохранена.
        # print("[DS-IDLE] Нет активного заказа. Отправка данных для поддержания соединения.")
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

# Глобальная переменная для хранения экземпляра планировщика
_scheduler_instance = None

def start_dscloud_scheduler():
    """
    Инициализирует и запускает APScheduler для задач DScloud.
    Гарантирует, что планировщик запускается только один раз.
    """
    global _scheduler_instance
    
    # Проверка, не запущен ли уже планировщик
    if _scheduler_instance is not None:
        # Проверим, не остановлен ли он
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
        trigger=IntervalTrigger(minutes=1), # hours=1
        id='dscloud_prices_ping_job',
        name='DScloud Ping Job (Prices)',
        replace_existing=True,
    )
    
    _scheduler_instance.start()
    print("[DS] APScheduler для DScloud успешно запущен (State ping: 5s, Prices ping: 1min).")

