# tests/test_api.py
import pytest
from django.urls import reverse
from orders.models.models import Program, WashOrder
from orders import payments as payments_module


@pytest.mark.django_db
def test_programs_list_via_router(api_client, program_factory):
    # создаём хотя бы одну программу
    program_factory(name="Базовая", price="100.00")
    url = reverse("program-list")
    res = api_client.get(url)
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list) and len(data) >= 1
    # структура соответствует ProgramSerializer
    assert {"id", "name", "price", "description", "duration"}.issubset(set(data[0].keys()))


@pytest.mark.django_db
def test_create_order_success(api_client, program_factory):
    # нужна программа для заказа
    program_factory(name="Стандарт", price="150.00")
    program = Program.objects.first()

    url = reverse("create-order")
    payload = {"program_id": program.id, "ucn": "123456"}
    res = api_client.post(url, payload, format="json")
    assert res.status_code == 201
    data = res.json()

    assert data["transaction_id"]
    assert data["status"] == WashOrder.Status.CREATED
    assert data["program_name"] == program.name
    assert float(data["program_price"]) == float(program.price)


@pytest.mark.django_db
def test_pay_mobile_app_returns_qr_and_sets_status(api_client, terminal_status, program_factory):
    program_factory(name="Мобайл", price="120.00")
    program = Program.objects.first()

    # создаём заказ
    create_url = reverse("create-order")
    create_res = api_client.post(create_url, {"program_id": program.id}, format="json")
    tx = create_res.json()["transaction_id"]

    # оплачиваем через мобильное приложение
    pay_url = reverse("washorder-pay")
    pay_res = api_client.post(
        pay_url,
        {"transaction_id": tx, "payment_type": "mobile_app"},
        format="json",
    )
    assert pay_res.status_code == 200
    body = pay_res.json()
    assert "qr_code" in body and isinstance(body["qr_code"], str)

    # статус заказа должен быть MOBILE_QR_REQUEST
    order = WashOrder.objects.get(transaction_id=tx)
    assert order.status == WashOrder.Status.MOBILE_QR_REQUEST


@pytest.mark.django_db
def test_pay_cash_sets_payed_and_sends_receipt(
    monkeypatch, api_client, terminal_status, receipt_config, program_factory
):
    # не спим в симуляции оплаты
    monkeypatch.setattr(payments_module, "cash_payment", lambda: None)

    # мок запроса QR на чек
    called = {"hits": 0}

    def _fake_receipt(order):
        called["hits"] += 1
        return "QR123"

    monkeypatch.setattr("orders.views.send_receipt_request", _fake_receipt)

    program_factory(name="Нал", price="200.00")
    program = Program.objects.first()

    # создаём заказ
    create_res = api_client.post(reverse("create-order"), {"program_id": program.id}, format="json")
    tx = create_res.json()["transaction_id"]

    # оплачиваем
    res = api_client.post(
        reverse("washorder-pay"),
        {"transaction_id": tx, "payment_type": "cash"},
        format="json",
    )
    assert res.status_code == 200

    order = WashOrder.objects.get(transaction_id=tx)
    assert order.status == WashOrder.Status.PAYED
    assert order.qr_code == "QR123"
    assert called["hits"] >= 1


@pytest.mark.django_db
def test_pay_bank_card_sets_payed_and_sends_receipt(
    monkeypatch, api_client, terminal_status, receipt_config, program_factory
):
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


@pytest.mark.django_db
def test_pay_loyalty_card_success_and_failure(
    monkeypatch, api_client, terminal_status, program_factory
):
    # создаём программу/заказ
    program_factory(name="Лояльность", price="300.00")
    program = Program.objects.first()
    tx = api_client.post(
        reverse("create-order"), {"program_id": program.id}, format="json"
    ).json()["transaction_id"]

    # --- успешный кейс: сервис лояльности отвечает errcode=200
    class _RespOK:
        status_code = 200

        def raise_for_status(self):  # имитируем requests.Response
            return None

        def json(self):
            return {"errcode": 200}

    monkeypatch.setattr("orders.payments.requests.post", lambda *a, **k: _RespOK())
    ok = api_client.post(
        reverse("washorder-pay"),
        {"transaction_id": tx, "payment_type": "loyalty_card", "ucn": "987654"},
        format="json",
    )
    assert ok.status_code == 200
    order = WashOrder.objects.get(transaction_id=tx)
    assert order.status == WashOrder.Status.PAYED  # статус меняет WashOrderPaymentView
    # создадим ещё один заказ для «ошибочного» сценариЯ
    tx2 = api_client.post(
        reverse("create-order"), {"program_id": program.id}, format="json"
    ).json()["transaction_id"]

    # --- неуспешный кейс: сервис вернул ошибку
    class _RespBad:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {"errcode": 500, "errmes": "Недостаточно средств"}

    monkeypatch.setattr("orders.payments.requests.post", lambda *a, **k: _RespBad())
    bad = api_client.post(
        reverse("washorder-pay"),
        {"transaction_id": tx2, "payment_type": "loyalty_card", "ucn": "111222"},
        format="json",
    )
    assert bad.status_code == 400
    order2 = WashOrder.objects.get(transaction_id=tx2)
    assert order2.status == WashOrder.Status.FAILED
