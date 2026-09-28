from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime

from orders.models.manage_server import ManageServerConfig
import requests

SEND_FILE = "send_data_raw.txt"


def append_to_file(hex_string: str):
    with open(SEND_FILE, "a", encoding="utf-8") as f:
        f.write(hex_string)


def read_file() -> str:
    try:
        with open(SEND_FILE, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return ""


def clear_file():
    open(SEND_FILE, "w").close()


def _encode_datetime(dt: datetime) -> bytes:
    """Упаковывает datetime как 4-байтовое число секунд от 1970-01-01,
    используя значение datetime напрямую (игнорируя tzinfo)."""
    dt = dt.replace(tzinfo=None)

    epoch = datetime(1970, 1, 1)
    ts = int((dt - epoch).total_seconds())
    return ts.to_bytes(4, "little")


@dataclass
class EncodedParams:
    oper: int
    status: int
    data: int
    counter: int
    localId: int
    begDate: datetime
    endDate: datetime
    deviceId: int

    def to_bytes(self) -> bytes:
        """Преобразует параметры в бинарный вид."""
        result = bytearray()

        # oper (1 byte)
        result.append(self.oper & 0xFF)

        # status (1 byte)
        result.append(self.status & 0xFF)

        # data (2 bytes, little-endian)
        result.extend(self.data.to_bytes(2, "little"))

        # counter (4 bytes, little-endian)
        result.extend(self.counter.to_bytes(4, "little"))

        # localId (4 bytes, little-endian)
        result.extend(self.localId.to_bytes(4, "little"))

        # begDate (4 bytes)
        result.extend(_encode_datetime(self.begDate))

        # endDate (4 bytes)
        result.extend(_encode_datetime(self.endDate))

        # deviceId (2 bytes, little-endian)
        result.extend(self.deviceId.to_bytes(2, "little"))

        return bytes(result)

    def to_hex(self) -> str:
        """Возвращает hex-строку (верхний регистр)."""
        return self.to_bytes().hex().upper()

    def send_hex_to_server(self) -> str:
        new_hex = self.to_hex()

        append_to_file(new_hex)
        full_hex = read_file()

        ok_servers = []
        error_servers = []

        for config in ManageServerConfig.get_all():

            if config.type.upper() == "CW":
                url = f"http://{config.ip_address}:{config.port}/cwash/api/service/data_oven"
                headers = {"data": full_hex}

            elif config.type.upper() == "ONVI":
                url = f"http://{config.ip_address}:{config.port}/data/raw"
                headers = {
                    "X-API-KEY": "84c54acb-db24-443d-887e-7a8331f9f9e1",
                    "Data": "{" + full_hex + "}",
                }
            else:
                error_servers.append(f"{config} (unknown type)")
                continue

            try:
                response = requests.post(url, headers=headers, timeout=10)
                response.raise_for_status()

                ok_servers.append(str(config))

                # очищаем файл только если хотя бы один сервер принял данные
                clear_file()

            except Exception as e:
                error_servers.append(f"{config}: {e}")

        if ok_servers and not error_servers:
            return f"OK: sent to {', '.join(ok_servers)}"

        if ok_servers and error_servers:
            return f"PARTIAL: OK[{', '.join(ok_servers)}] ERR[{', '.join(error_servers)}]"

        return f"ERROR: {', '.join(error_servers)}"
