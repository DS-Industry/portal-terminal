# orders/ucn.py
import requests
import logging
import time
from django.core.exceptions import ObjectDoesNotExist
from .models import ManageServerConfig, LoyaltySettings, TerminalStatus

logger = logging.getLogger(__name__)


class LoyaltyManager:
    """
    Менеджер для работы с картами лояльности
    """

    @classmethod
    def read_card_ucn(cls, port="COM1", baudrate=9600, timeout=1, max_wait=30):
        """
        Чтение карты с терминала.
        Возвращает корректный УН (ucn_number) как строку.
        """
        try:
            print("[LOYALTY] Ожидаем карту...")
            response = requests.get("http://host.docker.internal:5001/ucn", timeout=35)
            print(f"[LOYALTY] Получили: {response}")
            print(f"[LOYALTY] Номер: {response.json().get("ucn_number", -1)}")
            return response.json().get("ucn_number", -1)
        except Exception as e:
            print(f"[LOYALTY] Ошибка подключения к считывателю: {e}")
            return -1

    @classmethod
    def get_active_server(cls):
        """
        Получает первый активный сервер с включенной лояльностью
        Returns:
            ManageServerConfig or None
        """
        try:
            return ManageServerConfig.objects.filter(loyalty_status=True).first()
        except Exception as e:
            print(f"[LOYALTY] Ошибка при получении активного сервера лояльности: {e}")
            return None

    @classmethod
    def get_balance(cls, ucn_number):
        """
        Получает баланс карты лояльности
        Args:
            ucn_number (str): Номер карты лояльности

        Returns:
            dict: Результат запроса баланса
        """
        server = cls.get_active_server()

        if not server:
            return {
                'success': False,
                'error': 'Активный сервер лояльности не найден',
                'balance': None,
                'discount': None,
                'cashback': None
            }

        print(f"[LOYALTY] Тип сервера: {server.type}")

        # Логика в зависимости от типа сервера
        if server.type == "CW":
            return cls._get_balance_cw(server, ucn_number)
        elif server.type == "ONVI":
            return cls._get_balance_onvi(server, ucn_number)
        else:
            return cls._get_balance_default(server, ucn_number)

    @classmethod
    def _get_balance_cw(cls, server, ucn_number):
        """
        Логика для серверов типа CW
        """
        try:
            terminal = TerminalStatus.objects.first()
            if not terminal:
                raise Exception("TerminalStatus не найден")

            dev_id = terminal.identifier

            url = f"http://{server.ip_address}:{server.port}/cwash/api/service/card_balance"
            headers = {
                "dev_id": str(dev_id),
                "ucn": str(ucn_number),
                "token": "0"
            }

            response = requests.post(url, headers=headers, timeout=10)
            response.raise_for_status()

            data = response.json()

            return {
                'success': True,
                'balance': data.get('balance'),
                'discount': data.get('discount', 0),
                'cashback': data.get('cashback', 0),
                'card_number': ucn_number,
                'server_type': 'CW'
            }

        except requests.exceptions.RequestException as e:
            print(f"[LOYALTY] Ошибка запроса к серверу CW {server.ip_address}: {e}")
            return {
                'success': False,
                'error': f'Ошибка соединения с сервером CW: {str(e)}',
                'balance': None,
                'discount': None,
                'cashback': None
            }
        except Exception as e:
            print(f"[LOYALTY] Неожиданная ошибка при запросе баланса CW: {e}")
            return {
                'success': False,
                'error': f'Внутренняя ошибка: {str(e)}',
                'balance': None,
                'discount': None,
                'cashback': None
            }

    @classmethod
    def _get_balance_onvi(cls, server, ucn_number):
        """
        Логика для серверов типа ONVI
        """
        try:
            terminal = TerminalStatus.objects.first()
            if not terminal:
                raise Exception("TerminalStatus не найден")

            dev_id = terminal.identifier

            url = f"http://{server.ip_address}:{server.port}/device/loyalty/card-balance"
            headers = {
                "deviceId": str(dev_id),
                "devNumber": str(ucn_number),
                "token": "0"
            }

            response = requests.post(url, headers=headers, timeout=10)
            response.raise_for_status()

            data = response.json()

            return {
                'success': True,
                'balance': data.get('points_balance'),
                'discount': data.get('discount_percent', 0),
                'cashback': data.get('cashback_percent', 0),
                'card_number': ucn_number,
                'server_type': 'ONVI'
            }

        except requests.exceptions.RequestException as e:
            print(f"[LOYALTY] Ошибка запроса к серверу ONVI {server.ip_address}: {e}")
            return {
                'success': False,
                'error': f'Ошибка соединения с сервером ONVI: {str(e)}',
                'balance': None,
                'discount': None,
                'cashback': None
            }
        except Exception as e:
            print(f"[LOYALTY] Неожиданная ошибка при запросе баланса ONVI: {e}")
            return {
                'success': False,
                'error': f'Внутренняя ошибка: {str(e)}',
                'balance': None,
                'discount': None,
                'cashback': None
            }

    @classmethod
    def _get_balance_default(cls, server, ucn_number):
        """
        Логика для других типов серверов
        """
        print(f"[LOYALTY] Неизвестный тип сервера лояльности: {server.type}")

        return {
            'success': False,
            'error': f'Неизвестный тип сервера: {server.type}',
            'balance': None,
            'discount': None,
            'cashback': None,
            'server_type': server.type
        }

    @classmethod
    def update_local_settings(cls, ucn_number, balance, discount, cashback):
        """
        Обновляет локальные настройки лояльности
        """
        try:
            LoyaltySettings.create_or_replace_settings(
                ucn=ucn_number,
                discount=discount,
                cashback=cashback,
                balance=balance
            )
            print(f"[LOYALTY] Локальные настройки лояльности обновлены для карты {ucn_number}")
            return True
        except Exception as e:
            print(f"[LOYALTY] Ошибка при обновлении локальных настроек лояльности: {e}")
            return False

    @classmethod
    def get_balance_and_update(cls, ucn_number):
        """
        Получает баланс с сервера и обновляет локальные настройки
        """

        if ucn_number == -1:
            cls.update_local_settings(
                ucn_number=-1,
                balance=-1,
                discount=-1,
                cashback=-1
            )
            return {
                'success': False,
                'balance': -1,
                'discount': -1,
                'cashback': -1,
                'ucn_number': -1
            }

        print(f"[LOYALTY] Поиск карты в системе лояльности: {ucn_number}")
        result = cls.get_balance(ucn_number)

        if result['success']:
            cls.update_local_settings(
                ucn_number=ucn_number,
                balance=result['balance'],
                discount=result['discount'],
                cashback=result['cashback']
            )
        else:
            cls.update_local_settings(
                ucn_number=-1,
                balance=-1,
                discount=-1,
                cashback=-1
            )

        return result


def get_balance_and_update_local(ucn_number):
    """Получить баланс и обновить локальные настройки"""
    return LoyaltyManager.get_balance_and_update(ucn_number)


def get_active_loyalty_server():
    """Получить активный сервер лояльности"""
    return LoyaltyManager.get_active_server()
