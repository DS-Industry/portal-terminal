import json
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.utils import timezone


class OrderWebSocketService:
    @staticmethod
    def send_order_status_update(order):
        """Отправка обновления статуса заказа через WebSocket"""
        channel_layer = get_channel_layer()

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
    def send_order_created(order):
        """Отправка уведомления о создании нового заказа"""
        channel_layer = get_channel_layer()

        async_to_sync(channel_layer.group_send)(
            'order_status_updates',
            {
                'type': 'order_created',
                'order_id': str(order.id),
                'status': order.status,
                'transaction_id': order.transaction_id,
                'program_name': order.program.name,
                'program_price': str(order.program_price),
                'timestamp': timezone.now().isoformat()
            }
        )