import socket
import struct
from typing import Optional
from dataclasses import dataclass

from orders.models.vendotek_server import VendotekServerConfig

@dataclass
class VendotekResponse:
    """Ответ от терминала Vendotek"""
    success: bool
    message_type: str = ""
    operation_number: str = ""
    approved_amount: str = ""
    timeout: str = ""
    event_number: str = ""
    local_time: str = ""
    error_message: str = ""


class VendotekClient:

    def __init__(self, ip_address: str, port: int, timeout: int = 60):
        self.ip_address = ip_address
        self.port = port
        self.timeout = timeout
        self.socket: Optional[socket.socket] = None
        self.operation_number = 1

    @classmethod
    def from_db(cls, timeout: int = 60) -> Optional["VendotekClient"]:
        conf = VendotekServerConfig.get()
        if not conf:
            print("[VENDOTEK] Нет настроек в VendotekServerConfig")
            return None
        return cls(ip_address=conf.ip_address, port=conf.port, timeout=timeout)

    def connect(self) -> bool:
        """Установка соединения с терминалом"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(self.timeout)
            self.socket.connect((self.ip_address, self.port))
            print(f"[VENDOTEK] Соединение установлено с {self.ip_address}:{self.port}")
            return True
        except Exception as e:
            print(f"[VENDOTEK] Ошибка подключения: {e}")
            return False

    def disconnect(self):
        """Закрытие соединения"""
        if self.socket:
            try:
                self.socket.close()
                print("[VENDOTEK] Соединение закрыто")
            except Exception as e:
                print(f"[VENDOTEK] Ошибка при закрытии соединения: {e}")
            finally:
                self.socket = None

    def _split_amount(self, amount: int) -> tuple:
        """Разбивает сумму на отдельные цифры для протокола"""
        if amount < 10:
            return (0, 0, 0, amount)
        elif amount < 100:
            return (0, 0, amount // 10, amount % 10)
        elif amount < 1000:
            return (0, amount // 100, (amount // 10) % 10, amount % 10)
        elif amount < 10000:
            return (amount // 1000, (amount // 100) % 10, (amount // 10) % 10, amount % 10)
        else:
            raise ValueError(f"Сумма {amount} слишком большая (максимум 9999)")

    def _build_message(self, tlvs: bytearray) -> bytes:
        """Собирает кадр: [len(2)][96 FB][TLVs...]"""
        body = bytearray()
        body.extend((0x96, 0xFB))
        body.extend(tlvs)
        length = len(body)
        length_bytes = length.to_bytes(2, 'big')
        return bytes(length_bytes + body)

    def _create_idl_message(self) -> bytes:
        """Создает минимальное сообщение IDL (как в старом коде ПЛК)"""
        tlvs = bytearray()
        # 0x01 'IDL'
        tlvs.extend((0x01, 0x03))
        tlvs.extend(b'IDL')
        return self._build_message(tlvs)

    def _create_vrp_message(self, amount: int, operation_number: str) -> bytes:
        """Создает VRP сообщение (как в старом коде ПЛК).
        Содержит только MessageName, Amount, OperationNumber.
        """
        tlvs = bytearray()

        # 0x01 MessageName = "VRP"
        tlvs.extend((0x01, 0x03))
        tlvs.extend(b"VRP")

        # 0x04 AmountMinorCurrency (в копейках, ASCII)
        amount_minor = str(amount * 100).encode("ascii")
        tlvs.extend((0x04, len(amount_minor)))
        tlvs.extend(amount_minor)

        # 0x03 OperationNumber (ASCII)
        op_num_bytes = operation_number.encode("ascii")
        tlvs.extend((0x03, len(op_num_bytes)))
        tlvs.extend(op_num_bytes)

        return self._build_message(tlvs)

    def _create_fin_message(self, amount: int, operation_number: str) -> bytes:
        """FIN как в старом коде ПЛК"""
        tlvs = bytearray()
        # MessageName
        tlvs.extend((0x01, 0x03))
        tlvs.extend(b"FIN")
        # AmountMinorCurrency (в копейках)
        amount_minor = str(amount * 100).encode("ascii")
        tlvs.extend((0x04, len(amount_minor)))
        tlvs.extend(amount_minor)
        # OperationNumber
        op_num_bytes = operation_number.encode("ascii")
        tlvs.extend((0x03, len(op_num_bytes)))
        tlvs.extend(op_num_bytes)
        return self._build_message(tlvs)

    def _create_abr_message(self) -> bytes:
        """ABR как в старом коде ПЛК"""
        tlvs = bytearray()
        tlvs.extend((0x01, 0x03))
        tlvs.extend(b"ABR")
        return self._build_message(tlvs)

    def _send_message(self, message: bytes) -> bool:
        """Отправляет сообщение терминалу"""
        try:
            if not self.socket:
                raise Exception("Соединение не установлено")

            self.socket.sendall(message)
            return True
        except Exception as e:
            print(f"[VENDOTEK] Ошибка отправки: {e}")
            return False

    def _receive_response(self) -> Optional[bytes]:
        """Получает ответ от терминала"""
        try:
            if not self.socket:
                raise Exception("Соединение не установлено")

            length_data = self.socket.recv(2)
            if len(length_data) != 2:
                raise Exception("Не удалось получить длину сообщения")

            message_length = struct.unpack('>H', length_data)[0]

            response_data = self.socket.recv(message_length)
            if len(response_data) != message_length:
                raise Exception(f"Получено {len(response_data)} байт, ожидалось {message_length}")

            full_response = length_data + response_data
            return full_response

        except Exception as e:
            print(f"[VENDOTEK] Ошибка получения ответа: {e}")
            return None

    def _parse_response(self, response: bytes) -> VendotekResponse:
        """Парсит ответ от терминала"""
        try:
            if len(response) < 4:
                return VendotekResponse(success=False, error_message="Слишком короткий ответ")

            if response[2] != 0x97 or response[3] != 0xFB:
                return VendotekResponse(success=False, error_message="Неверный заголовок ответа")

            result = VendotekResponse(success=True)

            i = 4
            while i < len(response) - 1:
                param_id = response[i]
                param_len = response[i + 1]

                if i + 2 + param_len > len(response):
                    break

                param_data = response[i + 2:i + 2 + param_len]

                if param_id == 1:  # Тип сообщения
                    result.message_type = param_data.decode('ascii', errors='ignore')
                elif param_id == 3:  # Номер операции
                    result.operation_number = param_data.decode('ascii', errors='ignore')
                elif param_id == 4:  # Одобренная сумма
                    result.approved_amount = param_data.decode('ascii', errors='ignore')
                elif param_id == 6:  # Timeout
                    result.timeout = param_data.decode('ascii', errors='ignore')
                elif param_id == 8:  # Номер события
                    result.event_number = param_data.decode('ascii', errors='ignore')
                elif param_id == 17:  # Локальное время
                    result.local_time = param_data.decode('ascii', errors='ignore')

                i += 2 + param_len

            return result

        except Exception as e:
            return VendotekResponse(success=False, error_message=f"Ошибка парсинга: {e}")

    def send_idl(self) -> VendotekResponse:
        message = self._create_idl_message()
        if not self._send_message(message):
            return VendotekResponse(success=False, error_message="Ошибка отправки IDL")
        response = self._receive_response()
        if not response:
            return VendotekResponse(success=False, error_message="Нет ответа на IDL")
        return self._parse_response(response)

    def send_vrp(self, amount: int) -> VendotekResponse:
        message = self._create_vrp_message(amount, str(self.operation_number))
        if not self._send_message(message):
            return VendotekResponse(success=False, error_message="Ошибка отправки VRP")
        response = self._receive_response()
        if not response:
            return VendotekResponse(success=False, error_message="Нет ответа на VRP")
        return self._parse_response(response)

    def send_fin(self, amount: int) -> VendotekResponse:
        message = self._create_fin_message(amount, str(self.operation_number))
        if not self._send_message(message):
            return VendotekResponse(success=False, error_message="Ошибка отправки FIN")
        response = self._receive_response()
        if not response:
            return VendotekResponse(success=False, error_message="Нет ответа на FIN")
        return self._parse_response(response)

    def send_abr(self) -> VendotekResponse:
        """Отправляет команду отмены"""
        message = self._create_abr_message()
        if not self._send_message(message):
            return VendotekResponse(success=False, error_message="Ошибка отправки ABR")

        response = self._receive_response()
        if not response:
            return VendotekResponse(success=False, error_message="Нет ответа на ABR")

        return self._parse_response(response)

    def process_payment(self, amount: int) -> VendotekResponse:
        """Выполняет полный цикл оплаты"""
        try:
            # 1. Инициализация
            idl_response = self.send_idl()
            if not idl_response.success:
                return idl_response

            try:
                self.operation_number = int(idl_response.operation_number) + 1 if idl_response.operation_number else 1
            except Exception:
                self.operation_number = 1

            vrp_response = self.send_vrp(amount)
            print(f"[VENDOTEK] vrp_resp: {vrp_response}")
            if not vrp_response.success:
                return vrp_response

            approved = int(vrp_response.approved_amount)/100 if vrp_response.approved_amount else 0

            if approved != amount:
                self.send_idl()
                return VendotekResponse(
                    success=False,
                    error_message=f"Сумма оплаты не совпадает: ожидали {amount}, получили {approved}"
                )


            fin_response = self.send_fin(amount)
            if not fin_response.success:
                return fin_response


            idl_response_end = self.send_idl()
            if not idl_response_end.success:
                return idl_response_end

            return VendotekResponse(
                success=True,
                message_type="PAYMENT_COMPLETED",
                operation_number=vrp_response.operation_number,
                approved_amount=vrp_response.approved_amount
            )

        except Exception as e:
            return VendotekResponse(success=False, error_message=f"Ошибка процесса оплаты: {e}")