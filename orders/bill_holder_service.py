import logging
from typing import Optional
import time
import os
from pathlib import Path
from .websocket_service import OrderWebSocketService
from .modbus_client import ModbusClient
logger = logging.getLogger(__name__)
from .encoder import EncodedParams
from datetime import datetime
from orders.models.terminal_status import TerminalStatus

BASE_DIR = Path(__file__).resolve().parent.parent
env_file = BASE_DIR / ".env"

try:
    env_host = os.getenv("DEFAULT_HOST_BILL_HOLDER")
    env_port = os.getenv("DEFAULT_PORT_BILL_HOLDER")
    env_timeout = os.getenv("DEFAULT_TIMEOUT_BILL_HOLDER")

    if env_host:
        DEFAULT_HOST_BILL_HOLDER = env_host

    if env_port and env_port.isdigit():
        DEFAULT_PORT_BILL_HOLDER = int(env_port)

    if env_timeout and env_timeout.isdigit():
        DEFAULT_TIMEOUT_BILL_HOLDER = int(env_timeout)
except Exception as e:
    print(f"Ошибка при загрузке переменных окружения: {e}")


class BillHolderService:

    def __init__(self, host: str, port: int, timeout: int):
        self.client = ModbusClient(host, port, timeout)
        self.connected = False
        self.cash_register_address = 16388
        self.ask_register_address = 16391

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
        print(f"[BILL-HOLDER] начало приема оплаты для заказа {order.id}. Сумма к оплате: {order.program_price}")

        max_idle_seconds = 30
        start_wait_time = time.monotonic()
        first_cash_received = False

        try:
            while True:

                if not first_cash_received:
                    elapsed = time.monotonic() - start_wait_time
                    if elapsed >= max_idle_seconds:
                        logger.info(
                            f"[BILL-HOLDER] Таймаут ожидания первой купюры "
                            f"({max_idle_seconds} сек). Заказ отменён."
                        )
                        print(
                            f"[BILL-HOLDER] Таймаут ожидания первой купюры. "
                            f"Заказ {order.id} отменён."
                        )

                        order.mark_failed()
                        OrderWebSocketService.send_error(1001)
                        return False

                # Читаем номинал купюры
                cash_nominal = self.read_cash_amount()

                if cash_nominal is not None and cash_nominal > 0:

                    first_cash_received = True

                    ack_success = self.client.write_register(self.ask_register_address, 1)

                    if not ack_success:
                        logger.error("BillHolder: ошибка подтверждения чтения купюры")
                        print(f"[BILL-HOLDER] ошибка подтверждения чтения купюры")

                    while True:
                        time.sleep(0.1)

                        current_cash = self.read_cash_amount()
                        if current_cash == 0:
                            logger.info("BillHolder: оборудование обнулило сумму")
                            print(f"[BILL-HOLDER] оборудование обнулило сумму")
                            break

                        order.refresh_from_db()
                        if order.status == 'failed':
                            print(f"[BILL-HOLDER] оплата прервана во время ожидания обнуления")
                            self.client.write_register(self.ask_register_address, 0)
                            return False

                    final_ack_success = self.client.write_register(self.ask_register_address, 0)
                    if not final_ack_success:
                        logger.error("BillHolder: ошибка завершения обработки купюры")
                        print(f"[BILL-HOLDER] ошибка завершения обработки купюры")

                    # Добавляем купюру к сумме
                    order.amount_sum += cash_nominal
                    order.save(update_fields=['amount_sum'])

                    logger.info(
                        f"BillHolder: внесено {cash_nominal}. Текущая сумма: {order.amount_sum}/{order.program_price}")
                    print(
                        f"[BILL-HOLDER] внесено {cash_nominal}. Текущая сумма: {order.amount_sum}/{order.program_price}")

                    try:
                        terminal = TerminalStatus.get_terminal()
                        device_id = int(terminal.identifier)
                        now_dt = datetime.now()

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
                            f"[BILL-HOLDER] Оплата завершена. Внесено: {order.amount_sum}, требуется: {order.program_price}")
                        print(f"[BILL-HOLDER] Оплата наличными прошла успешно. Внесено: {order.amount_sum}")
                        return True

                # Проверяем, не был ли отменен заказ
                order.refresh_from_db()
                if order.status in ('failed', 'canceled'):
                    logger.info(f"[BILL-HOLDER] оплата прервана - заказ [{order.status}]")
                    return False

                # Ждем перед следующим опросом
                time.sleep(poll_interval)

        except Exception as e:
            logger.error(f"[BILL-HOLDER] ошибка во время приема оплаты: {e}")
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
