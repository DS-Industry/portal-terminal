from rest_framework import viewsets
from .models import Order, Terminal, Robot, Program
from .serializers import (
    OrderSerializer,
    TerminalSerializer,
    RobotSerializer,
    ProgramSerializer,
)


class OrderViewSet(viewsets.ModelViewSet):
    """
    ViewSet для управления заказами (Order).
    
    Поддерживает все CRUD-операции:
    - получение списка заказов
    - создание нового заказа
    - получение одного заказа по ID
    - обновление заказа
    - удаление заказа
    """
    queryset = Order.objects.all().order_by('-created_at')
    serializer_class = OrderSerializer


class TerminalViewSet(viewsets.ModelViewSet):
    """
    ViewSet для управления терминалами (Terminal).
    
    Позволяет:
    - добавлять терминалы
    - редактировать/удалять
    - получать список и детали терминалов
    """
    queryset = Terminal.objects.all()
    serializer_class = TerminalSerializer


class RobotViewSet(viewsets.ModelViewSet):
    """
    ViewSet для управления роботами (Robot).
    
    Роботы привязаны к терминалам.
    CRUD-интерфейс: создание, просмотр, обновление, удаление.
    """
    queryset = Robot.objects.all()
    serializer_class = RobotSerializer


class ProgramViewSet(viewsets.ModelViewSet):
    """
    ViewSet для программ мойки (Program).
    
    Программы включают название, длительность и стоимость.
    Доступны все стандартные методы: list, create, retrieve, update, destroy.
    """
    queryset = Program.objects.all()
    serializer_class = ProgramSerializer
