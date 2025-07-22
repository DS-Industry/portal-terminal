"""Модели приложения orders: описывают терминалы, роботов, программы и заказы."""

import uuid
from django.db import models


class Program(models.Model):
    """
    Модель Program описывает доступные программы мойки.

    Атрибуты:
        name (str): Название программы.
        duration (int): Продолжительность программы в секундах.
        price (Decimal): Стоимость программы.
    """
    name = models.CharField(max_length=100)
    duration = models.PositiveIntegerField(help_text="Длительность в секундах")
    price = models.DecimalField(max_digits=8, decimal_places=2)

    def __str__(self):
        return self.name


class Terminal(models.Model):
    """
    Модель Terminal описывает терминал самообслуживания.

    Атрибуты:
        name (str): Название/номер терминала.
        location (str): Местоположение.
        ip_address (str): IP-адрес терминала.
    """
    name = models.CharField(max_length=100)
    location = models.CharField(max_length=255, blank=True, null=True)
    ip_address = models.GenericIPAddressField()

    def __str__(self):
        return self.name


class Robot(models.Model):
    """
    Модель Robot представляет робота мойки, привязанного к терминалу.

    Атрибуты:
        terminal (Terminal): Терминал, к которому привязан робот.
        status (str): Текущий статус робота (idle, in_progress и т.д.).
    """
    terminal = models.OneToOneField(Terminal, on_delete=models.CASCADE)
    status = models.CharField(max_length=50, default="idle")

    def __str__(self):
        return f"Robot for {self.terminal.name}"


class Order(models.Model):
    """
    Модель Order описывает заказ на мойку автомобиля.

    Атрибуты:
        id (UUID): Уникальный идентификатор заказа.
        car_number (str): Номер автомобиля.
        program (Program): Выбранная программа мойки.
        terminal (Terminal): Терминал, где сделан заказ.
        robot (Robot): Робот, выполняющий заказ (опционально).
        payment_status (str): Статус оплаты.
        execution_status (str): Статус выполнения заказа.
        created_at (datetime): Дата и время создания заказа.
    """

    class PaymentStatus(models.TextChoices):
        CREATED = 'created', 'Создан'
        PENDING = 'payment_pending', 'Ожидание оплаты'
        PAID = 'paid', 'Оплачен'

    class ExecutionStatus(models.TextChoices):
        QUEUE = 'queue', 'В очереди'
        IN_PROGRESS = 'in_progress', 'В процессе'
        COMPLETED = 'completed', 'Завершен'
        CANCELLED = 'cancelled', 'Отменен'
        FAILED = 'failed', 'Ошибка'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    car_number = models.CharField(max_length=20)
    program = models.ForeignKey(Program, on_delete=models.CASCADE)
    terminal = models.ForeignKey(Terminal, on_delete=models.CASCADE)
    robot = models.ForeignKey(Robot, on_delete=models.SET_NULL, null=True, blank=True)
    payment_status = models.CharField(max_length=20, choices=PaymentStatus.choices, default=PaymentStatus.CREATED)
    execution_status = models.CharField(max_length=20, choices=ExecutionStatus.choices, default=ExecutionStatus.QUEUE)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Order {self.id} - {self.car_number}"
