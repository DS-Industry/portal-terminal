# tests/test_queue_autostart_smoke.py
import pytest
from orders.models import WashOrder, Program
from orders import queue_option


@pytest.mark.django_db
def test_autostart_chain_without_sleeps(monkeypatch, program_factory):
    """
    Smoke: проверяем, что при вызове try_run_next_car_wash():
      - позиции сдвигаются (1->0, 2->1),
      - стартуется заказ с позицией 0,
      - после «завершения» первого сразу стартует следующий из очереди.
    Без реальных sleep: подменяем start_car_wash на синхронный мок.
    """
    p = Program.objects.first() or program_factory()

    # Два оплаченных заказа в очереди: позиции 1 и 2
    o1 = WashOrder.objects.create(
        program=p, program_price=p.price, transaction_id="tx-1",
        status=WashOrder.Status.PAYED, payment_type=WashOrder.PaymentType.CASH,
        queue_number="A-1", queue_position=1,
    )
    o2 = WashOrder.objects.create(
        program=p, program_price=p.price, transaction_id="tx-2",
        status=WashOrder.Status.PAYED, payment_type=WashOrder.PaymentType.CASH,
        queue_number="A-2", queue_position=2,
    )

    calls = []

    def _fake_start_car_wash(order):
        """
        Имитация «быстрой мойки»: сразу завершаем заказ и запускаем следующий.
        """
        calls.append(order.transaction_id)
        # processing -> completed (пропускаем processing для простоты)
        order.status = WashOrder.Status.COMPLETED
        order.queue_position = None
        order.queue_number = None
        order.save()
        # сразу запускаем следующий в цепочке
        queue_option.try_run_next_car_wash()

    # Патчим целевую функцию, которую вызывает try_run_next_car_wash
    monkeypatch.setattr("orders.start_carwash.start_car_wash", _fake_start_car_wash)

    # Убедимся, что пост свободен
    assert queue_option.is_car_wash_busy() is False

    # Первый вызов: позиции сдвинутся (1->0, 2->1) и стартует o1
    queue_option.try_run_next_car_wash()

    # Обновим из БД
    o1.refresh_from_db()
    o2.refresh_from_db()

    # Оба заказа должны быть завершены (наш мок завершает и сразу запускает следующий)
    assert o1.status == WashOrder.Status.COMPLETED
    assert o2.status == WashOrder.Status.COMPLETED
    assert o1.queue_position is None and o2.queue_position is None

    # Порядок запуска: сначала tx-1, затем tx-2
    assert calls == ["tx-1", "tx-2"]
