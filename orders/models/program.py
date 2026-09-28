from django.db import models
from django.core.exceptions import ValidationError
from django.db.models import BooleanField


class Program(models.Model):
    name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    lty_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    start_time_lty_price = models.TextField(blank=True, null=True)
    end_time_lty_price = models.TextField(blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    promo_value = models.TextField(blank=True, null=True)
    duration = models.PositiveIntegerField(default=0)
    id_service = models.PositiveIntegerField(default=0)
    functions = models.TextField(blank=True, null=True)
    plc_start_write_address = models.PositiveIntegerField(default=0)
    is_visibility = models.BooleanField(default=False)

    # ---------- Работа с функциями ----------

    def get_functions_list(self):
        if not self.functions:
            return []
        return [f.strip() for f in self.functions.split(",") if f.strip()]

    def set_functions_list(self, functions_list):
        self.functions = ", ".join(functions_list) if functions_list else ""

    def has_function(self, func_name: str) -> bool:
        return func_name in self.get_functions_list()

    # ---------- Цены ----------

    def has_loyalty_price(self) -> bool:
        return self.lty_price is not None

    # ---------- Доступность ----------

    def is_available(self):
        return self.is_visibility

    @classmethod
    def get_visible_programs(cls):
        return cls.objects.filter(is_visibility=True)

    @classmethod
    def get_program_by_service_id(cls, service_id: int):
        return cls.objects.filter(id_service=service_id).first()

    # ---------- Представление ----------

    def __str__(self):
        return f"{self.name} — {self.duration} мин"

    class Meta:
        verbose_name = "Программа мойки"
        verbose_name_plural = "Программы мойки"
