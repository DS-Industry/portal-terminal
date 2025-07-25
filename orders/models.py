import uuid
from django.db import models
from datetime import datetime


class Program(models.Model):
    """
    Модель Program описывает доступные программы мойки.
    """
    name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=8, decimal_places=2)
    description = models.TextField(blank=True, null=True, help_text="Описание программы")
    duration = models.PositiveIntegerField(default=0, help_text="Продолжительность в минутах")

    def __str__(self):
        return f"{self.name} — {self.duration} мин"



class WashOrder(models.Model):
    """
    Модель WashOrder описывает заказ на мойку.

    Поля:
        - program: связь с программой мойки
        - program_price: цена на момент заказа
        - transaction_id: уникальный ID транзакции
        - date: дата и время создания заказа
        - status: текущий статус заказа
        - ucn: номер карты лояльности (опционально)
        - payment_type: тип оплаты (банковская карта, наличные и т.д.)
    """

    class Status(models.TextChoices):
        CREATED = 'created'
        WAITING_PAYMENT = 'waiting_payment'
        PAYED = 'payed'
        FAILED = 'failed'
        COMPLETED = 'completed'
        PROCESSING = 'processing'

    class PaymentType(models.TextChoices):
        BANK_CARD = 'bank-card'
        CASH = 'cash'
        MOBILE_APP = 'mobile-app'
        LOYALTY_CARD = 'loyalty-card'

    program = models.ForeignKey(Program, on_delete=models.CASCADE)
    program_price = models.DecimalField(max_digits=8, decimal_places=2)
    transaction_id = models.CharField(max_length=100, unique=True)
    date = models.CharField(max_length=30)
    status = models.CharField(max_length=50, choices=Status.choices, default=Status.CREATED)
    ucn = models.CharField(max_length=50, null=True, blank=True)
    payment_type = models.CharField(
        max_length=20,
        choices=PaymentType.choices,
        null=True,
        blank=True,
        help_text="Тип оплаты"
    )

    def __str__(self):
        return f"Order {self.transaction_id} [{self.program.name}] - {self.status}"
