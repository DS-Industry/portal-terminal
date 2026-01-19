import pytest
from django.urls import reverse
from orders.models.models import Program, WashOrder
from orders import payments as payments_module


@pytest.mark.django_db
def test_pay_cash_when_busy_puts_order_into_queue(
    monkeypatch, api_client, terminal_status, receipt_config, program_factory, make_processing_order
):
    """
    Когда пост занят (есть заказ в PROCESSING), оплата cash:
      - переводит заказ в PAYED,
      - назначает queue_number и queue_position >= 1,
      - сохраняет QR кода чека в заказ.
    """

    # пост уже занят действующим заказом
    busy_order = make_processing_order()
    assert busy_order.status == WashOrder.Status.PROCESSING

    # ускоряем тесты: не спим при "оплате" и не ходим во внешний сервис чеков
    monkeypatch.setattr(payments_module, "cash_payment", lambda: None)
    monkeypatch.setattr("orders.views.send_receipt_request", lambda order: "QR-QUEUE")

    # создаём программу и заказ
    program_factory(name="Очередь", price="210.00")
    program = Program.objects.first()
    create_res = api_client.post(
        reverse("create-order"), {"program_id": program.id}, format="json"
    )
    assert create_res.status_code == 201
    tx = create_res.json()["transaction_id"]

    # оплачиваем наличными
    pay_res = api_client.post(
        reverse("washorder-pay"),
        {"transaction_id": tx, "payment_type": "cash"},
        format="json",
    )
    assert pay_res.status_code == 200

    # проверяем состояние заказа
    order = WashOrder.objects.get(transaction_id=tx)
    assert order.status == WashOrder.Status.PAYED
    assert order.qr_code == "QR-QUEUE"
    assert order.queue_number is not None
    assert isinstance(order.queue_position, int) and order.queue_position >= 1
