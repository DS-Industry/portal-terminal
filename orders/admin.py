from django.contrib import admin
from .models import Program, WashOrder


@admin.register(Program)
class ProgramAdmin(admin.ModelAdmin):
    """
    Настройка отображения таблицы программ мойки в админке.
    Показываем ID, название и цену.
    """
    list_display = ('name', 'price', 'id')
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
