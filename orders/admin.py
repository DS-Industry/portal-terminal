from django.contrib import admin
from django.utils.dateformat import format as date_format
from django.utils import timezone

from .models import (
    Program,
    WashOrder,
    TerminalStatus,
    WashSettings,
    ReceiptServerConfig,
    VendotekServerConfig,
    ManageServerConfig
)


# Ограничение на создание только одной записи
class SingletonAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return self.model.objects.count() == 0


@admin.register(Program)
class ProgramAdmin(admin.ModelAdmin):
    """Настройка отображения таблицы программ мойки в админке.
    Показываем ID, название, цену, описание, время выполнения, id_service и функции.
    """
    list_display = ('id', 'name', 'price', 'lty_price', 'description', 'promo_value', 'duration', 'id_service', 'functions')
    ordering = ('id',)
    fields = ('name', 'price', 'lty_price', 'description', 'promo_value', 'duration', 'id_service', 'functions')


@admin.register(WashOrder)
class WashOrderAdmin(admin.ModelAdmin):
    """Настройка отображения таблицы заказов в админке."""

    def formatted_date(self, obj):
        """Форматирует дату в 'DD.MM.YYYY - HH:MM:SS'"""
        if obj.date:
            local_date = timezone.localtime(obj.date) if timezone.is_aware(obj.date) else obj.date
            return date_format(local_date, 'd.m.Y - H:i:s')
        return "-"

    formatted_date.short_description = 'Дата и время создания'
    formatted_date.admin_order_field = 'date'

    list_display = (
        'id', 'program', 'program_price', 'amount_sum', 'formatted_date', 'status',
        'payment_type', 'queue_number', 'queue_position',
        'transaction_id', 'ucn', 'qr_code',
    )
    ordering = ('-id',)
    list_filter = ('status', 'program', 'payment_type', 'is_mobile_payment')
    search_fields = ('transaction_id', 'queue_number', 'ucn')

@admin.register(TerminalStatus)
class TerminalStatusAdmin(SingletonAdmin):
    """Настройка отображения состояния терминалов в админке.
    Показываем ID, identifier, имя, номер бокса, car_wash_identifier и все технические поля.
    """
    list_display = (
        'id', 'identifier', 'car_wash_identifier', 'name', 'loyalty_status', 'bay_number',
        'gvl_cardnum', 'gvl_cardsum', 'gvl_sum',
        'gvl_err', 'gvl_time', 'gvl_source',
        'mobile_app_qr_code',
    )
    fields = (
        'identifier', 'name', 'loyalty_status', 'bay_number', 'car_wash_identifier',
        'gvl_cardnum', 'gvl_cardsum', 'gvl_sum',
        'gvl_err', 'gvl_time', 'gvl_source',
        'mobile_app_qr_code',
    )
    list_editable = ('identifier', 'car_wash_identifier', 'name', 'loyalty_status', 'bay_number', 'mobile_app_qr_code')


@admin.register(WashSettings)
class WashSettingsAdmin(SingletonAdmin):
    list_display = ('delay_between_washes',)


@admin.register(ReceiptServerConfig)
class ReceiptServerConfigAdmin(SingletonAdmin):
    list_display = ('ip_address',)


@admin.register(VendotekServerConfig)
class VendotekServerConfigAdmin(SingletonAdmin):
    list_display = ('ip_address', 'port',)


@admin.register(ManageServerConfig)
class ManageServerConfigAdmin(admin.ModelAdmin):
    list_display = ('id', 'ip_address', 'port', 'type',)
    fields = ('ip_address', 'port', 'type',)
