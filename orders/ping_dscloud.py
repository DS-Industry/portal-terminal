# orders/ping_dscloud.py

import os
import requests
import json
import time
import uuid
# import threading # Убрано, как и требовалось
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
    Эта задача выполняется НЕЗАВИСИМО от состояния мойки.
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

def dscloud_job():
    """
    Основная фоновая задача для APScheduler.
    Отправляет данные состояния терминала каждые 5 секунд.
    Обрабатывает оплату через мобильное приложение.
    Эта задача НЕ ВЫПОЛНЯЕТСЯ, если мойка занята (любой заказ в PROCESSING).
    """
    global _gvl_sent_for, _last_processing_order_id, _last_processed_cardsum

    max_retries = 3

    try:
        WashOrder = apps.get_model('orders', 'WashOrder')
        TerminalStatus = apps.get_model('orders', 'TerminalStatus')
        Program = apps.get_model('orders', 'Program')

        # --- ГЛАВНОЕ УСЛОВИЕ: ЕСЛИ МОЙКА ЗАНЯТА, НЕ ВЫПОЛНЯЕМ НИЧЕГО ---
        any_processing_order = WashOrder.objects.filter(status=WashOrder.Status.PROCESSING).first()

        if any_processing_order:
            print(f"[DS] Мойка занята (заказ {any_processing_order.transaction_id}). Основной пинг DScloud приостановлен.")
            # Примечание: Сообщение "Execution of job ... skipped: maximum number of running instances reached (1)"
            # может появляться здесь, если start_car_wash (вызванная ранее) все еще выполняется (time.sleep).
            # Это нормально, если start_car_wash блокирует поток.
            return
        # -----------------------------------------------------------------------

        # --- ЕСЛИ МОЙКА СВОБОДНА, ВЫПОЛНЯЕМ ВСЮ ЛОГИКУ ---
        print("[DS] Мойка свободна. Выполняем пинг и проверку оплаты.")

        # --- ПРОВЕРКА НА ЗАВЕРШЕННЫЕ ЗАКАЗЫ И ОБНУЛЕНИЕ GVL_SUM ---
        # Проверяем, были ли недавно завершенные заказы, требующие обнуления gvl_sum.
        # Это критично для мобильных заказов, которые не управляются логикой _gvl_sent_for.
        ts = TerminalStatus.objects.first()
        if ts and ts.gvl_sum != 0:
            # gvl_sum не равен 0, но активных заказов в PROCESSING нет.
            # Это означает, что предыдущая мойка (терминальная или мобильная) завершена,
            # но DScloud не был уведомлен об этом (gvl_sum не обнулён).
            print(f"[DS] Нет активных заказов, но gvl_sum={ts.gvl_sum}. Обнуляем GVL_SUM в БД.")
            with transaction.atomic():
                ts.gvl_sum = 0
                ts.save()
                ts.refresh_from_db()
            print(f"[DS] GVL_SUM обнулён в БД.")

            # Отправляем обнуленные данные и дожидаемся подтверждения от DScloud,
            # чтобы DScloud перешёл в статус "Free".
            confirmed_zero = False
            retries = 0
            while not confirmed_zero and retries < max_retries:
                response_data = send_data_to_dscloud()
                if response_data and response_data.get('GVLSum') == '0':
                    print(f"[DS] Подтверждение обнуления суммы от DScloud получено. DScloud должен показать статус Free.")
                    confirmed_zero = True
                    # Сбрасываем флаги терминальных заказов, если они были установлены.
                    # Это важно для корректной работы логики терминальных заказов в будущем.
                    _gvl_sent_for = None
                    _last_processing_order_id = None
                else:
                    print(f"[DS] Ожидание подтверждения обнуления суммы от DScloud... (Попытка {retries + 1}/{max_retries})")
                    if response_data:
                        print(f"[DS] Получен ответ: {response_data}")
                    retries += 1
                    if retries == max_retries:
                        print(f"[DS] ОШИБКА: Не удалось получить подтверждение обнуления суммы от DScloud после {max_retries} попыток.")
                        # Продолжаем выполнение. Следующая итерация снова попытается обнулить.
            # ВАЖНО: Не прерываем выполнение основной логики, если обнуление не удалось.
            # Лучше продолжить пинг и попробовать снова на следующем шаге.
            # return # Не используем return здесь

        # --- ОСНОВНОЙ ПИНГ DScloud ---
        # Отправляем данные и получаем ответ ТОЛЬКО если мойка свободна.
        # На этом этапе gvl_sum должен быть 0 (если обнуление прошло успешно выше).
        response_data = send_data_to_dscloud()

        # --- ОБРАБОТКА ОПЛАТЫ ЧЕРЕЗ МОБИЛЬНОЕ ПРИЛОЖЕНИЕ ---
        if response_data:
            gvl_cardsum = int(response_data.get('GVLCardSum', 0))
            gvl_cardnum = int(response_data.get('GVLCardNum', 0))
            gvl_source = int(response_data.get('GVLSource', 0))

            if gvl_cardsum > 0 and gvl_cardsum != _last_processed_cardsum:
                print(f"[DS-MOBILE] Обнаружена оплата через мобильное приложение: сумма {gvl_cardsum}, карта {gvl_cardnum}, источник {gvl_source}")

                # Проверяем еще раз, свободна ли мойка.
                # Это важно, если состояние могло измениться между проверками.
                if not WashOrder.objects.filter(status=WashOrder.Status.PROCESSING).exists():
                    try:
                        program = Program.objects.get(price=gvl_cardsum)
                        print(f"[DS-MOBILE] Найдена программа '{program.name}' для суммы {gvl_cardsum}")

                        # --- ЛОГИКА ОТПРАВКИ СУММЫ НА DSCLOUD ДО СОЗДАНИЯ ЗАКАЗА ---
                        # Чтобы DScloud показал статус "Busy", нужно сначала отправить сумму.
                        if ts: # Убедимся, что TerminalStatus существует
                            # 1. Обновляем GVLSum в нашей БД
                            ts.gvl_sum = gvl_cardsum
                            ts.save()
                            print(f"[DS-MOBILE] GVL_SUM обновлён в БД на сумму заказа: {gvl_cardsum}")

                        # 2. Отправляем сумму на DScloud и ждем подтверждения
                        confirmed_sum = False
                        retries = 0
                        while not confirmed_sum and retries < max_retries:
                            # Отправляем текущее состояние (с обновленным gvl_sum)
                            confirm_response = send_data_to_dscloud()
                            if confirm_response and confirm_response.get('GVLSum') == str(gvl_cardsum):
                                print(f"[DS-MOBILE] Подтверждение получения суммы {gvl_cardsum} от DScloud получено. DScloud должен показать статус Busy.")
                                confirmed_sum = True
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
                            # Сбрасываем gvl_cardsum в TerminalStatus, чтобы DScloud не продолжал слать его
                            ts.gvl_cardsum = 0
                            ts.save()
                            print(f"[DS-MOBILE] Сброшено gvl_cardsum в TerminalStatus из-за ошибки.")
                            return # Прерываем обработку мобильной оплаты

                        # 3. Создаем заказ и запускаем мойку только после подтверждения от DScloud
                        transaction_id_for_mobile = f"mobile_app_{uuid.uuid4()}"
                        new_order = None
                        with transaction.atomic():
                            new_order = WashOrder.objects.create(
                                program=program,
                                program_price=gvl_cardsum,
                                transaction_id=transaction_id_for_mobile,
                                status=WashOrder.Status.PROCESSING,
                                ucn=str(gvl_cardnum) if gvl_cardnum else "",
                                payment_type=WashOrder.PaymentType.MOBILE_APP,
                                gvl_source=gvl_source,
                                is_mobile_payment=True,
                            )
                            print(f"[DS-MOBILE] Создан заказ для мобильного приложения: ID={new_order.transaction_id}, Программа={program.name}")
                            # Поле 'date' будет заполнено автоматически благодаря auto_now_add=True

                            # Сбрасываем gvl_cardsum в TerminalStatus, так как оплата обработана
                            # и мы не хотим, чтобы DScloud продолжал присылать её.
                            ts.gvl_cardsum = 0
                            ts.save()
                            print(f"[DS-MOBILE] Сброшено gvl_cardsum в TerminalStatus.")

                        # Обновляем глобальную переменную для отслеживания последней обработанной оплаты
                        _last_processed_cardsum = gvl_cardsum

                        # 4. Запуск мойки НЕМЕДЛЕННО (БЕЗ THREADING)
                        if new_order:
                            print(f"[DS-MOBILE] Немедленный запуск мойки для заказа {new_order.transaction_id}")
                            try:
                                # Предполагается, что start_car_wash импортирована
                                start_car_wash(new_order)
                                print(f"[DS-MOBILE] Функция start_car_wash вызвана для заказа {new_order.transaction_id}")
                            except Exception as e:
                                print(f"[DS-MOBILE] ОШИБКА при вызове start_car_wash для заказа {new_order.transaction_id}: {e}")
                        # --------------------

                    except Program.DoesNotExist:
                        print(f"[DS-MOBILE] ОШИБКА: Не найдена программа с ценой {gvl_cardsum}. Оплата проигнорирована.")
                        # Сбрасываем gvl_cardsum в TerminalStatus в случае ошибки,
                        # чтобы DScloud не продолжал слать её.
                        if ts:
                            ts.gvl_cardsum = 0
                            ts.save()
                            print(f"[DS-MOBILE] Сброшено gvl_cardsum в TerminalStatus из-за ошибки.")
                else:
                    print(f"[DS-MOBILE] Мойка стала занята после получения данных. Оплата через мобильное приложение отклонена.")
            elif gvl_cardsum > 0 and gvl_cardsum == _last_processed_cardsum:
                print(f"[DS-MOBILE] Получено повторное значение gvl_cardsum ({gvl_cardsum}), игнорируем.")
            # else: gvl_cardsum == 0, ничего не делаем
        # --- КОНЕЦ ОБРАБОТКИ ОПЛАТЫ ЧЕРЕЗ МОБИЛЬНОЕ ПРИЛОЖЕНИЕ ---

        # --- ЛОГИКА ОБРАБОТКИ ЗАКАЗОВ ТЕРМИНАЛА ---
        # Эта логика обрабатывает заказы, созданные через терминал (не мобильные).
        # Она срабатывает, если:
        # 1. Нет активных заказов (мы дошли до этого места).
        # 2. gvl_sum уже обнулён (проверили выше или он был 0 изначально).
        # 3. Появился новый терминальный заказ в PROCESSING.

        # Получаем терминальные заказы в PROCESSING (исключаем мобильные)
        terminal_processing_order = WashOrder.objects.exclude(is_mobile_payment=True).filter(status=WashOrder.Status.PROCESSING).first()
        current_terminal_processing_order_id = str(terminal_processing_order.transaction_id) if terminal_processing_order else None

        if terminal_processing_order and current_terminal_processing_order_id != _last_processing_order_id:
            print(f"[DS] Новый или измененный заказ терминала в статусе PROCESSING: {current_terminal_processing_order_id}")
            expected_sum = int(terminal_processing_order.program_price)

            ts = TerminalStatus.objects.first()
            if ts:
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
                        _gvl_sent_for = current_terminal_processing_order_id
                        _last_processing_order_id = current_terminal_processing_order_id
                    else:
                        print(f"[DS] Ожидание подтверждения суммы {expected_sum} от DScloud... (Попытка {retries + 1}/{max_retries})")
                        if response_data:
                            print(f"[DS] Получен ответ: {response_data}")
                        retries += 1
                        if retries == max_retries:
                            print(f"[DS] ОШИБКА: Не удалось получить подтверждение суммы {expected_sum} от DScloud после {max_retries} попыток.")

        # Условие `elif not terminal_processing_order and _gvl_sent_for:` больше не нужно,
        # так как обнуление происходит в общей секции проверки "gvl_sum != 0" в начале функции.
        # Это делает логику более надежной для всех типов заказов.

    except Exception as e:
        print(f"[DS] Критическая ошибка в задаче dscloud_job: {e}")

# ... (другие функции, такие как dscloud_prices_job, start_dscloud_scheduler и т.д.) ...



def dscloud_prices_job():
    """
    Фоновая задача для APScheduler.
    Отправляет данные о ценах программ каждую минуту.
    Эта задача выполняется ВСЕГДА по расписанию, независимо от состояния основного пинга.
    """
    print("[DS-PRICES] Запуск задачи отправки цен (независимо от состояния мойки).")
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
