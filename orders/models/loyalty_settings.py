from django.db import models
from django.core.exceptions import ValidationError


class LoyaltySettings(models.Model):
    """
    Настройки лояльности - модель с единственной записью.
    """
    ucn = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text="Номер карты лояльности",
    )

    discount = models.IntegerField(
        default=0,
        help_text="Скидка в процентах",
    )

    cashback = models.IntegerField(
        default=0,
        help_text="Кешбэк в процентах",
    )

    balance = models.IntegerField(
        default=0,
        help_text="Баланс баллов",
    )

    def clean(self):
        # Запрещаем создание более одной записи
        if LoyaltySettings.objects.exists() and not self.pk:
            raise ValidationError("Можно создать только одну запись LoyaltySettings.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Настройки лояльности (Карта: {self.ucn or 'не указана'})"

    class Meta:
        verbose_name = "Настройки лояльности"
        verbose_name_plural = "Настройки лояльности"

    @classmethod
    def get_settings(cls):
        """Получить единственную запись настроек"""
        try:
            return cls.objects.get()
        except cls.DoesNotExist:
            return None

    @classmethod
    def create_or_replace_settings(cls, ucn=None, discount=0, cashback=0, balance=0):
        """Удалить старую запись и создать новую"""
        # Удаляем существующую запись если она есть
        cls.objects.all().delete()

        # Создаем новую запись
        new_settings = cls(
            ucn=ucn,
            discount=discount,
            cashback=cashback,
            balance=balance
        )
        new_settings.save()
        return new_settings

    @classmethod
    def delete_settings(cls):
        """Удалить запись настроек лояльности"""
        cls.objects.all().delete()
