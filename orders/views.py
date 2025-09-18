import uuid

from django.shortcuts import get_object_or_404
from django.utils import timezone

from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import (
    Program,
    WashOrder,
    )
from .serializers import (
    ProgramSerializer,
    WashOrderCreateSerializer,
    WashOrderPaymentSerializer,
)
from .receipt_qr import send_receipt_request
from .payments import (
    bank_card_payment,
    cash_payment,    
    loyalty_card_payment,
    mobile_app_payment,
)
from .queue_option import (
    assign_queue_number_and_position,
    is_car_wash_busy,
    reset_queue_if_needed,
)


class ProgramViewSet(viewsets.ModelViewSet):
    """
    ViewSet для управления программами мойки.
    """
    queryset = Program.objects.all()
    serializer_class = ProgramSerializer


class ProgramListView(APIView):
    """
    Эндпоинт получения списка программ мойки.
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
            "queue_number": А-3, (Может и None)
            "queue_position": 1
        }
    """
    def post(self, request):
        serializer = WashOrderCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        program_id = serializer.validated_data['program_id']
        ucn = serializer.validated_data.get('ucn')

        try:
            program = Program.objects.get(pk=program_id)
        except Program.DoesNotExist:
            return Response({'error': 'Программа не найдена'}, status=404)

        reset_queue_if_needed()

        queue_number = None
        queue_position = None

        transaction_id = str(uuid.uuid4())

        order = WashOrder.objects.create(
            program=program,
            program_price=program.price,
            transaction_id=transaction_id,
            status=WashOrder.Status.CREATED,
            ucn=ucn,
            queue_number=queue_number,
            queue_position=queue_position
        )

        formatted_date = (
            timezone.localtime(
                order.date
                ).strftime('%d.%m.%Y - %H:%M:%S') if order.date else None
            )
        
        print(f"[LOG] Новый заказ создан: ID={order.transaction_id}, Очередь={queue_number}, Позиция={queue_position}")

        return Response({
            "id": order.id,
            "transaction_id": transaction_id,
            "status": order.status,
            "program_name": program.name,
            "program_price": float(program.price),
            "date": formatted_date,
            "queue_number": queue_number,
            "queue_position": queue_position
        }, status=201)


class WashOrderPaymentView(APIView):
    """
    Эндпоинт для обработки типа оплаты и запуска мойки.

    Принимает JSON:
        {
            "transaction_id": "uuid",
            "payment_type": "cash" | "bank_card" | "mobile_app" | "loyalty_card",
            "ucn": "1234567890"  # опционально, только для loyalty_card
        }
    """
    def post(self, request):
        serializer = WashOrderPaymentSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        transaction_id = serializer.validated_data["transaction_id"]
        payment_type = serializer.validated_data["payment_type"]
        ucn = serializer.validated_data.get("ucn", "")

        order = get_object_or_404(WashOrder, transaction_id=transaction_id)

        if order.status in [
            WashOrder.Status.PAYED,
            WashOrder.Status.PROCESSING,
            WashOrder.Status.COMPLETED,
        ]:
            return Response(
                {"error": "Невозможно оплатить заказ с текущим статусом."}, status=400
            )

        order.status = WashOrder.Status.WAITING_PAYMENT
        order.payment_type = payment_type
        if ucn:
            order.ucn = ucn
        order.save()
        print(f"[LOG] Статус заказа {order.transaction_id} обновлён: waiting_payment")

        if payment_type == "cash":
            cash_payment()

        elif payment_type == "bank_card":
            print(f"[VENDOTEK] Начало обработки оплаты по банковской карте для заказа {order.transaction_id}")
            success, error_message = bank_card_payment(order)
            if not success:
                order.status = WashOrder.Status.FAILED
                order.save(update_fields=["status"])
                print(f"[VENDOTEK] Оплата не удалась для заказа {order.transaction_id}. Статус изменен на FAILED.")
                return Response(
                    {"error": f"Ошибка оплаты по банковской карте: {error_message}"},
                    status=400,
                )
            print(f"[VENDOTEK] Оплата успешно завершена для заказа {order.transaction_id}")

        elif payment_type == "mobile_app":
            return mobile_app_payment(order)

        elif payment_type == "loyalty_card":
            print(f"[LOYALTY] Начало обработки оплаты по карте лояльности для заказа {order.transaction_id}")
            success, error_message = loyalty_card_payment(order, ucn)
            if not success:
                order.status = WashOrder.Status.FAILED
                order.save(update_fields=["status"])
                print(f"[LOYALTY] Оплата не удалась для заказа {order.transaction_id}. Статус изменен на FAILED.")
                return Response(
                    {"error": f"Ошибка оплаты по карте лояльности: {error_message}"},
                    status=400,
                )
            print(f"[LOYALTY] Оплата успешно завершена для заказа {order.transaction_id}")

        else:
            return Response({"error": "Неверный тип оплаты"}, status=400)

        order.status = WashOrder.Status.PAYED

        if payment_type in ("cash", "bank_card"):
            qr_code = send_receipt_request(order)
            if qr_code:
                order.qr_code = qr_code
                print(f"[QR] Чек успешно получен: {qr_code}")
            else:
                print("[QR] Не удалось получить чек.")

        if is_car_wash_busy():
            try:
                queue_number, queue_position = assign_queue_number_and_position()
                order.queue_number = queue_number
                order.queue_position = queue_position
                print(
                    f"[LOG] Заказ {order.transaction_id} поставлен в очередь: "
                    f"номер={queue_number}, позиция={queue_position}"
                )
            except ValueError as e:
                return Response({"error": str(e)}, status=400)
        else:
            print(
                f"[LOG] Мойка свободна. Заказ {order.transaction_id} будет запускаться немедленно."
            )

        queue_number_to_return = order.queue_number
        order.save()
        print(f"[LOG] Статус заказа {order.transaction_id} обновлён: payed")

        return Response(
            {
                "message": "Оплата прошла успешно. Ожидание подтверждения от терминала.",
                "queue_number": queue_number_to_return,  # Может быть None
            },
            status=200,
        )
