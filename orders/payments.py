import os
import requests
import time

from pathlib import Path

from rest_framework.response import Response

from .models import (
    TerminalStatus,
    WashOrder,
)

from .vendotek import VendotekClient
from .bill_holder_service import payment_process

BASE_DIR = Path(__file__).resolve().parent.parent
env_file = BASE_DIR / ".env"

try:
    CARWASH_IP = os.getenv("CARWASH_IP")
    CARWASH_PORT = os.getenv("CARWASH_PORT")
except Exception as e:
    print(f"Ошибка при загрузке переменных окружения CARWASH: {e}")


def bank_card_payment(order):
    client = VendotekClient.from_db()
    if not client:
        print("[VENDOTEK] Не удалось получить конфигурацию терминала")
        return False, "Не удалось получить конфигурацию терминала"

    if not client.connect():
        print("[VENDOTEK] Ошибка подключения к терминалу")
        return False, "Ошибка подключения к терминалу"

    try:
        amount = int(order.program_price)

        response = client.process_payment(amount)

        if not response.success:
            print(f"[VENDOTEK] Ошибка оплаты: {response.error_message}")
            return False, response.error_message

        return True, ""

    except Exception as e:
        error_msg = f"Неожиданная ошибка при обработке оплаты картой: {e}"
        print(f"[VENDOTEK] {error_msg}")
        return False, error_msg

    finally:
        client.disconnect()


def cash_payment(order):
    """
    Симуляция оплаты наличными.
    """
    success = payment_process(order)
    if not success:
        print(f"[CASH_PAYMENT] Ошибка наличной оплаты")
        return False, "[CASH_PAYMENT] Ошибка наличной оплаты"

    return True, ""


def loyalty_card_payment(order, ucn):
    """
    Обрабатывает оплату по карте лояльности.
    Выполняет запрос на списание средств.
    """
    try:
        terminal = TerminalStatus.objects.first()
        if not terminal:
            raise Exception("TerminalStatus не найден")

        dev_id = terminal.identifier
        sum_amount = int(order.program_price)

        url = f"http://{CARWASH_IP}:{CARWASH_PORT}/cwash/api/service/card_oper"
        headers = {
            "dev_id": str(dev_id),
            "ucn": str(ucn),
            "token": "0",
            "sum": str(sum_amount)
        }

        response = requests.post(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()

        errcode = data.get("errcode")
        if errcode == 200:
            print(f"[LOYALTY] Списание успешно для заказа {order.transaction_id}")
            return True, ""
        else:
            errmes = data.get("errmes", "Неизвестная ошибка")
            print(f"[LOYALTY] Ошибка списания для заказа {order.transaction_id}: {errmes}")
            return False, errmes

    except requests.exceptions.RequestException as e:
        error_msg = f"Ошибка сети при запросе к сервису лояльности: {e}"
        print(f"[LOYALTY] {error_msg}")
        return False, error_msg
    except Exception as e:
        error_msg = f"Неожиданная ошибка при обработке оплаты лояльностью: {e}"
        print(f"[LOYALTY] {error_msg}")
        return False, error_msg


def mobile_app_payment(order):
    """
    Обрабатывает запрос на переход в старое мобильное приложение.
    Меняет статус заказа и возвращает статический QR-код.

    Принимает:
        order (WashOrder): Заказ, для которого запрашивается переход.

    Возвращает:
        Response: DRF Response с QR-кодом или ошибкой.
    """

    order.status = WashOrder.Status.MOBILE_QR_REQUEST
    terminal_status = TerminalStatus.objects.first()
    if not terminal_status or not terminal_status.mobile_app_qr_code:
        error_msg = "QR-код для старого мобильного приложения не настроен в TerminalStatus."
        print(f"[MOBILE-PAYMENT-QR] ОШИБКА: {error_msg}")
        return Response({'error': error_msg}, status=500)

    qr_code_string = terminal_status.mobile_app_qr_code
    order.save()
    print(f"[MOBILE-PAYMENT-QR] Статус заказа {order.transaction_id} обновлён на MOBILE_QR_REQUEST. QR-код получен.")

    return Response({
        'qr_code': qr_code_string
    }, status=200)
