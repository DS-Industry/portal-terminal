from django.core.exceptions import ValidationError
from django.db import models

class VendotekServerConfig(models.Model):
    """
    Настройки сервера Vendotek
    """

    ip_address = models.CharField(
        max_length=100,
        help_text="IP-адрес терминала, например 192.168.53.186"
    )
    port = models.IntegerField(
        default=62801,
        help_text="Порт терминала, например 62801"
    )

    def clean(self):
        if VendotekServerConfig.objects.exists() and not self.pk:
            raise ValidationError("Можно создать только одну запись VendotekServerConfig.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    @classmethod
    def get(cls):
        """
        Возвращает конфигурацию Vendotek или None.
        """
        return cls.objects.first()

    @classmethod
    def get_required(cls):
        """
        Возвращает конфигурацию Vendotek или бросает исключение.
        """
        obj = cls.objects.first()
        if not obj:
            raise ValueError("VendotekServerConfig не настроен")
        return obj

    def get_url(self) -> str:
        return f"http://{self.ip_address}:{self.port}"

    def __str__(self):
        return f"Vendotek: {self.ip_address}:{self.port}"

    class Meta:
        verbose_name = "Настройки API Vendotek"
        verbose_name_plural = "Настройки API Vendotek"
