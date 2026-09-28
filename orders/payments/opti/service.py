from .exceptions import OptiError, OptiQrError
from orders.lty_integrations.opti.service import OptiService
import time
from datetime import datetime
from orders.models.terminal_status import TerminalStatus
from ...encoder import EncodedParams


class OptiPaymentService:
    POLL_INTERVAL = 1
    MAX_WAIT_SECONDS = 120

    @staticmethod
    def pay(order):
        opti = OptiService()

        opti.authorize()

        items = [
            {
                "service_id": opti.service_id,
                "price": float(order.program_price),
                "amount": 1,
            }
        ]

        order_response = opti.create_order(items=items)

        opti_order_id = order_response["data"]["uuid"]

        order.transaction_id = opti_order_id
        order.save(update_fields=["transaction_id"])

        qr_response = opti.get_order_qr(opti_order_id)

        qr_base64 = qr_response["data"]

        if not qr_base64:
            raise OptiQrError("QR-код не получен")

        return qr_base64

    @staticmethod
    def wait_for_payment_result(order):
        opti = OptiService()
        opti.authorize()

        elapsed = 0

        while elapsed < OptiPaymentService.MAX_WAIT_SECONDS:
            status_response = opti.get_order(order.transaction_id)
            status_code = status_response["data"]["status"]

            if status_code == 3:
                try:
                    terminal = TerminalStatus.get_terminal()
                    device_id = int(terminal.identifier)
                    now_dt = datetime.now()

                    params = EncodedParams(
                        oper=40,
                        status=1,
                        data=int(order.program_price),
                        counter=0,
                        localId=0,
                        begDate=now_dt,
                        endDate=now_dt,
                        deviceId=device_id
                    )
                    results = params.send_hex_to_server()
                    print(f"[ENCODER_MANAGE] Cash payment sent (oper=40): {results}")
                except Exception as e:
                    print(f"[ENCODER_MANAGE] Error sending bank-card payment event: {e}")
                return "PAID"

            if status_code == -1:
                return "CANCELED"

            time.sleep(OptiPaymentService.POLL_INTERVAL)
            elapsed += OptiPaymentService.POLL_INTERVAL

        raise TimeoutError("Таймаут ожидания оплаты Opti")

    @staticmethod
    def cancel(order) -> bool:

        try:
            opti = OptiService()
            opti.authorize()

            opti.cancel_order(order.transaction_id)

            print(f"[OPTI] Заказ {order.transaction_id} успешно отменён в Opti")
            return True

        except Exception as e:
            print(f"[OPTI] Ошибка отмены заказа {order.transaction_id}: {e}")
            return False
