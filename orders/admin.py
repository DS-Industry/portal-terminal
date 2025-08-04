from django.contrib import admin
from .models import (
    Program,
    WashOrder,
    TerminalStatus,
    WashSettings,
    ReceiptServerConfig
    )


# Ограничение на создание только одной записи
class SingletonAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return self.model.objects.count() == 0
    

@admin.register(Program)
class ProgramAdmin(admin.ModelAdmin):
    """Настройка отображения таблицы программ мойки в админке.
    Показываем ID, название, цену, описание, время выполнения и новое поле id_service.
    """
    list_display = ('id', 'name', 'price', 'description', 'duration', 'id_service')
    ordering = ('id',)
    fields = ('name', 'price', 'description', 'duration', 'id_service')


@admin.register(WashOrder)
class WashOrderAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'program',
        'program_price',
        'date',
        'status',
        'payment_type',
        'queue_number',
        'queue_position',
        'transaction_id',
        'ucn',
    )
    ordering = ('-id',)
    list_filter = ('status', 'program', 'payment_type')
    search_fields = ('transaction_id', 'queue_number', 'ucn')


@admin.register(TerminalStatus)
class TerminalStatusAdmin(SingletonAdmin):
    """Настройка отображения состояния терминалов в админке.
    Показываем ID, identifier, имя, номер бокса, car_wash_identifier и все технические поля.
    """
    list_display = (
        'id', 'identifier', 'car_wash_identifier','name', 'bay_number',
        'gvl_cardnum', 'gvl_cardsum', 'gvl_sum',
        'gvl_err', 'gvl_time', 'gvl_source',
    )
    fields = (
        'identifier', 'name', 'bay_number', 'car_wash_identifier',
        'gvl_cardnum', 'gvl_cardsum', 'gvl_sum',
        'gvl_err', 'gvl_time', 'gvl_source',
    )


@admin.register(WashSettings)
class WashSettingsAdmin(SingletonAdmin):
    list_display = ('delay_between_washes',)


@admin.register(ReceiptServerConfig)
class ReceiptServerConfigAdmin(SingletonAdmin):
    list_display = ('ip_address',)
