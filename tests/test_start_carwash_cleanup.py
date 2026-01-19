import pytest
from orders.models.models import Program, WashOrder
from orders import start_carwash as sc

@pytest.mark.django_db
def test_run_wash_cleans_queue_and_calls_next(monkeypatch, program_factory):
    # не спим
    monkeypatch.setattr("orders.start_carwash.time.sleep", lambda s: None)

    # отследим вызов следующего шага
    called = {"hits": 0}
    def _fake_try():
        called["hits"] += 1
    monkeypatch.setattr("orders.queue_option.try_run_next_car_wash", _fake_try)

    p = Program.objects.first() or program_factory()
    o = WashOrder.objects.create(
        program=p,
        program_price=p.price,
        transaction_id="tx-cleanme",
        status=WashOrder.Status.PAYED,
        queue_number="A-1",
        queue_position=0,
    )

    # вызовем внутреннюю функцию синхронно (без планировщика)
    sc._run_wash(o.id)

    o.refresh_from_db()
    assert o.status == WashOrder.Status.COMPLETED
    assert o.queue_number is None and o.queue_position is None
    assert called["hits"] == 1
