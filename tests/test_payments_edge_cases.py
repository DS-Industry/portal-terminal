import pytest
from django.urls import reverse
from orders.models.models import Program, WashOrder
from orders import payments as payments_module


# --- Переполненная очередь (cash/bank_card) ---

@pytest.mark.django_db
@pytest.mark.parametrize("payment_type", ["cash", "bank_card"])
def test_payment_queue_overflow_returns_400(
    payment_type, monkeypatch, api_client, terminal_status, receipt_config, program_factory, make_processing_order
):
    """
    Если пост занят и в очереди уже 5 активных заказов, новая оплата (cash/bank_card)
    должна вернуть 400 с понятной ошибкой.
    """
    # пост занят
    make_processing_order()

    # ускоряем оплату/печать
    if payment_type == "cash":
        monkeypatch.setattr(payments_module, "cash_payment", lambda: None)
    else:
        monkeypatch.setattr(payments_module, "bank_card_payment", lambda: None)
    monkeypatch.setattr("orders.views.send_receipt_request", lambda order: "QR-IGNORED")

    # создаём программу
    program_factory(name="Очередь-полная", price="200.00")
    p = Program.objects.first()

    # заполняем очередь до лимита (5)
    for i in range(1, 6):
        WashOrder.objects.create(
            program=p,
            program_price=p.price,
            transaction_id=f"tx-qfull-{i}",
            status=WashOrder.Status.PAYED,  # активный для очереди статус
            payment_type=WashOrder.PaymentType.CASH,
            queue_number=f"A-{i}",
            queue_position=i,
        )

    # создаём новый заказ
    tx = api_client.post(
        reverse("create-order"), {"program_id": p.id}, format="json"
    ).json()["transaction_id"]

    # пытаемся оплатить (должно упасть из-за переполнения)
    res = api_client.post(
        reverse("washorder-pay"),
        {"transaction_id": tx, "payment_type": payment_type},
        format="json",
    )
    assert res.status_code == 400
    body = res.json()
    # текст может отличаться, но ключ/смысл ошибки должен присутствовать
    assert any(k in body for k in ("error", "detail", "message"))


# --- waiting_payment выставляется до вызова обработчика ---

@pytest.mark.django_db
def test_waiting_payment_set_before_handler_call(
    monkeypatch, api_client, terminal_status, receipt_config, program_factory
):
    """
    Вьюха должна перевести заказ в waiting_payment до вызова конкретного обработчика оплаты.
    Проверяем на cash, но логика общая.
    """
    program_factory(name="WaitingPayment", price="150.00")
    p = Program.objects.first()
    tx = api_client.post(
        reverse("create-order"), {"program_id": p.id}, format="json"
    ).json()["transaction_id"]

    captured = {"seen_status": None}

    def _fake_cash_payment():
        # во время вызова обработчика статус уже должен быть waiting_payment
        o = WashOrder.objects.get(transaction_id=tx)
        captured["seen_status"] = o.status
        return None

    # мок обработчика и печати
    monkeypatch.setattr("orders.views.cash_payment", _fake_cash_payment)
    monkeypatch.setattr("orders.views.send_receipt_request", lambda order: "QR-CHECK")

    res = api_client.post(
        reverse("washorder-pay"),
        {"transaction_id": tx, "payment_type": "cash"},
        format="json",
    )
    assert res.status_code == 200
    assert captured["seen_status"] == WashOrder.Status.WAITING_PAYMENT


# --- для loyalty_card не печатаем чек ---

@pytest.mark.django_db
def test_loyalty_does_not_call_receipt_print(
    monkeypatch, api_client, terminal_status, program_factory
):
    """
    При успешной оплате лояльностью печать чека НЕ вызывается.
    """
    class _RespOK:
        def raise_for_status(self): ...
        def json(self): return {"errcode": 200}

    monkeypatch.setattr("orders.payments.requests.post", lambda *a, **k: _RespOK())

    # если вдруг вызовут печать — урони тест
    def _should_not_be_called(*a, **k):
        raise AssertionError("send_receipt_request must not be called for loyalty_card")

    monkeypatch.setattr("orders.views.send_receipt_request", _should_not_be_called)

    program_factory(name="Loyalty-No-Receipt", price="180.00")
    p = Program.objects.first()
    tx = api_client.post(
        reverse("create-order"), {"program_id": p.id}, format="json"
    ).json()["transaction_id"]

    res = api_client.post(
        reverse("washorder-pay"),
        {"transaction_id": tx, "payment_type": "loyalty_card", "ucn": "123456"},
        format="json",
    )
    assert res.status_code == 200
    order = WashOrder.objects.get(transaction_id=tx)
    assert order.status == WashOrder.Status.PAYED
    assert not order.qr_code
