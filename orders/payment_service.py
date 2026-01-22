from orders.models.wash_order import PaymentFailed
from django.utils import timezone
from .payments import (
    bank_card_payment,
    cash_payment,
    loyalty_card_payment,
    mobile_app_payment,
)
from .encoder import EncodedParams
from .websocket_service import OrderWebSocketService
import time


class PaymentService:

    @staticmethod
    def process_payment(order, terminal, payment_type, ucn=None):

        order.ensure_not_canceled()

        if payment_type == "cash":
            print(f"[CASH_PAYMENT] Начало обработки оплаты по наличке для заказа {order.transaction_id}")
            success, error_message = cash_payment(order)

            order.ensure_not_canceled()

            if not success:
                order.mark_failed()
                raise PaymentFailed(f"Ошибка оплаты по наличке: {error_message}", ws_code=1001)

        elif payment_type == "bank_card":
            print(f"[VENDOTEK] Начало обработки оплаты по банковской карте для заказа {order.transaction_id}")
            success, error_message = bank_card_payment(order)

            order.ensure_not_canceled()

            if not success:
                order.mark_failed()
                raise PaymentFailed(f"Ошибка оплаты по карте: {error_message}", ws_code=1002)

            PaymentService._send_bank_event(order, terminal)

        elif payment_type == "mobile_app":
            return mobile_app_payment(order)

        elif payment_type == "loyalty_card":
            print(f"[LOYALTY] Начало обработки оплаты по карте лояльности для заказа {order.transaction_id}")
            success, error_message = loyalty_card_payment(order, ucn)

            order.ensure_not_canceled()

            if not success:
                order.mark_failed()
                raise PaymentFailed(f"Ошибка оплаты по лояльности: {error_message}", ws_code=1003)

        elif payment_type == "opti":
            print(f"[LOYALTY] Начало обработки оплаты по OPTI для заказа {order.transaction_id}")
            qr = "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"
            OrderWebSocketService.send_qr_opti(order, qr)
            time.sleep(10)


        else:
            raise PaymentFailed("Неверный тип оплаты", ws_code=1005)

        print(f"[CASH_PAYMENT] Оплата успешно завершена для заказа {order.transaction_id}")

    @staticmethod
    def _send_bank_event(order, terminal):
        try:
            device_id = int(terminal.identifier)
            now_dt = timezone.now()

            params = EncodedParams(
                oper=23,
                status=1,
                data=int(order.program_price),
                counter=0,
                localId=0,
                begDate=now_dt,
                endDate=now_dt,
                deviceId=device_id
            )
            params.send_hex_to_server()
        except Exception as e:
            print(f"[ENCODER_MANAGE] Error sending bank-card payment event: {e}")
