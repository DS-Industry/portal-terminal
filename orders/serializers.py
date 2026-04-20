from rest_framework import serializers

from orders.models.program import Program
from orders.models.wash_order import WashOrder


class ProgramSerializer(serializers.ModelSerializer):
    """
    Сериализатор для модели Program.
    """

    class Meta:
        model = Program
        fields = [
            'id',
            'name',
            'price',
            'lty_price',
            'start_time_lty_price',
            'end_time_lty_price',
            'description',
            'duration',
            'functions',
            'promo_value'
        ]


class WashOrderPaymentSerializer(serializers.Serializer):

    program_id = serializers.IntegerField()
    payment_type = serializers.ChoiceField(choices=WashOrder.PaymentType.choices)
    ucn = serializers.CharField(required=False, allow_blank=True)

    def validate_program_id(self, value):
        try:
            program = Program.objects.get(pk=value)
        except Program.DoesNotExist:
            raise serializers.ValidationError("Программа не найдена")

        if not program.is_available():
            raise serializers.ValidationError("Программа недоступна")

        return program


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
