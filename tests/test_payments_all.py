import pytest
from django.urls import reverse
from orders.models import Program, WashOrder
from orders import payments as payments_module


# --- CASH ---

@pytest.mark.django_db
def test_pay_cash_success_sets_payed_and_receipt_saved(
    monkeypatch, api_client, terminal_status, receipt_config, program_factory
):
    """
    Успешная оплата наличными:
      - статус -> PAYED
      - чек напечатан и сохранён в order.qr_code
      - если пост свободен — заказ без очереди
    """
    # ускоряем оплату и печать
    monkeypatch.setattr(payments_module, "cash_payment", lambda: None)
    monkeypatch.setattr("orders.views.send_receipt_request", lambda order: "QR-CASH")

    program_factory(name="Наличные", price="200.00")
    program = Program.objects.first()

    tx = api_client.post(
        reverse("create-order"), {"program_id": program.id}, format="json"
    ).json()["transaction_id"]

    res = api_client.post(
        reverse("washorder-pay"),
        {"transaction_id": tx, "payment_type": "cash"},
        format="json",
    )
    assert res.status_code == 200

    order = WashOrder.objects.get(transaction_id=tx)
    assert order.status == WashOrder.Status.PAYED
    assert order.qr_code == "QR-CASH"
    assert order.queue_position is None and order.queue_number is None


# --- BANK CARD ---

@pytest.mark.django_db
def test_pay_bank_card_success_sets_payed_and_receipt_saved(
    monkeypatch, api_client, terminal_status, receipt_config, program_factory
):
    """
    Успешная оплата банковской картой:
      - статус -> PAYED
      - чек напечатан и сохранён
      - без очереди если пост свободен
    """
    monkeypatch.setattr(payments_module, "bank_card_payment", lambda: None)
    monkeypatch.setattr("orders.views.send_receipt_request", lambda order: "QR-BANK")

    program_factory(name="Карта", price="250.00")
    program = Program.objects.first()

    tx = api_client.post(
        reverse("create-order"), {"program_id": program.id}, format="json"
    ).json()["transaction_id"]

    res = api_client.post(
        reverse("washorder-pay"),
        {"transaction_id": tx, "payment_type": "bank_card"},
        format="json",
    )
    assert res.status_code == 200

    order = WashOrder.objects.get(transaction_id=tx)
    assert order.status == WashOrder.Status.PAYED
    assert order.qr_code == "QR-BANK"
    assert order.queue_position is None and order.queue_number is None


@pytest.mark.django_db
def test_pay_bank_card_when_busy_puts_order_into_queue(
    monkeypatch, api_client, terminal_status, receipt_config, program_factory, make_processing_order
):
    """
    При занятом посте оплата банковской картой ставит заказ в очередь и печатает чек.
    """
    # есть активный PROCESSING-заказ -> пост занят
    make_processing_order()

    monkeypatch.setattr(payments_module, "bank_card_payment", lambda: None)
    monkeypatch.setattr("orders.views.send_receipt_request", lambda order: "QR-BANK-Q")

    program_factory(name="Карта-Очередь", price="210.00")
    program = Program.objects.first()

    tx = api_client.post(
        reverse("create-order"), {"program_id": program.id}, format="json"
    ).json()["transaction_id"]

    res = api_client.post(
        reverse("washorder-pay"),
        {"transaction_id": tx, "payment_type": "bank_card"},
        format="json",
    )
    assert res.status_code == 200

    order = WashOrder.objects.get(transaction_id=tx)
    assert order.status == WashOrder.Status.PAYED
    assert order.qr_code == "QR-BANK-Q"
    assert order.queue_number is not None
    assert isinstance(order.queue_position, int) and order.queue_position >= 1


# --- LOYALTY CARD ---

@pytest.mark.django_db
def test_pay_loyalty_success_sets_payed_without_receipt(
    monkeypatch, api_client, terminal_status, program_factory
):
    """
    Успешная оплата по карте лояльности:
      - статус -> PAYED
      - чек НЕ печатается (по твоим правилам)
    """
    class _RespOK:
        def raise_for_status(self): ...
        def json(self): return {"errcode": 200}

    # замокаем HTTP в модуле payments
    monkeypatch.setattr("orders.payments.requests.post", lambda *a, **k: _RespOK())

    program_factory(name="Лояльность-OK", price="300.00")
    program = Program.objects.first()

    tx = api_client.post(
        reverse("create-order"), {"program_id": program.id}, format="json"
    ).json()["transaction_id"]

    res = api_client.post(
        reverse("washorder-pay"),
        {"transaction_id": tx, "payment_type": "loyalty_card", "ucn": "111222"},
        format="json",
    )
    assert res.status_code == 200

    order = WashOrder.objects.get(transaction_id=tx)
    assert order.status == WashOrder.Status.PAYED
    # чек при лояльности не печатаем
    assert not order.qr_code


@pytest.mark.django_db
def test_pay_loyalty_failure_sets_failed(
    monkeypatch, api_client, terminal_status, program_factory
):
    """
    Неуспешная оплата лояльностью:
      - вьюха возвращает 400,
      - статус -> FAILED,
      - чек не печатается.
    """
    class _RespBad:
        def raise_for_status(self): ...
        def json(self): return {"errcode": 500, "errmes": "Недостаточно средств"}

    monkeypatch.setattr("orders.payments.requests.post", lambda *a, **k: _RespBad())

    program_factory(name="Лояльность-FAIL", price="300.00")
    program = Program.objects.first()

    tx = api_client.post(
        reverse("create-order"), {"program_id": program.id}, format="json"
    ).json()["transaction_id"]

    res = api_client.post(
        reverse("washorder-pay"),
        {"transaction_id": tx, "payment_type": "loyalty_card", "ucn": "999000"},
        format="json",
    )
    assert res.status_code == 400

    order = WashOrder.objects.get(transaction_id=tx)
    assert order.status == WashOrder.Status.FAILED
    assert not order.qr_code
