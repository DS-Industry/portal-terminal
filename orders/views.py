# orders/views.py
from rest_framework import viewsets
from rest_framework import status as drf_status
from rest_framework.views import APIView
from rest_framework.response import Response

from django.shortcuts import get_object_or_404
from django.utils import timezone

from .models import Program, WashOrder, WashSettings
from .serializers import (
    ProgramSerializer,
    WashOrderCreateSerializer,
    WashOrderPaymentSerializer
)

import uuid
import time

# ---------------------------
# 📌 ФУНКЦИИ ДЛЯ ОЧЕРЕДИ
# ---------------------------

def is_car_wash_busy() -> bool:
    """
    Проверяет, занята ли мойка (есть заказ со статусом PROCESSING).
    """
    return WashOrder.objects.filter(status=WashOrder.Status.PROCESSING).exists()


def reset_queue_if_needed():
    """
    Сбрасывает очередь, если все заказы завершены.
    """
    active_statuses = [
        WashOrder.Status.CREATED,
        WashOrder.Status.WAITING_PAYMENT,
        WashOrder.Status.PAYED,
        WashOrder.Status.PROCESSING,
    ]
    if not WashOrder.objects.filter(status__in=active_statuses).exists():
        WashOrder.objects.update(queue_number=None, queue_position=None)
        print("[LOG] Очередь сброшена — мойка и очередь пусты.")


def get_next_queue_number() -> str:
    """
    Возвращает следующий уникальный номер очереди в формате A-<номер>.
    """
    existing = WashOrder.objects.exclude(queue_number__isnull=True).values_list('queue_number', flat=True)
    max_num = 0
    for q in existing:
        try:
            num = int(q.split("-")[1])
            max_num = max(max_num, num)
        except (IndexError, ValueError):
            continue
    return f"A-{max_num + 1}"


def assign_queue_number_and_position() -> tuple[str, int]:
    """
    Назначает queue_number и queue_position новому заказу.

    Возвращает:
        (queue_number, queue_position)
    """
    queue = WashOrder.objects.filter(
        queue_number__isnull=False,
        status__in=[
            WashOrder.Status.CREATED,
            WashOrder.Status.WAITING_PAYMENT,
            WashOrder.Status.PAYED,
        ]
    ).order_by("id")

    if queue.count() >= 5:
        raise ValueError("Очередь переполнена")

    return get_next_queue_number(), queue.count() + 1


def update_queue_positions_after_start():
    """
    После запуска мойки сдвигает позиции заказов в очереди.
    """
    queue = WashOrder.objects.filter(queue_position__isnull=False).order_by("queue_position")
    for order in queue:
        if order.queue_position == 1:
            order.queue_position = 0
        elif order.queue_position is not None and order.queue_position > 1:
            order.queue_position -= 1
        order.save()
    print("[LOG] Очередь обновлена после запуска мойки.")


def try_run_next_car_wash():
    """
    Если мойка свободна и есть заказ с позицией 0 и статусом PAYED — запускает мойку.
    Если есть очередь, перед запуском обновляет позиции.
    """
    if is_car_wash_busy():
        return

    # Сначала обновим позиции: 1 → 0, 2 → 1 и т.д.
    update_queue_positions_after_start()

    # И только потом ищем того, у кого позиция = 0
    next_order = WashOrder.objects.filter(
        status=WashOrder.Status.PAYED,
        queue_position=0
    ).order_by("id").first()

    if next_order:
        print(f"[LOG] Заказ {next_order.transaction_id} запускается с позиции 0.")
        start_car_wash(next_order)



