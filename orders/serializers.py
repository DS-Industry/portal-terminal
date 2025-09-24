from rest_framework import serializers

from .models import Program, WashOrder


class ProgramSerializer(serializers.ModelSerializer):
    """
    Сериализатор для модели Program.
    """

    class Meta:
        model = Program
        fields = ['id', 'name', 'price', 'lty_price', 'description', 'duration', 'functions', 'promo_value']


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
        - "program_id": 1,
        - payment_type (str): Тип оплаты
    """
    program_id = serializers.IntegerField()
    payment_type = serializers.ChoiceField(choices=[
        ('cash', 'cash'),
        ('bank_card', 'bank_card'),
        ('mobile_app', 'mobile_app'),
        ('loyalty_card', 'loyalty_card'),
    ])
    ucn = serializers.CharField(required=False, allow_blank=True)


class WashOrderDetailSerializer(serializers.ModelSerializer):
    program_name = serializers.CharField(source='program.name', read_only=True)

    class Meta:
        model = WashOrder
        fields = [
            'id',
            'transaction_id',
            'payment_type',
            'program_name',
            'program_price',
            'amount_sum',
            'ucn',
            'queue_position',
            'queue_number',
            'status',
            'qr_code'
        ]
