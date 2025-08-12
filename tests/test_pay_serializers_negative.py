import pytest
from django.urls import reverse
from orders.models import Program

@pytest.mark.django_db
def test_pay_missing_transaction_id_returns_400(api_client, program_factory):
    program_factory(name="X", price="100.00")
    # без transaction_id
    res = api_client.post(
        reverse("washorder-pay"),
        {"payment_type": "cash"},
        format="json",
    )
    assert res.status_code in (400, 422)

@pytest.mark.django_db
def test_pay_invalid_payment_type_returns_400(api_client, program_factory):
    program_factory(name="X", price="100.00")
    # создадим валидный заказ
    p = Program.objects.first()
    tx = api_client.post(
        reverse("create-order"), {"program_id": p.id}, format="json"
    ).json()["transaction_id"]

    # невалидный тип оплаты
    res = api_client.post(
        reverse("washorder-pay"),
        {"transaction_id": tx, "payment_type": "crypto"},
        format="json",
    )
    assert res.status_code in (400, 422)

@pytest.mark.django_db
def test_pay_unknown_transaction_returns_404(api_client, program_factory):
    program_factory(name="X", price="100.00")
    # несуществующий transaction_id
    res = api_client.post(
        reverse("washorder-pay"),
        {"transaction_id": "no-such-tx", "payment_type": "cash"},
        format="json",
    )
    # у тебя может быть 404 или 400, в любом случае — ошибка
    assert res.status_code in (400, 404)
