import uuid
from django.db import models
from datetime import datetime


class Program(models.Model):
    """
    Модель Program описывает доступные программы мойки.
    Редактируется через Django Admin.
    """
    name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=8, decimal_places=2)

    def __str__(self):
        return f"{self.name} ({self.price}₽)"


class WashOrder(models.Model):
    """
    Модель WashOrder описывает заказ на мойку.

    Поля:
        - program: связь с программой мойки
        - program_price: цена на момент заказа
        - transaction_id: уникальный ID транзакции
        - date: дата и время в формате "дд.мм.гггг - чч:мм:сс"
        - status: статус заказа
        - ucn: необязательный номер карты лояльности
    """

    class Status(models.TextChoices):
        CREATED = 'created'
        PAYMENT_PROCESSING = 'payment_processing'
        WAITING_PAYMENT = 'waiting_payment'
        PAYMENT_AUTHORIZED = 'payment_authorized'
        PAYED = 'payed'
        FAILED = 'failed'
        COMPLETED = 'completed'
        CANCELED = 'canceled'
        REFUNDED = 'refunded'
        FREE_PROCESSING = 'free_processing'

    program = models.ForeignKey(Program, on_delete=models.CASCADE)
    program_price = models.DecimalField(max_digits=8, decimal_places=2)
    transaction_id = models.CharField(max_length=100, unique=True)
    date = models.CharField(max_length=30)
    status = models.CharField(max_length=50, choices=Status.choices, default=Status.CREATED)
    ucn = models.CharField(max_length=50, null=True, blank=True)

    def __str__(self):
        return f"Order {self.transaction_id} [{self.program.name}] - {self.status}"
