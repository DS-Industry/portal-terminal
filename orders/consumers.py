import json
import asyncio
from channels.generic.websocket import AsyncWebsocketConsumer


class OrderStatusConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # Подключаемся к группе обновлений заказов
        self.room_group_name = 'order_status_updates'

        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()
        await self.send(text_data=json.dumps({
            'type': 'connection',
            'message': 'Connected to order status updates'
        }))

    async def disconnect(self, close_code):
        # Отключаемся от группы
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def order_status_update(self, event):
        """Отправка обновления статуса заказа всем подключенным клиентам"""
        await self.send(text_data=json.dumps({
            'type': 'status_update',
            'order_id': event['order_id'],
            'status': event['status'],
            'transaction_id': event['transaction_id'],
            'timestamp': event['timestamp']
        }))

    async def order_error(self, event):
        """Обработка создания нового заказа"""
        await self.send(text_data=json.dumps({
            'type': 'error',
            'code': event['code']
        }))

    async def card_reader(self, event):
        """Обработка создания нового заказа"""
        await self.send(text_data=json.dumps({
            'type': 'card_reader',
            'code': event['code']
        }))