# ---------------------------
# 📌 API-КЛАССЫ
# ---------------------------

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
            "queue_number": А-3,
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
        current_date = timezone.now().strftime('%d.%m.%Y - %H:%M:%S')

        order = WashOrder.objects.create(
            program=program,
            program_price=program.price,
            transaction_id=transaction_id,
            date=current_date,
            status=WashOrder.Status.CREATED,
            ucn=ucn,
            queue_number=queue_number,
            queue_position=queue_position
        )

        print(f"[LOG] Новый заказ создан: ID={order.transaction_id}, Очередь={queue_number}, Позиция={queue_position}")

        return Response({
            "id": order.id,
            "transaction_id": transaction_id,
            "status": order.status,
            "program_name": program.name,
            "program_price": float(program.price),
            "date": current_date,
            "queue_number": queue_number,
            "queue_position": queue_position
        }, status=201)


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
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        transaction_id = serializer.validated_data['transaction_id']
        payment_type = serializer.validated_data['payment_type']
        order = get_object_or_404(WashOrder, transaction_id=transaction_id)

        if order.status in [WashOrder.Status.PAYED, WashOrder.Status.PROCESSING, WashOrder.Status.COMPLETED]:
            return Response({'error': 'Невозможно оплатить заказ с текущим статусом.'}, status=400)

        # Устанавливаем статус "ожидание оплаты"
        order.status = WashOrder.Status.WAITING_PAYMENT
        order.payment_type = payment_type
        order.save()
        print(f"[LOG] Статус заказа {order.transaction_id} обновлён: waiting_payment")

        # Симуляция оплаты
        if payment_type == 'cash':
            cash_payment()
        elif payment_type == 'bank_card':
            bank_card_payment()
        elif payment_type == 'mobile_app':
            mobile_app_payment()
        elif payment_type == 'loyalty_card':
            loyalty_card_payment()

        # После успешной оплаты — статус "оплачен"
        order.status = WashOrder.Status.PAYED

        if is_car_wash_busy():
            try:
                queue_number, queue_position = assign_queue_number_and_position()
                order.queue_number = queue_number
                order.queue_position = queue_position
                print(f"[LOG] Заказ {order.transaction_id} поставлен в очередь: номер={queue_number}, позиция={queue_position}")
            except ValueError as e:
                return Response({'error': str(e)}, status=400)
        else:
            print(f"[LOG] Мойка свободна. Заказ {order.transaction_id} будет запускаться немедленно.")

        # Сохраняем все обновления
        order.save()
        print(f"[LOG] Статус заказа {order.transaction_id} обновлён: payed")

        # Запуск мойки, если можно
        if order.queue_position is None and not is_car_wash_busy():
            print(f"[LOG] Мойка свободна. Заказ {order.transaction_id} запускается сразу без очереди.")
            start_car_wash(order)
        else:
            try_run_next_car_wash()

        return Response({'message': 'Оплата прошла успешно'}, status=200)


# ---------------------------
# 📌 МОЙКА
# ---------------------------

def start_car_wash(order):
    """
    Запускает мойку: статус processing → completed через 120 сек.
    После завершения мойки — запускает следующий заказ (если есть).
    """
    print(f"[LOG] Запуск мойки по программе: {order.program.name}")
    order.status = WashOrder.Status.PROCESSING
    order.save()

    time.sleep(120)

    order.status = WashOrder.Status.COMPLETED
    order.queue_position = None
    order.queue_number = None
    order.save()
    print(f"[LOG] Мойка завершена. Статус заказа {order.transaction_id} обновлён: completed")

    # 🔁 Переход к следующему заказу
    delay = WashSettings.objects.first().delay_between_washes if WashSettings.objects.exists() else 5
    print(f"[LOG] Начало следующей мойки через {delay} сек...")
    time.sleep(delay)
    try_run_next_car_wash()

# ---------------------------
# 📌 ОПЛАТА (каждая отдельно)
# ---------------------------

def bank_card_payment():
    """
    Симуляция оплаты банковской картой.
    """
    print("[LOG] Выбран тип оплаты: bank_card")
    time.sleep(5)
    print("[LOG] Оплата банковской картой прошла успешно.")


def cash_payment():
    """
    Симуляция оплаты наличными.
    """
    print("[LOG] Выбран тип оплаты: cash")
    time.sleep(5)
    print("[LOG] Оплата наличными прошла успешно.")


def mobile_app_payment():
    """
    Симуляция оплаты через мобильное приложение.
    """
    print("[LOG] Выбран тип оплаты: mobile_app")
    time.sleep(5)
    print("[LOG] Оплата через мобильное приложение прошла успешно.")


def loyalty_card_payment():
    """
    Симуляция оплаты по карте лояльности.
    """
    print("[LOG] Выбран тип оплаты: loyalty_card")
    time.sleep(5)
    print("[LOG] Оплата по карте лояльности прошла успешно.")
