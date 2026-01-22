import uuid
from django.db import models
from django.core.exceptions import ValidationError
from orders.models.program import Program
from orders.start_carwash import start_car_wash
from orders.websocket_service import OrderWebSocketService


class WashOrder(models.Model):
    """
    Заказ на мойку — доменная модель.
    Управляет своим состоянием через бизнес-методы.
    """
    MAX_QUEUE_SIZE = 5

    class Status(models.TextChoices):
        CREATED = 'created', "Создан"
        WAITING_PAYMENT = 'waiting_payment', "Ожидание оплаты"
        PAYED = 'payed', "Оплачен"
        FAILED = 'failed', "Ошибка оплаты"
        CANCELED = 'canceled', "Отменён"
        COMPLETED = 'completed', "Завершён"
        PROCESSING = 'processing', "В процессе"
        MOBILE_QR_REQUEST = 'mobile_qr_request', "Запрос QR мобильного приложения"

    class PaymentType(models.TextChoices):
        BANK_CARD = 'bank_card', "Банковская карта"
        CASH = 'cash', "Наличные"
        MOBILE_APP = 'mobile_app', "Мобильное приложение"
        LOYALTY_CARD = 'loyalty_card', "Карта лояльности"
        OPTI = 'opti', "OPTI"

    program = models.ForeignKey(Program, on_delete=models.CASCADE)

    program_price = models.DecimalField(max_digits=8, decimal_places=2)
    amount_sum = models.DecimalField(max_digits=8, decimal_places=2, default=0)

    transaction_id = models.CharField(max_length=100, unique=True)
    date = models.DateTimeField(auto_now_add=True)

    status = models.CharField(
        max_length=50,
        choices=Status.choices,
        default=Status.CREATED
    )

    ucn = models.CharField(max_length=50, null=True, blank=True)
    payment_type = models.CharField(max_length=20, choices=PaymentType.choices, null=True, blank=True)

    queue_position = models.PositiveIntegerField(null=True, blank=True)
    queue_number = models.CharField(max_length=20, null=True, blank=True)

    qr_code = models.TextField(null=True, blank=True)
    gvl_source = models.IntegerField(null=True, blank=True)

    is_mobile_payment = models.BooleanField(default=False)

    # -------------------- BUSINESS LOGIC --------------------

    @classmethod
    def create_order(cls, program: Program, payment_type=None, ucn=None):
        return cls.objects.create(
            program=program,
            program_price=program.price,
            transaction_id=str(uuid.uuid4()),
            status=cls.Status.CREATED,
            ucn=ucn or None,
            payment_type=payment_type or None,
            queue_number=None,
            queue_position=None,
        )

    @classmethod
    def is_car_wash_busy(cls) -> bool:
        """
        Проверяет, занята ли мойка (есть заказ со статусом PROCESSING).
        """
        return cls.objects.filter(status=cls.Status.PROCESSING).exists()

    @classmethod
    def reset_queue_if_needed(cls):
        """
        Сбрасывает очередь, если все заказы завершены.
        """
        active_statuses = [
            cls.Status.CREATED,
            cls.Status.WAITING_PAYMENT,
            cls.Status.PAYED,
            cls.Status.PROCESSING,
        ]
        if not cls.objects.filter(status__in=active_statuses).exists():
            cls.objects.update(queue_number=None, queue_position=None)
            print("[LOG] Очередь сброшена — мойка и очередь пусты.")

    @classmethod
    def get_next_queue_number(cls) -> str:
        """
        Возвращает следующий уникальный номер очереди в формате A-<номер>.
        """
        existing = cls.objects.exclude(queue_number__isnull=True).values_list('queue_number', flat=True)
        max_num = 0
        for q in existing:
            try:
                num = int(q.split("-")[1])
                max_num = max(max_num, num)
            except (IndexError, ValueError):
                continue
        return f"A-{max_num + 1}"

    def assign_queue_if_possible(self, terminal) -> None:
        """
        Назначает номер и позицию в очереди, если очередь доступна.
        terminal: экземпляр TerminalStatus
        """
        if not terminal.has_queue_availability():
            return

        if not WashOrder.is_car_wash_busy():
            self.queue_number = None
            self.queue_position = 0
            self.save(update_fields=["queue_number", "queue_position"])
            print(f"[LOG] Заказ {self.transaction_id} сразу запускается (мойка свободна)")
            return

        queue = WashOrder.objects.filter(
            queue_number__isnull=False,
            status__in=[
                WashOrder.Status.CREATED,
                WashOrder.Status.WAITING_PAYMENT,
                WashOrder.Status.PAYED,
            ]
        ).order_by("id")

        if queue.count() >= self.MAX_QUEUE_SIZE:
            raise ValueError("Очередь переполнена")

        self.queue_number = self.get_next_queue_number()
        self.queue_position = queue.count() + 1
        self.save(update_fields=["queue_number", "queue_position"])
        print(f"[LOG] Заказ {self.transaction_id} поставлен в очередь: "
              f"номер={self.queue_number}, позиция={self.queue_position}")

    @classmethod
    def shift_queue_positions_after_start(cls):
        """
        После запуска мойки сдвигает позиции заказов в очереди.
        1 → 0, 2 → 1 и т.д.
        """
        queue = cls.objects.filter(queue_position__isnull=False).order_by("queue_position")

        for order in queue:
            if order.queue_position == 1:
                order.queue_position = 0
            elif order.queue_position > 1:
                order.queue_position -= 1

            order.save(update_fields=["queue_position"])

    @classmethod
    def try_run_next_car_wash(cls, terminal):
        """
        Если мойка свободна и есть заказ с позицией 0 и статусом PAYED — запускает мойку.
        """
        if cls.is_car_wash_busy():
            return

        if not terminal.has_queue_availability():
            return

        cls.shift_queue_positions_after_start()

        next_order = cls.objects.filter(
            status=cls.Status.PAYED,
            queue_position=0
        ).order_by("id").first()

        if next_order:
            print(f"[LOG] Заказ {next_order.transaction_id} запускается с позиции 0.")

            start_car_wash(next_order)

    def ensure_not_canceled(self):
        self.refresh_from_db()
        if self.status == self.Status.CANCELED:
            raise OrderCanceled("Заказ был отменен")

    @classmethod
    def get_next_payed_from_queue(cls):
        cls.shift_queue_positions_after_start()
        return cls.objects.filter(
            status=cls.Status.PAYED,
            queue_position=0
        ).order_by("id").first()

    @classmethod
    def can_create_new_order(cls, terminal) -> bool:
        if not cls.has_active_or_processing_orders():
            return True

        return terminal.has_queue_availability()

    @classmethod
    def has_active_or_processing_orders(cls) -> bool:
        return cls.objects.filter(
            status__in=[cls.Status.PAYED, cls.Status.PROCESSING]
        ).exists()

    def can_start(self):
        return self.status == self.Status.PAYED

    def is_waiting_in_queue(self):
        return self.queue_position is not None and self.queue_position > 0

    def _set_status(self, status):
        if status not in self.Status.values:
            raise ValidationError(f"Недопустимый статус: {status}")
        self.status = status
        self.save(update_fields=["status"])
        print(f"[LOG] Статус заказа {self.transaction_id} обновлён: {status}")

        OrderWebSocketService.send_order_status_update(self)

    def mark_created(self):
        self._set_status(self.Status.CREATED)

    def mark_waiting_payment(self):
        self._set_status(self.Status.WAITING_PAYMENT)

    def mark_payed(self):
        self._set_status(self.Status.PAYED)

    def mark_failed(self):
        self._set_status(self.Status.FAILED)

    def mark_canceled(self):
        self._set_status(self.Status.CANCELED)

    def mark_completed(self):
        self._set_status(self.Status.COMPLETED)

    def mark_processing(self):
        self._set_status(self.Status.PROCESSING)

    def mark_mobile_qr_request(self):
        self._set_status(self.Status.MOBILE_QR_REQUEST)

    # -------------------- REPRESENTATION --------------------

    def __str__(self):
        payment_type_str = " (Моб.)" if self.is_mobile_payment else ""
        if self.status == self.Status.MOBILE_QR_REQUEST:
            payment_type_str = " (Старое Моб. приложение)"
        return f"Заказ {self.transaction_id}{payment_type_str} - {self.program.name}"

    class Meta:
        verbose_name = "Таблица заказов"
        verbose_name_plural = "Таблица заказов"


class OrderCanceled(Exception):
    """Заказ был отменён во время обработки."""
    pass


class PaymentFailed(Exception):
    def __init__(self, message, ws_code):
        super().__init__(message)
        self.ws_code = ws_code

