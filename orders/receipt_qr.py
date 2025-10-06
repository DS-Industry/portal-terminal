import json
import requests

from typing import Optional

from .models import (
    ReceiptServerConfig,
    TerminalStatus,
    WashOrder,
    )


def send_receipt_request(order: WashOrder) -> Optional[str]:
    """
    Отправляет POST-запрос на сервер печати чека.
    Возвращает строку QR-кода или None при ошибке.
    """
    try:
        server_conf = ReceiptServerConfig.objects.first()
        if not server_conf:
            print("[QR] Не настроен IP-адрес кассы в ReceiptServerConfig.")
            return None

        bay_row = TerminalStatus.objects.first()
        if not bay_row:
            print("[QR] В таблице TerminalStatus нет записей.")
            return None

        payload = {
            "name": "1",  # всегда "1" = робот
            "bay": str(bay_row.bay_number),
            "sum": str(order.program_price),
            "type": "0" if order.payment_type == "cash" else "1"
        }

        headers = {
            "Content-Type": "application/json",
            "Data": json.dumps(payload)
        }

        url = f"http://{server_conf.ip_address}/create-check"

        response = requests.post(url, headers=headers, timeout=15)
        response.raise_for_status()
        data = response.json()
        return data.get("qr")
    except Exception as e:
        print(f"[QR] Ошибка при отправке чека: {e}")
        return None
