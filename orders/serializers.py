from rest_framework import serializers
from .models import Program


class ProgramSerializer(serializers.ModelSerializer):
    """
    Сериализатор для модели Program.
    """
    class Meta:
        model = Program
        fields = '__all__'


class WashOrderCreateSerializer(serializers.Serializer):
    """
    Сериализатор для создания заказа на мойку.
    Ожидает:
        - program_id (int)
        - ucn (str, необязательное)
    """
    program_id = serializers.IntegerField()
    ucn = serializers.CharField(required=False, allow_blank=True)
