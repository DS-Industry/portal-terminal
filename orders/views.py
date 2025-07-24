from rest_framework import viewsets, status
from rest_framework.views import APIView
from rest_framework.response import Response
from .models import Program, WashOrder
from .serializers import ProgramSerializer, WashOrderCreateSerializer
import uuid
from datetime import datetime


class ProgramViewSet(viewsets.ModelViewSet):
    """
    ViewSet для управления программами мойки.
    """
    queryset = Program.objects.all()
    serializer_class = ProgramSerializer


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
        "transaction_id": "...",
        "status": "created",
        "program_name": "...",
        "program_price": 100.0,
        "date": "24.07.2025 - 16:01:20"
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
            current_date = datetime.now().strftime('%d.%m.%Y - %H:%M:%S')

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
                "transaction_id": transaction_id,
                "status": order.status,
                "program_name": program.name,
                "program_price": float(program.price),
                "date": current_date
            }, status=201)

        return Response(serializer.errors, status=400)
