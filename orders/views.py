import time

from django.core.exceptions import ValidationError

from django.utils import timezone

from .ping_dscloud import _start_payed_without_queue
from .websocket_service import OrderWebSocketService

from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework.views import APIView
from .encoder import EncodedParams

from orders.models.loyalty_settings import LoyaltySettings
from orders.models.wash_order import WashOrder, OrderCanceled, PaymentFailed
from orders.models.terminal_status import TerminalStatus
from orders.models.program import Program
from .serializers import (
    ProgramSerializer,
    WashOrderPaymentSerializer,
    WashOrderDetailSerializer
)
from .receipt_qr import send_receipt_request
from .payment import (
    cancel_bank_card_payment
)
from .payment_service import PaymentService
from .ucn import (
    LoyaltyManager
)
from orders.payments.opti.service import OptiPaymentService


class ProgramViewSet(viewsets.ModelViewSet):
    """
    ViewSet для управления программами мойки.
    """
    queryset = Program.get_visible_programs()
    serializer_class = ProgramSerializer


class ProgramListView(APIView):
    """
    Эндпоинт получения списка программ мойки.
    """

    def get(self, request):
        programs = Program.get_visible_programs().order_by("id")
        serializer = ProgramSerializer(programs, many=True)
        return Response(serializer.data)


class TerminalDataView(APIView):
    """
    Эндпоинт получения флага лояльности
    """

    def get(self, request):
        terminal = TerminalStatus.get_terminal()
        return Response({'car_wash_id': terminal.car_wash_identifier, 'device_id': terminal.identifier})


class LtyCheckView(APIView):
    """
    Эндпоинт получения флага лояльности
    """

    def get(self, request):
        LoyaltySettings.delete_settings()
        terminal = TerminalStatus.get_terminal()
        return Response({'loyalty_status': terminal.loyalty_status})


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
        terminal = TerminalStatus.get_terminal()
        if not terminal.mobile_app_qr_code:
            error_msg = "QR-код для старого мобильного приложения не настроен в TerminalStatus."
            print(f"[MOBILE-PAYMENT-QR] ОШИБКА: {error_msg}")
            return Response({'error': error_msg}, status=500)

        qr_code_string = terminal.mobile_app_qr_code
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

        try:
            serializer = WashOrderPaymentSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            program = serializer.validated_data["program_id"]
            payment_type = serializer.validated_data["payment_type"]
            ucn = serializer.validated_data.get("ucn", "")
            terminal = TerminalStatus.get_terminal()

            if not WashOrder.can_create_new_order(terminal):
                return Response(
                    {"error": "Мойка занята и очередь недоступна"},
                    status=400
                )

            WashOrder.reset_queue_if_needed()

            order = WashOrder.create_order(program=program, payment_type=payment_type, ucn=ucn)
            OrderWebSocketService.send_order_status_update(order)

            print(
                f"[LOG] Новый заказ создан: ID={order.transaction_id}, Очередь={order.queue_number}, Позиция={order.queue_position}")
            order.mark_waiting_payment()
            order.ensure_not_canceled()
            PaymentService.process_payment(order, terminal, payment_type, ucn)

            try:
                order.assign_queue_if_possible(terminal)
            except ValueError as e:
                return Response({"error": str(e)}, status=400)

            order.mark_payed()

            if payment_type in ("cash", "bank_card"):
                #qr_code = send_receipt_request(order)
                time.sleep(5)
                qr_code = "test_qr"
                if qr_code:
                    order.qr_code = qr_code
                    print(f"[QR] Чек успешно получен: {qr_code}")

                    order.save(update_fields=['qr_code'])
                    print(f"[LOG] Статус заказа {order.transaction_id} обновлён: изменение в qr-code")
                else:
                    print("[QR] Не удалось получить чек.")

            return Response(
                {
                    "message": "Оплата прошла успешно. Ожидание подтверждения от терминала.",
                    "queue_number": order.queue_number,  # Может быть None
                },
                status=200,
            )
        except OrderCanceled as e:
            return Response({"error": str(e)}, status=400)
        except PaymentFailed as e:
            OrderWebSocketService.send_error(e.ws_code)
            return Response({"error": str(e)}, status=400)


class WashOrderCancellationView(APIView):
    def post(self, request, order_id):

        try:
            order = WashOrder.objects.get(pk=order_id)
        except WashOrder.DoesNotExist:
            return Response({'error': 'Заказ не найден'}, status=400)

        allowed_statuses = [WashOrder.Status.CREATED, WashOrder.Status.WAITING_PAYMENT]

        if order.status not in allowed_statuses:
            print(f"[LOG] Ошибка отмены заказа по статусу: {order.transaction_id}.")
            return Response(
                {
                    'error': f'Невозможно отменить заказ со статусом "{order.get_status_display()}"'
                },
                status=400
            )

        order.mark_canceled()

        if order.payment_type == 'bank_card':
            #cancellation_success = cancel_bank_card_payment(order)
            time.sleep(5)
            cancellation_success = True
            if not cancellation_success:
                print(f"[VENDOTEK] Заказ {order.transaction_id} отменен, но ошибка отмены в Vendotek")

        elif order.payment_type == "opti":

            if not OptiPaymentService.cancel(order):
                print(f"[LOYALTY] Заказ {order.transaction_id} отменен локально, но не отменён в Opti")

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

        if not order.can_start():
            return Response(
                {
                    'error': f'Невозможно запустить заказ со статусом "{order.get_status_display()}"'
                },
                status=400
            )

        if order.is_waiting_in_queue():
            print(f"[LOG] У заказа {order.transaction_id} есть номер в очереди: {order.queue_number}.")
            return Response(
                {
                    "message": "Заказ стоит в очереди."
                },
                status=200
            )

        terminal = TerminalStatus.get_terminal()
        _start_payed_without_queue(order, terminal, 3)
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
        OrderWebSocketService.send_card_reader(1)
        ucn_number = LoyaltyManager.read_card_ucn()
        OrderWebSocketService.send_card_reader(2)
        result = LoyaltyManager.get_balance_and_update(ucn_number)
        OrderWebSocketService.send_card_reader(3)

        return Response(
            {
                "message": "Чтение карты завершено",
                "success": result.get('success', False),
                "ucn": result.get('ucn_number'),
                "balance": result.get('balance'),
                "discount": result.get('discount'),
                "cashback": result.get('cashback')
            },
            status=200
        )
