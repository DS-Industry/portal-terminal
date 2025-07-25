from rest_framework import serializers
from .models import Program, WashOrder


class ProgramSerializer(serializers.ModelSerializer):
    """
    Сериализатор для модели Program.
    """
    class Meta:
        model = Program
        fields = ['id', 'name', 'price', 'description', 'duration']


class WashOrderCreateSerializer(serializers.Serializer):
    """
    Сериализатор для создания заказа на мойку.
    Ожидает:
        - program_id (int)
        - ucn (str, необязательное)
    """
    program_id = serializers.IntegerField()
    ucn = serializers.CharField(required=False, allow_blank=True)


class WashOrderPaymentSerializer(serializers.Serializer):
    """
    Сериализатор для обработки типа оплаты.

    Ожидает:
        - transaction_id (str): UUID заказа
        - payment_type (str): Тип оплаты
    """
    transaction_id = serializers.UUIDField()
    payment_type = serializers.ChoiceField(choices=[
        ('cash', 'cash'),
        ('bank_card', 'bank_card'),
        ('mobile_app', 'mobile_app'),
        ('loyalty_card', 'loyalty_card'),
    ])
