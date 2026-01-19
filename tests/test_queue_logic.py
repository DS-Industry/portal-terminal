import pytest

from orders.models.models import Program
from orders.models.wash_order import WashOrder
from orders import queue_option


@pytest.mark.django_db
def test_is_car_wash_busy_true_and_false(program_factory):
    """
    Есть PROCESSING — занято; нет PROCESSING — свободно.
    """
    # свободно
    assert WashOrder.is_car_wash_busy() is False

    # создаём заказ в обработке -> занято
    p = Program.objects.first() or program_factory()
    WashOrder.objects.create(
        program=p,
        program_price=p.price,
        transaction_id="tx-busy",
        status=WashOrder.Status.PROCESSING,
        payment_type=WashOrder.PaymentType.CASH,
    )
    assert WashOrder.is_car_wash_busy() is True

    # завершаем заказ -> свободно
    o = WashOrder.objects.get(transaction_id="tx-busy")
    o.status = WashOrder.Status.COMPLETED
    o.save()
    assert WashOrder.is_car_wash_busy() is False


@pytest.mark.django_db
def test_try_run_next_car_wash_starts_payed_from_zero(monkeypatch, program_factory):
    """
    Когда свободно:
      - позиции сначала сдвигаются (1 -> 0),
      - берётся PAYED с позицией 0,
      - вызывается start_car_wash(next_order).
    """
    p = Program.objects.first() or program_factory()
    # один оплаченный в очереди на позиции 1 (после сдвига станет 0)
    order = WashOrder.objects.create(
        program=p, program_price=p.price, transaction_id="tx-q",
        status=WashOrder.Status.PAYED, payment_type=WashOrder.PaymentType.CASH,
        queue_number="A-10", queue_position=1,
    )

    called = {"args": None}

    # try_run_next_car_wash делает ЛЕНИВЫЙ импорт: from .start_carwash import start_car_wash
    # поэтому патчим целевую функцию в модуле start_carwash
    def _fake_start(o):
        called["args"] = o.transaction_id

    monkeypatch.setattr("orders.start_carwash.start_car_wash", _fake_start)

    # убедимся, что нет PROCESSING-заказов => пост свободен
    assert WashOrder.is_car_wash_busy() is False

    # функция должна вызвать старт именно для нашего заказа после сдвига в позицию 0
    order.refresh_from_db()
    assert order.queue_position == 0
    assert called["args"] == "tx-q"
