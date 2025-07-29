from django.contrib import admin
from .models import Program, WashOrder, TerminalStatus, WashSettings


@admin.register(Program)
class ProgramAdmin(admin.ModelAdmin):
    """
    Настройка отображения таблицы программ мойки в админке.
    Показываем ID, название, цену, описание, время выполнения.
    """
    list_display = ('name', 'price', 'description', 'duration', 'id')
    ordering = ('id',)


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
class TerminalStatusAdmin(admin.ModelAdmin):
    """
    Настройка отображения состояния терминалов в админке.
    Показываем ID и все технические поля.
    """
    list_display = (
        'id', 'identifier', 'name', 'bay_number',
        'gvl_cardnum', 'gvl_cardsum', 'gvl_sum',
        'gvl_err', 'gvl_time', 'gvl_source'
    )
    ordering = ('identifier',)
    search_fields = ('name',)

@admin.register(WashSettings)
class WashSettingsAdmin(admin.ModelAdmin):
    list_display = ('delay_between_washes',)
