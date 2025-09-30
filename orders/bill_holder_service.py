import logging
from typing import Optional
import time

from django.conf import settings

from .modbus_client import ModbusClient
from modbus_config import DEFAULT_HOST_BILL_HOLDER, DEFAULT_PORT_BILL_HOLDER, DEFAULT_TIMEOUT_BILL_HOLDER

logger = logging.getLogger(__name__)
from .models import TerminalStatus
from .encoder import EncodedParams
from django.utils import timezone


class BillHolderService:

    def __init__(self, host: str, port: int, timeout: int):
        self.client = ModbusClient(host, port, timeout)
        self.connected = False
        self.cash_register_address = 16388

    def connect(self) -> bool:
        """Connect to PLC"""
        self.connected = self.client.connect()
        if self.connected:
            logger.info("Connected to BillHolder")
        else:
            logger.error("Failed to connect to BillHolder")
        return self.connected

    def disconnect(self):
        """Disconnect from PLC"""
        if self.connected:
            self.client.disconnect()
            self.connected = False
            logger.info("Disconnected from BillHolder")

    def read_cash_amount(self) -> Optional[int]:
        """Чтение номинала внесенной купюры"""
        if not self.connected:
            logger.error("Not connected to BillHolder")
            return None

        try:
            cash_value = self.client.read_register(self.cash_register_address)
            if cash_value is not None:
                logger.info(f"BillHolder: прочитана купюра номиналом {cash_value}")
                return cash_value
            else:
                logger.warning("BillHolder: не удалось прочитать купюру")
                return None
        except Exception as e:
            logger.error(f"BillHolder: ошибка чтения купюры: {e}")
            return None

    def wait_for_payment(self, order, poll_interval: float = 0.5) -> bool:
        """
        Ожидание полной оплаты заказа

        Args:
            order: объект заказа WashOrder
            poll_interval: интервал опроса купюроприемника в секундах

        Returns:
            bool: True если оплата завершена успешно, False при ошибке
        """
        if not self.connected:
            logger.error("Cannot wait for payment - not connected to BillHolder")
            return False

        logger.info(f"BillHolder: начало приема оплаты для заказа {order.id}. Сумма к оплате: {order.program_price}")

        try:
            while True:
                # Читаем номинал купюры
                cash_nominal = self.read_cash_amount()

                if cash_nominal is not None and cash_nominal > 0:
                    # Добавляем купюру к сумме
                    order.amount_sum += cash_nominal
                    order.save(update_fields=['amount_sum'])

                    logger.info(
                        f"BillHolder: внесено {cash_nominal}. Текущая сумма: {order.amount_sum}/{order.program_price}")

                    try:
                        ts = TerminalStatus.objects.first()
                        device_id = int(ts.identifier) if ts and ts.identifier is not None else 0
                        now_dt = timezone.now()

                        params = EncodedParams(
                            oper=2,
                            status=1,
                            data=int(cash_nominal),
                            counter=0,
                            localId=0,
                            begDate=now_dt,
                            endDate=now_dt,
                            deviceId=device_id
                        )
                        results = params.send_hex_to_server()
                        print(f"[ENCODER_MANAGE] Cash payment sent (oper=2): {results}")
                    except Exception as e:
                        print(f"[ENCODER_MANAGE] Error sending bank-card payment event: {e}")

                    # Проверяем, достигли ли нужной суммы
                    if order.amount_sum >= order.program_price:
                        logger.info(
                            f"BillHolder: оплата завершена. Внесено: {order.amount_sum}, требуется: {order.program_price}")
                        return True

                # Проверяем, не был ли отменен заказ
                order.refresh_from_db()
                if order.status == 'failed':
                    logger.info("BillHolder: оплата прервана - заказ отменен")
                    return False

                # Ждем перед следующим опросом
                time.sleep(poll_interval)

        except Exception as e:
            logger.error(f"BillHolder: ошибка во время приема оплаты: {e}")
            return False

    def process_cash_payment(self, order) -> bool:
        """
        Полный процесс обработки наличной оплаты

        Args:
            order: объект заказа WashOrder

        Returns:
            bool: True если оплата успешна, False при ошибке
        """
        logger.info(f"BillHolder: запуск процесса наличной оплаты для заказа {order.id}")

        try:
            # Подключаемся к купюроприемнику
            if not self.connect():
                return False

            # Ожидаем полную оплату
            success = self.wait_for_payment(order)

            return success

        except Exception as e:
            logger.error(f"BillHolder: критическая ошибка при обработке оплаты: {e}")
            return False
        finally:
            # Всегда отключаемся
            self.disconnect()


def payment_process(order):
    """
    Обработка оплаты наличными через купюроприемник
    """
    logger.info(f"[CASH] Запуск наличной оплаты для заказа {order.id}")

    # Создаем сервис и обрабатываем оплату
    bill_service = BillHolderService(DEFAULT_HOST_BILL_HOLDER, DEFAULT_PORT_BILL_HOLDER, DEFAULT_TIMEOUT_BILL_HOLDER)
    success = bill_service.process_cash_payment(order)

    if success:
        logger.info(f"[CASH] Оплата наличными завершена успешно для заказа {order.id}")
        print(f"[LOG] Оплата наличными прошла успешно. Внесено: {order.amount_sum}")
    else:
        logger.error(f"[CASH] Ошибка наличной оплаты для заказа {order.id}")
        print(f"[LOG] Ошибка оплаты наличными")

    return success
