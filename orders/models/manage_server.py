from django.db import models


class ManageServerConfig(models.Model):
    """
    Настройки сервера для системы мониторинга.
    Может быть несколько серверов.
    """

    ip_address = models.CharField(
        max_length=100,
        help_text="IP-адрес терминала, например 46.19.66.141"
    )
    port = models.IntegerField(
        default=5001,
        help_text="Порт терминала, например 5001"
    )
    type = models.CharField(
        max_length=50,
        default="CW",
        help_text="Тип сервера (например CW, ONVI)"
    )
    loyalty_status = models.BooleanField(
        default=False,
        help_text="Система лояльности для работы с картой",
    )

    # ---- Domain API ----
    @classmethod
    def get_all(cls):
        """
        Возвращает QuerySet со всеми серверами мониторинга.
        """
        return cls.objects.all()

    @classmethod
    def get_loyalty(cls):
        return cls.objects.filter(loyalty_status=True).first()

    def get_url(self) -> str:
        return f"http://{self.ip_address}:{self.port}"

    def __str__(self):
        return f"ManageServer: {self.ip_address}:{self.port} [{self.type}]"

    class Meta:
        verbose_name = "Настройки API системы мониторинга"
        verbose_name_plural = "Настройки API системы мониторинга"
