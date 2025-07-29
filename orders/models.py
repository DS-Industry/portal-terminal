import uuid
from django.core.exceptions import ValidationError
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
    
    queue_position = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Порядковый номер в очереди"
    )
    
    queue_number = models.CharField(
        null=True,
        blank=True,
        help_text="Статичный номер в очереди (например, A-1)"
    )
 
    def __str__(self):
        return f"Order {self.transaction_id} [{self.program.name}] - {self.status}"


class TerminalStatus(models.Model):
    """
    Модель TerminalStatus описывает параметры состояния терминала в момент времени.

    Поля:
        - identifier (int): Идентификатор записи (например, счётчик или внешний ID)
        - name (str): Название терминала
        - bay_number (int): Номер бокса
        - gvl_cardnum (int): Количество карт
        - gvl_cardsum (int): Сумма по картам
        - gvl_sum (int): Общая сумма
        - gvl_err (int): Количество ошибок
        - gvl_time (int): Время работы
        - gvl_source (int): Код источника
    """
    identifier = models.IntegerField()
    name = models.CharField(max_length=255)
    bay_number = models.IntegerField()
    gvl_cardnum = models.IntegerField()
    gvl_cardsum = models.IntegerField()
    gvl_sum = models.IntegerField()
    gvl_err = models.IntegerField()
    gvl_time = models.IntegerField()
    gvl_source = models.IntegerField()

    def __str__(self):
        return f"{self.name} (ID: {self.identifier})"

    class Meta:
        verbose_name = "Terminal status"
        verbose_name_plural = "Terminal statuses"


class WashSettings(models.Model):
    """
    Глобальные настройки мойки.
    """
    delay_between_washes = models.PositiveIntegerField(
        default=5, 
        help_text="Задержка перед запуском следующей мойки (в секундах)"
        )

    def clean(self):
        if WashSettings.objects.exists() and not self.pk:
            raise ValidationError("Разрешён только один экземпляр WashSettings.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return "Глобальные настройки мойки"

    class Meta:
        verbose_name = "Настройки мойки"
        verbose_name_plural = "Настройки мойки"
