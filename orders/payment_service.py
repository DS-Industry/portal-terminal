from orders.models.wash_order import PaymentFailed, OrderCanceled
from datetime import datetime
from .payment import (
    bank_card_payment,
    cash_payment,
    loyalty_card_payment,
    mobile_app_payment,
)
from .encoder import EncodedParams
from .payments.opti.service import OptiPaymentService
from .websocket_service import OrderWebSocketService
import time


class PaymentService:

    @staticmethod
    def process_payment(order, terminal, payment_type, ucn=None):

        order.ensure_not_canceled()

        if payment_type == "cash":
            print(f"[CASH_PAYMENT] Начало обработки оплаты по наличке для заказа {order.transaction_id}")
            #success, error_message = cash_payment(order)
            time.sleep(15)
            success, error_message = True, ""

            order.ensure_not_canceled()

            if not success:
                order.mark_failed()
                raise PaymentFailed(f"Ошибка оплаты по наличке: {error_message}", ws_code=1001)

        elif payment_type == "bank_card":
            print(f"[VENDOTEK] Начало обработки оплаты по банковской карте для заказа {order.transaction_id}")
            #success, error_message = bank_card_payment(order)

            time.sleep(15)
            success, error_message = True, ""

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
            print("[LOYALTY] Начало обработки оплаты по OPTI для заказа")
            qr = OptiPaymentService.pay(order)
            OrderWebSocketService.send_qr_opti(order, qr)

            result = OptiPaymentService.wait_for_payment_result(order)
            order.ensure_not_canceled()

            if result == "CANCELED":
                try:
                    order.ensure_not_canceled()
                except OrderCanceled:
                    raise PaymentFailed(
                        "Оплата отменена (заказ уже был отменен)",
                        ws_code=1006
                    )

                order.mark_failed()
                raise PaymentFailed(
                    "Оплата отменена в Opti",
                    ws_code=1006
                )

        else:
            raise PaymentFailed("Неверный тип оплаты", ws_code=1005)

        print(f"[CASH_PAYMENT] Оплата успешно завершена для заказа {order.transaction_id}")

    @staticmethod
    def _send_bank_event(order, terminal):
        try:
            device_id = int(terminal.identifier)
            now_dt = datetime.now()

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
