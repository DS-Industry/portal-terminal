from django.contrib import admin
from .models import Program, WashOrder, TerminalStatus


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
    """
    Настройка отображения заказов в админке.
    Показываем ID, транзакцию, дату, статус и цену.
    """
    list_display = ('program', 'program_price', 'date', 'status', 'ucn', 'transaction_id', 'id')
    ordering = ('-id',)
    list_filter = ('status', 'program')
    search_fields = ('transaction_id', 'ucn')


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
