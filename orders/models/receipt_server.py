from django.core.exceptions import ValidationError
from django.db import models


class ReceiptServerConfig(models.Model):
    """
    Настройки сервера фискального регистратора (Flask).
    """

    ip_address = models.CharField(
        max_length=100,
        help_text="IP:PORT кассы, например 192.168.0.10:5000"
    )

    # ---------- Singleton ----------

    def clean(self):
        if ReceiptServerConfig.objects.exists() and not self.pk:
            raise ValidationError("Можно создать только одну запись ReceiptServerConfig.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    @classmethod
    def get(cls):
        """Возвращает конфигурацию или None."""
        return cls.objects.first()

    @classmethod
    def get_or_create_default(cls, ip_address: str = "127.0.0.1:5000"):
        """Возвращает конфигурацию, создавая при отсутствии."""
        obj = cls.objects.first()
        if not obj:
            obj = cls.objects.create(ip_address=ip_address)
        return obj

    # ---------- Бизнес-методы ----------

    def get_address(self) -> str:
        return self.ip_address

    def get_base_url(self) -> str:
        return f"http://{self.ip_address}"

    def set_address(self, ip_address: str):
        self.ip_address = ip_address
        self.save(update_fields=["ip_address"])

    # ---------- Представление ----------

    def __str__(self):
        return f"Receipt Server: {self.ip_address}"

    class Meta:
        verbose_name = "Настройки API печати чеков"
        verbose_name_plural = "Настройки API печати чеков"
