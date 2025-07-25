# orders/views.py
from rest_framework import viewsets
from rest_framework import status as drf_status
from rest_framework.views import APIView
from rest_framework.response import Response


from django.shortcuts import get_object_or_404
from django.utils import timezone

from .models import Program, WashOrder
from .serializers import (
    ProgramSerializer,
    WashOrderCreateSerializer,
    WashOrderPaymentSerializer
)

import uuid
import time


class ProgramViewSet(viewsets.ModelViewSet):
    """
    ViewSet для управления программами мойки.
    """
    queryset = Program.objects.all()
    serializer_class = ProgramSerializer


class ProgramListView(APIView):
    """
    Эндпоинт для получения списка программ мойки.

    URL: /api/wash-programs/
    Метод: GET
    """

    def get(self, request):
        programs = Program.objects.all().order_by('id')
        serializer = ProgramSerializer(programs, many=True)
        return Response(serializer.data)


class CreateWashOrderView(APIView):
    """
    Эндпоинт создания заказа на мойку.

    Принимает JSON:
        {
            "program_id": 1,
            "ucn": "123456" (необязательно)
        }

    Возвращает:
        {
            "id": 1,
            "transaction_id": "...",
            "status": "created",
            "program_name": "...",
            "program_price": 100.0,
            "date": "25.07.2025 - 14:45:45"
        }
    """

    def post(self, request):
        serializer = WashOrderCreateSerializer(data=request.data)
        if serializer.is_valid():
            program_id = serializer.validated_data['program_id']
            ucn = serializer.validated_data.get('ucn', None)

            try:
                program = Program.objects.get(pk=program_id)
            except Program.DoesNotExist:
                return Response({'error': 'Программа не найдена'}, status=404)

            transaction_id = str(uuid.uuid4())
            current_date = timezone.now().strftime('%d.%m.%Y - %H:%M:%S')

            order = WashOrder.objects.create(
                program=program,
                program_price=program.price,
                transaction_id=transaction_id,
                date=current_date,
                status=WashOrder.Status.CREATED,
                ucn=ucn
            )

            print(f"[LOG] Новый заказ создан: ID={order.transaction_id}, Программа={program.name}, Цена={order.program_price}₽")

            return Response({
                "id": order.id,
                "transaction_id": transaction_id,
                "status": order.status,
                "program_name": program.name,
                "program_price": float(program.price),
                "date": current_date
            }, status=201)

        return Response(serializer.errors, status=400)


class WashOrderPaymentView(APIView):
    """
    Эндпоинт для обработки типа оплаты и запуска мойки.

    Принимает JSON:
        {
            "transaction_id": "uuid",
            "payment_type": "cash"
        }
    """

    def post(self, request):
        serializer = WashOrderPaymentSerializer(data=request.data)
        if serializer.is_valid():
            transaction_id = serializer.validated_data['transaction_id']
            payment_type = serializer.validated_data['payment_type']

            order = get_object_or_404(WashOrder, transaction_id=transaction_id)

            # Проверки статуса
            if order.status == WashOrder.Status.COMPLETED:
                return Response({"error": "Заказ уже завершён. Повторная оплата невозможна."},
                                status=drf_status.HTTP_400_BAD_REQUEST)

            if order.status == WashOrder.Status.PAYED:
                return Response({"error": "Заказ уже оплачен."},
                                status=drf_status.HTTP_400_BAD_REQUEST)

            if order.status == WashOrder.Status.PROCESSING:
                return Response({"error": "Мойка уже запущена. Повторная оплата невозможна."},
                                status=drf_status.HTTP_400_BAD_REQUEST)

            if order.status == WashOrder.Status.WAITING_PAYMENT:
                return Response({"error": "Заказ уже в ожидании оплаты."},
                                status=drf_status.HTTP_400_BAD_REQUEST)

            # Обновляем статус и тип оплаты
            order.payment_type = payment_type
            order.status = WashOrder.Status.WAITING_PAYMENT
            order.save()
            print(f"[LOG] Статус заказа {order.transaction_id} обновлён: waiting_payment")

            # Заглушка оплаты
            if payment_type == 'cash':
                cash_payment()
            elif payment_type == 'bank_card':
                bank_card_payment()
            elif payment_type == 'mobile_app':
                mobile_app_payment()
            elif payment_type == 'loyalty_card':
                loyalty_card_payment()

            # Статус: Оплачено
            order.status = WashOrder.Status.PAYED
            order.save()
            print(f"[LOG] Статус заказа {order.transaction_id} обновлён: payed")

            # Запуск мойки (заглушка)
            start_car_wash(order)

            return Response({'message': 'Оплата прошла успешно, мойка запущена'}, status=200)

        return Response(serializer.errors, status=drf_status.HTTP_400_BAD_REQUEST)


def start_car_wash(order):
    """
    Заглушка для запуска мойки после оплаты.

    Меняет статус заказа:
    - processing
    - completed (через 10 секунд)
    """
    print(f"[LOG] Запуск мойки по программе: {order.program.name}")
    order.status = WashOrder.Status.PROCESSING
    order.save()

    time.sleep(10)

    order.status = WashOrder.Status.COMPLETED
    order.save()
    print(f"[LOG] Мойка завершена. Статус заказа {order.transaction_id} обновлён: completed")

# -------
# ОПЛАТА: Заглушки под каждую функцию оплаты
# -------

def bank_card_payment():
    """
    Заглушка оплаты банковской картой.
    """
    print("[LOG] Выбран тип оплаты: bank_card")
    time.sleep(5)
    print("[LOG] Оплата банковской картой прошла успешно.")


def cash_payment():
    """
    Заглушка оплаты наличными.
    """
    print("[LOG] Выбран тип оплаты: cash")
    time.sleep(5)
    print("[LOG] Оплата наличными прошла успешно.")


def mobile_app_payment():
    """
    Заглушка оплаты через мобильное приложение.
    """
    print("[LOG] Выбран тип оплаты: mobile_app")
    time.sleep(5)
    print("[LOG] Оплата через мобильное приложение прошла успешно.")


def loyalty_card_payment():
    """
    Заглушка оплаты картой лояльности.
    """
    print("[LOG] Выбран тип оплаты: loyalty_card")
    time.sleep(5)
    print("[LOG] Оплата по карте лояльности прошла успешно.")
