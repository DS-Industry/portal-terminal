import pytest

from orders.models import WashOrder, Program
from orders import queue_option


@pytest.mark.django_db
def test_is_car_wash_busy_true_and_false(program_factory):
    """
    Есть PROCESSING — занято; нет PROCESSING — свободно.
    """
    # свободно
    assert queue_option.is_car_wash_busy() is False

    # создаём заказ в обработке -> занято
    p = Program.objects.first() or program_factory()
    WashOrder.objects.create(
        program=p,
        program_price=p.price,
        transaction_id="tx-busy",
        status=WashOrder.Status.PROCESSING,
        payment_type=WashOrder.PaymentType.CASH,
    )
    assert queue_option.is_car_wash_busy() is True

    # завершаем заказ -> свободно
    o = WashOrder.objects.get(transaction_id="tx-busy")
    o.status = WashOrder.Status.COMPLETED
    o.save()
    assert queue_option.is_car_wash_busy() is False


@pytest.mark.django_db
def test_assign_queue_number_and_position_increments_and_limits(program_factory):
    """
    Кол-во активных в очереди -> позиция = n+1.
    При 5 элементах — ValueError («Очередь переполнена»).
    """
    p = Program.objects.first() or program_factory()

    def _mk(i, status=WashOrder.Status.CREATED):
        return WashOrder.objects.create(
            program=p,
            program_price=p.price,
            transaction_id=f"tx-{i}",
            status=status,
            payment_type=WashOrder.PaymentType.CASH,
            queue_number=f"A-{i}",
            queue_position=i,  # важно: считаются только queue_number != NULL и подходящие статусы
        )

    # 4 заказа в активных статусах
    _mk(1, WashOrder.Status.CREATED)
    _mk(2, WashOrder.Status.WAITING_PAYMENT)
    _mk(3, WashOrder.Status.PAYED)
    _mk(4, WashOrder.Status.CREATED)

    qn, pos = queue_option.assign_queue_number_and_position()
    assert isinstance(qn, str) and qn.startswith("A-")  # формат «A-<номер>»
    assert pos == 5  # 4 активных -> следующая позиция 5

    # добавим ещё один, чтобы стало 5 — дальше должно упасть
    _mk(5, WashOrder.Status.CREATED)
    with pytest.raises(ValueError):
        queue_option.assign_queue_number_and_position()  # очередь переполнена (лимит 5)


@pytest.mark.django_db
def test_update_queue_positions_after_start_shifts(program_factory):
    """
    1 -> 0, 2 -> 1, 3 -> 2 и т.д.
    """
    p = Program.objects.first() or program_factory()
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
    o3 = WashOrder.objects.create(
        program=p, program_price=p.price, transaction_id="tx-3",
        status=WashOrder.Status.PAYED, payment_type=WashOrder.PaymentType.CASH,
        queue_number="A-3", queue_position=3,
    )

    queue_option.update_queue_positions_after_start()

    o1.refresh_from_db(); o2.refresh_from_db(); o3.refresh_from_db()
    assert (o1.queue_position, o2.queue_position, o3.queue_position) == (0, 1, 2)


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
    assert queue_option.is_car_wash_busy() is False

    queue_option.try_run_next_car_wash()

    # функция должна вызвать старт именно для нашего заказа после сдвига в позицию 0
    order.refresh_from_db()
    assert order.queue_position == 0
    assert called["args"] == "tx-q"
