from django.core.exceptions import ValidationError
from django.db import models


class WashSettings(models.Model):

    delay_between_washes = models.PositiveIntegerField(
        default=5,
        help_text="Задержка перед запуском следующей мойки (в секундах)",
    )

    # ---------- Singleton ----------

    def clean(self):
        if WashSettings.objects.exists() and not self.pk:
            raise ValidationError("Разрешён только один экземпляр WashSettings.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    @classmethod
    def get(cls):
        """
        Возвращает единственную запись настроек или None.
        """
        return cls.objects.first()

    @classmethod
    def get_or_create_default(cls):
        """
        Возвращает настройки, создавая их при отсутствии.
        """
        obj = cls.objects.first()
        if not obj:
            obj = cls.objects.create()
        return obj

    # ---------- Бизнес-методы ----------

    def get_delay(self) -> int:
        return int(self.delay_between_washes)

    def set_delay(self, seconds: int):
        self.delay_between_washes = max(0, int(seconds))
        self.save(update_fields=["delay_between_washes"])

    # ---------- Представление ----------

    def __str__(self):
        return "Глобальные настройки мойки"

    class Meta:
        verbose_name = "Настройки таймера между мойками"
        verbose_name_plural = "Настройки таймера между мойками"
