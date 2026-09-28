import json
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.utils import timezone


class OrderWebSocketService:
    @staticmethod
    def send_order_status_update(order):
        """Отправка обновления статуса заказа через WebSocket"""
        channel_layer = get_channel_layer()

        print(f"[WEB-SOCKET] Отправка изменения статуса для заказа: {order.transaction_id}")
        async_to_sync(channel_layer.group_send)(
            'order_status_updates',
            {
                'type': 'order_status_update',
                'order_id': str(order.id),
                'status': order.status,
                'transaction_id': order.transaction_id,
                'timestamp': timezone.now().isoformat()
            }
        )

    @staticmethod
    def send_error(err: int):
        """Отправка уведомления о создании нового заказа"""
        channel_layer = get_channel_layer()

        print(f"[WEB-SOCKET] Отправка ошибки")
        async_to_sync(channel_layer.group_send)(
            'order_status_updates',
            {
                'type': 'order_error',
                'code': err
            }
        )

    @staticmethod
    def send_card_reader(code: int):
        """Отправка уведомления о создании нового заказа"""
        channel_layer = get_channel_layer()

        print(f"[WEB-SOCKET] Отправка состояния чтения карты")
        async_to_sync(channel_layer.group_send)(
            'order_status_updates',
            {
                'type': 'card_reader',
                'code': code
            }
        )

    @staticmethod
    def send_qr_opti(order, qr: str):
        """Отправка обновления статуса заказа через WebSocket"""
        channel_layer = get_channel_layer()

        print(f"[WEB-SOCKET] Отправка qr OPTI для заказа: {order.transaction_id}")
        async_to_sync(channel_layer.group_send)(
            'order_status_updates',
            {
                'type': 'order_qr_opti',
                'order_id': str(order.id),
                'transaction_id': order.transaction_id,
                'qr': qr
            }
        )
