import uuid
from django.core.exceptions import ValidationError
from django.db import models
from datetime import datetime


class Program(models.Model):
    """Модель Program описывает программу мойки.
    Поля:
    - name: название программы
    - price: цена
    - description: описание
    - duration: длительность (в минутах)
    - id_service: идентификатор программы в DScloud
    """
    name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField(blank=True, null=True)
    duration = models.PositiveIntegerField(default=0, help_text="Длительность в минутах")
    id_service = models.PositiveIntegerField(
        default=0,
        help_text="идентификатор программы DScloud"
    )
    def __str__(self):
        return f"{self.name} — {self.duration} мин"

    class Meta:
        verbose_name = "Программа мойки"
        verbose_name_plural = "Программы мойки"


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
        BANK_CARD = 'bank_card'
        CASH = 'cash'
        MOBILE_APP = 'mobile_app'
        LOYALTY_CARD = 'loyalty_card'

    program = models.ForeignKey(Program, on_delete=models.CASCADE)
    program_price = models.DecimalField(max_digits=8, decimal_places=2)
    transaction_id = models.CharField(max_length=100, unique=True)
    date = models.CharField(max_length=30)
    status = models.CharField(max_length=50, choices=Status.choices, default=Status.CREATED)
    ucn = models.CharField(max_length=50, null=True, blank=True, verbose_name="Номер карты лояльности")
    payment_type = models.CharField(
        max_length=20,
        choices=PaymentType.choices,
        null=True,
        blank=True,
    )
    
    queue_position = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Позиция в очереди",
        help_text="Позиция в очереди"
    )
    
    queue_number = models.CharField(
        null=True,
        blank=True,
        verbose_name="номер в очереди (например, A-1)",
        help_text="Статичный номер в очереди (например, A-1)"
    )
    
    qr_code = models.TextField(
    null=True,
    blank=True,
    )
    
    gvl_source = models.IntegerField(null=True, blank=True)
 
    def __str__(self):
        return f"Order {self.transaction_id} [{self.program.name}] - {self.status}"

    class Meta:
        verbose_name = "Таблица заказов"
        verbose_name_plural = "Таблица заказов"



class TerminalStatus(models.Model):
    """
    Модель TerminalStatus описывает параметры состояния терминала в момент времени.
    """
    identifier = models.PositiveIntegerField(default=0)    
    car_wash_identifier = models.PositiveIntegerField(default=0)
    name = models.CharField(max_length=100)
    bay_number = models.PositiveIntegerField()
    gvl_cardnum = models.IntegerField(default=0)
    gvl_cardsum = models.IntegerField(default=0)
    gvl_sum = models.IntegerField(default=0)
    gvl_err = models.IntegerField(default=0)
    gvl_time = models.IntegerField(default=0)
    gvl_source = models.IntegerField(default=0)

    def clean(self):
        if TerminalStatus.objects.exists() and not self.pk:
            raise ValidationError("Можно создать только одну запись TerminalStatus.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} (ID: {self.identifier})"

    class Meta:
        verbose_name = "Terminal Status DScloud"
        verbose_name_plural = "Terminal Statuses DScloud"



class WashSettings(models.Model):
    """
    Глобальные настройки мойки.
    """
    delay_between_washes = models.PositiveIntegerField(
        default=5, 
        verbose_name="Задержка перед запуском следующей мойки (в секундах)",
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
        verbose_name = "Настройки таймера между мойками"
        verbose_name_plural = "Настройки таймера между мойками"


class ReceiptServerConfig(models.Model):
    """
    Настройки сервера фискального регистратора (Flask).
    """

    ip_address = models.CharField(max_length=100, help_text="IP:PORT кассы, например 192.168.0.10:5000")

    def clean(self):
        if ReceiptServerConfig.objects.exists() and not self.pk:
            raise ValidationError("Можно создать только одну запись ReceiptServerConfig.")

    def save(self, *args, **kwargs):
        self.full_clean()  # обязательно вызвать clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Receipt Server: {self.ip_address}"

    class Meta:
        verbose_name = "Настройки API печати чеков"
        verbose_name_plural = "Настройки API печати чеков"