from rest_framework import serializers
from .models import Order, Terminal, Robot, Program


class ProgramSerializer(serializers.ModelSerializer):
    """
    Сериализатор для модели Program.
    """
    class Meta:
        model = Program
        fields = '__all__'


class TerminalSerializer(serializers.ModelSerializer):
    """
    Сериализатор для модели Terminal.
    """
    class Meta:
        model = Terminal
        fields = '__all__'


class RobotSerializer(serializers.ModelSerializer):
    """
    Сериализатор для модели Robot.
    """
    class Meta:
        model = Robot
        fields = '__all__'


class OrderSerializer(serializers.ModelSerializer):
    """
    Сериализатор для модели Order.
    """
    class Meta:
        model = Order
        fields = '__all__'
