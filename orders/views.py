import uuid
import time

from django.apps import apps
from django.utils import timezone

from .ping_dscloud import _start_payed_without_queue
from .websocket_service import OrderWebSocketService

from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework.views import APIView
from .encoder import EncodedParams

from .models import (
    Program,
    WashOrder,
    TerminalStatus,
    LoyaltySettings
)
from .serializers import (
    ProgramSerializer,
    WashOrderCreateSerializer,
    WashOrderPaymentSerializer,
    WashOrderDetailSerializer
)
from .receipt_qr import send_receipt_request
from .payments import (
    bank_card_payment,
    cash_payment,
    loyalty_card_payment,
    mobile_app_payment,
    cancel_bank_card_payment
)
from .queue_option import (
    assign_queue_number_and_position,
    is_car_wash_busy,
    reset_queue_if_needed,
)
from .ucn import (
    LoyaltyManager
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
        programs = Program.objects.filter(is_visibility=True).order_by('id')
        serializer = ProgramSerializer(programs, many=True)
        return Response(serializer.data)


class LtyCheckView(APIView):
    """
    Эндпоинт получения флага лояльности
    """

    def get(self, request):
        LoyaltySettings.delete_settings()
        terminal_status = TerminalStatus.objects.get()
        return Response({'loyalty_status': terminal_status.loyalty_status})


class UcnCheckView(APIView):
    """
    Эндпоинт получения ucn данных
    """

    def get(self, request):
        ucn_data = LoyaltySettings.get_settings()

        if not ucn_data:
            return Response(
                {
                    'ucn': None,
                    'discount': None,
                    'cashback': None,
                    'balance': None
                }
            )

        return Response(
            {
                'ucn': ucn_data.ucn,
                'discount': ucn_data.discount,
                'cashback': ucn_data.cashback,
                'balance': ucn_data.balance
            }
        )


class MobileQrView(APIView):
    """
    Эндпоинт получения QR для МП
    """

    def get(self, request):
        terminal_status = TerminalStatus.objects.first()
        if not terminal_status or not terminal_status.mobile_app_qr_code:
            error_msg = "QR-код для старого мобильного приложения не настроен в TerminalStatus."
            print(f"[MOBILE-PAYMENT-QR] ОШИБКА: {error_msg}")
            return Response({'error': error_msg}, status=500)

        qr_code_string = terminal_status.mobile_app_qr_code
        return Response({
            'qr_code': qr_code_string
        }, status=200)


class WashOrderPaymentView(APIView):
    """
    Эндпоинт для обработки типа оплаты и запуска мойки.

    Принимает JSON:
        {
            "program_id": 1,
            "payment_type": "cash" | "bank_card" | "mobile_app" | "loyalty_card",
            "ucn": "1234567890"  # опционально, только для loyalty_card
        }
    """

    def post(self, request):

        serializer = WashOrderPaymentSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        program_id = serializer.validated_data['program_id']
        payment_type = serializer.validated_data["payment_type"]
        ucn = serializer.validated_data.get("ucn", "")

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
        OrderWebSocketService.send_order_status_update(order)

        print(f"[LOG] Новый заказ создан: ID={order.transaction_id}, Очередь={queue_number}, Позиция={queue_position}")

        order.status = WashOrder.Status.WAITING_PAYMENT
        order.payment_type = payment_type
        if ucn:
            order.ucn = ucn
        order.save()
        OrderWebSocketService.send_order_status_update(order)
        print(f"[LOG] Статус заказа {order.transaction_id} обновлён: waiting_payment")

        order.refresh_from_db()
        if order.status == WashOrder.Status.CANCELED:
            return Response(
                {"error": "Заказ был отменен до начала оплаты"},
                status=400
            )

        if payment_type == "cash":
            print(f"[CASH_PAYMENT] Начало обработки оплаты по наличке для заказа {order.transaction_id}")
            success, error_message = cash_payment(order)
            order.refresh_from_db()
            if order.status == WashOrder.Status.CANCELED:
                return Response(
                    {"error": "Заказ был отменен во время обработки платежа"},
                    status=400
                )

            if not success:
                order.status = WashOrder.Status.FAILED
                order.save(update_fields=["status"])
                print(f"[CASH_PAYMENT] Оплата не удалась для заказа {order.transaction_id}. Статус изменен на FAILED.")
                OrderWebSocketService.send_error(1001)
                return Response(
                    {"error": f"Ошибка оплаты по наличке: {error_message}"},
                    status=400,
                )
            print(f"[CASH_PAYMENT] Оплата успешно завершена для заказа {order.transaction_id}")

        elif payment_type == "bank_card":
            print(f"[VENDOTEK] Начало обработки оплаты по банковской карте для заказа {order.transaction_id}")
            success, error_message = bank_card_payment(order)

            order.refresh_from_db()
            if order.status == WashOrder.Status.CANCELED:
                return Response(
                    {"error": "Заказ был отменен во время обработки платежа"},
                    status=400
                )
            if not success:
                order.status = WashOrder.Status.FAILED
                order.save(update_fields=["status"])
                print(f"[VENDOTEK] Оплата не удалась для заказа {order.transaction_id}. Статус изменен на FAILED.")
                OrderWebSocketService.send_error(1002)
                return Response(
                    {"error": f"Ошибка оплаты по банковской карте: {error_message}"},
                    status=400,
                )
            print(f"[VENDOTEK] Оплата успешно завершена для заказа {order.transaction_id}")

            # отправляем событие "Безнал"
            try:
                ts = TerminalStatus.objects.first()
                device_id = int(ts.identifier) if ts and ts.identifier is not None else 0
                now_dt = timezone.now()

                params = EncodedParams(
                    oper=23,
                    status=1,
                    data=int(order.program_price),
                    counter=0,
                    localId=0,
                    begDate=now_dt,
                    endDate=now_dt,
                    deviceId=device_id
                )
                results = params.send_hex_to_server()
                print(f"[ENCODER_MANAGE] Bank card payment sent (oper=23): {results}")
            except Exception as e:
                print(f"[ENCODER_MANAGE] Error sending bank-card payment event: {e}")

        elif payment_type == "mobile_app":
            return mobile_app_payment(order)

        elif payment_type == "loyalty_card":
            print(f"[LOYALTY] Начало обработки оплаты по карте лояльности для заказа {order.transaction_id}")
            success, error_message = loyalty_card_payment(order, ucn)

            order.refresh_from_db()
            if order.status == WashOrder.Status.CANCELED:
                return Response(
                    {"error": "Заказ был отменен во время обработки платежа"},
                    status=400
                )
            if not success:
                order.status = WashOrder.Status.FAILED
                order.save(update_fields=["status"])
                print(f"[LOYALTY] Оплата не удалась для заказа {order.transaction_id}. Статус изменен на FAILED.")
                OrderWebSocketService.send_error(1003)
                return Response(
                    {"error": f"Ошибка оплаты по карте лояльности: {error_message}"},
                    status=400,
                )
            print(f"[LOYALTY] Оплата успешно завершена для заказа {order.transaction_id}")

        else:
            return Response({"error": "Неверный тип оплаты"}, status=400)

        order.status = WashOrder.Status.PAYED
        order.amount_sum = int(order.program_price)

        order.save()
        OrderWebSocketService.send_order_status_update(order)
        print(f"[LOG] Статус заказа {order.transaction_id} обновлён: payed")

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
        print(f"[LOG] Статус заказа {order.transaction_id} обновлён: изменение в qr-code")

        return Response(
            {
                "message": "Оплата прошла успешно. Ожидание подтверждения от терминала.",
                "queue_number": queue_number_to_return,  # Может быть None
            },
            status=200,
        )


class WashOrderCancellationView(APIView):
    def post(self, request, order_id):

        try:
            order = WashOrder.objects.get(pk=order_id)
        except WashOrder.DoesNotExist:
            return Response({'error': 'Заказ не найден'}, status=400)

        allowed_statuses = [WashOrder.Status.CREATED, WashOrder.Status.WAITING_PAYMENT]

        if order.status not in allowed_statuses:
            return Response(
                {
                    'error': f'Невозможно отменить заказ со статусом "{order.get_status_display()}"'
                },
                status=400
            )

        order.status = WashOrder.Status.CANCELED
        order.save(update_fields=["status"])
        print(f"[LOG] Заказ отменен {order.transaction_id}.")

        if order.payment_type == 'bank_card':
            cancellation_success = cancel_bank_card_payment(order)
            if not cancellation_success:
                print(f"[VENDOTEK] Заказ {order.transaction_id} отменен, но ошибка отмены в Vendotek")

        return Response(
            {
                "message": "Заказ отменен."
            },
            status=200,
        )


class WashOrderStartView(APIView):
    def post(self, request, order_id):

        try:
            order = WashOrder.objects.get(pk=order_id)
        except WashOrder.DoesNotExist:
            return Response({'error': 'Заказ не найден'}, status=400)

        print(f"[LOG] Пришел запрос на запуск {order.transaction_id}.")

        allowed_statuses = [WashOrder.Status.PAYED]

        if order.status not in allowed_statuses:
            return Response(
                {
                    'error': f'Невозможно запустить заказ со статусом "{order.get_status_display()}"'
                },
                status=400
            )

        TerminalStatus = apps.get_model('orders', 'TerminalStatus')

        _start_payed_without_queue(order, TerminalStatus, 3)
        print(f"[LOG] Заказ отправлен на запуск {order.transaction_id}.")

        return Response(
            {
                "message": "Заказ отправлен на запуск."
            },
            status=200,
        )


class WashOrderDetailView(APIView):
    """
    Получение информации о заказе
    """

    def get(self, request, order_id):

        try:
            order = WashOrder.objects.get(pk=order_id)
        except WashOrder.DoesNotExist:
            return Response(
                {'error': 'Заказ не найден'},
                status=404
            )

        serializer = WashOrderDetailSerializer(order)
        return Response(serializer.data, status=200)


class OpenReaderView(APIView):
    def post(self, request):
        time.sleep(5)
        result = LoyaltyManager.get_balance_and_update('794976664919')

        return Response(
            {
                "message": "Чтение карты завершено",
                "success": result.get('success', False),
                "balance": result.get('balance'),
                "discount": result.get('discount'),
                "cashback": result.get('cashback')
            },
            status=200
        )
