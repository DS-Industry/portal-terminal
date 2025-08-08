from django.db import models
from django.core.exceptions import ValidationError


class Program(models.Model):
    """Модель Program описывает программу мойки.
    Поля:
    - name: название программы
    - price: цена
    - description: описание
    - duration: длительность (в минутах)
    - id_service: идентификатор программы в DScloud
    """
    name = models.CharField(
        max_length=100,
        help_text="Название программы",
        )
    
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Цена программы",
        )
    
    description = models.TextField(
        blank=True, 
        null=True,
        help_text="Описание программы",
        )
    
    duration = models.PositiveIntegerField(
        default=0,
        help_text="Продолжительность мойки (мин)",
        )
    
    id_service = models.PositiveIntegerField(
        default=0,
        help_text="Идентификатор программы DScloud",
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
        MOBILE_QR_REQUEST = 'mobile_qr_request'

    class PaymentType(models.TextChoices):
        BANK_CARD = 'bank_card'
        CASH = 'cash'
        MOBILE_APP = 'mobile_app'
        LOYALTY_CARD = 'loyalty_card'

    program = models.ForeignKey(
        Program,
        on_delete=models.CASCADE,
        help_text="Название программы мойки"
        )
    
    program_price = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        help_text="Цена программы мойки"
        )
    
    transaction_id = models.CharField(
        max_length=100,
        unique=True,
        help_text="ID транзакции",
        )
    
    date = models.DateTimeField(
        auto_now_add=True,
        help_text="Дата и время создания",
        )
    
    status = models.CharField(
        max_length=50,
        choices=Status.choices, default=Status.CREATED,
        help_text="Статус заказа"
        )
    
    ucn = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        help_text="Номер карты лояльности",
        )
    
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
        help_text="Позиция в очереди (Первый, второй, и т.д.)",
        )
    
    queue_number = models.CharField(
        null=True,
        blank=True,
        help_text="Статичный номер в очереди (например, A-1)"
        )
    
    qr_code = models.TextField(
        null=True,
        blank=True,
        )
    
    gvl_source = models.IntegerField(
        null=True,
        blank=True,
        )
    
    is_mobile_payment = models.BooleanField(
        default=False,
        help_text="Оплата через мобильное приложение да/нет",
        )
    
    def __str__(self):
        payment_type_str = " (Моб.)" if self.is_mobile_payment else ""
        if self.status == self.Status.MOBILE_QR_REQUEST:
            payment_type_str = " (Старое Моб. приложение)"
        return f"Заказ {self.transaction_id}{payment_type_str} - {self.program.name}"
    
    class Meta:
        verbose_name = "Таблица заказов"
        verbose_name_plural = "Таблица заказов"



class TerminalStatus(models.Model):
    """
    Модель TerminalStatus описывает параметры состояния терминала в момент времени.
    """
    identifier = models.PositiveIntegerField(
        default=0,
        help_text="ID робота в системе DScloud",
        )
        
    car_wash_identifier = models.PositiveIntegerField(
        default=0,
        help_text="ID мойки в системе DScloud",
        )
    
    name = models.CharField(
        max_length=100,
        help_text="Название робота",
        )
    
    mobile_app_qr_code = models.TextField(
        blank=True, 
        help_text="Статический QR-код для перехода в старое мобильное приложение",
    )
    
    bay_number = models.PositiveIntegerField(verbose_name="Номер поста",)
    
    gvl_cardnum = models.IntegerField(default=0,)
    
    gvl_cardsum = models.IntegerField(default=0,)
    
    gvl_sum = models.IntegerField(default=0,)
    
    gvl_err = models.IntegerField(default=0,)
    
    gvl_time = models.IntegerField(default=0,)
    
    gvl_source = models.IntegerField(default=0,)

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
        help_text="Задержка перед запуском следующей мойки (в секундах)",
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

    ip_address = models.CharField(
        max_length=100,
        help_text="IP:PORT кассы, например 192.168.0.10:5000"
        )

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