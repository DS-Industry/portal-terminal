import json
import requests

from typing import Optional

from orders.models.terminal_status import TerminalStatus
from orders.models.receipt_server import ReceiptServerConfig


def send_receipt_request(order) -> Optional[str]:
    """
    Отправляет POST-запрос на сервер печати чека.
    Возвращает строку QR-кода или None при ошибке.
    """
    try:
        server_conf = ReceiptServerConfig.get()
        if not server_conf:
            print("[QR] Не настроен IP-адрес кассы в ReceiptServerConfig.")
            return None

        terminal = TerminalStatus.get_terminal()

        payload = {
            "name": "1",  # всегда "1" = робот
            "bay": str(terminal.bay_number),
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
