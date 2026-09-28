from django.db import models, transaction
from django.core.exceptions import ValidationError, ObjectDoesNotExist


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
    loyalty_status = models.BooleanField(
        default=False,
        help_text="Наличие системы лояльности",
    )
    led_board = models.BooleanField(
        default=False,
        help_text="Наличие LED табло",
    )
    queue_availability = models.BooleanField(
        default=False,
        help_text="Наличие очереди",
    )

    mobile_app_qr_code = models.TextField(
        blank=True,
        help_text="Статический QR-код для перехода в старое мобильное приложение",
    )
    bay_number = models.PositiveIntegerField(verbose_name="Номер поста", )

    gvl_cardnum = models.IntegerField(default=0, )
    gvl_cardsum = models.IntegerField(default=0, )
    gvl_sum = models.IntegerField(default=0, )
    gvl_err = models.IntegerField(default=0, )
    gvl_time = models.IntegerField(default=0, )
    gvl_source = models.IntegerField(default=0, )

    # ---------------- БИЗНЕС ЛОГИКА ----------------

    @classmethod
    def get_terminal(cls):
        terminal = cls.objects.first()
        if not terminal:
            raise ObjectDoesNotExist("TerminalStatus не найден")
        return terminal

    # ---- Boolean проверки ----

    def has_loyalty(self) -> bool:
        return bool(self.loyalty_status)

    def has_led_board(self) -> bool:
        return bool(self.led_board)

    def has_queue_availability(self) -> bool:
        return bool(self.queue_availability)

    def set_gvl_sum(self, value: int):
        with transaction.atomic():
            self.gvl_sum = int(value)
            self.save(update_fields=["gvl_sum"])
            self.refresh_from_db()

    # ---------------- СИСТЕМНАЯ ЛОГИКА ----------------

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
