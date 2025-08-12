import pytest
from django.urls import reverse
from orders.models import Program, WashOrder


@pytest.mark.django_db
def test_mobile_app_payment_without_terminal_status_returns_500(api_client, program_factory):
    """
    Если в БД нет TerminalStatus, мобильная оплата возвращает 500.
    Заказ к этому моменту уже переведён в waiting_payment.
    """
    program_factory(name="Мобайл", price="120.00")
    program = Program.objects.first()

    # создаём заказ
    create_res = api_client.post(
        reverse("create-order"), {"program_id": program.id}, format="json"
    )
    assert create_res.status_code == 201
    tx = create_res.json()["transaction_id"]

    # пробуем оплатить через мобильное приложение — без TerminalStatus
    pay_res = api_client.post(
        reverse("washorder-pay"),
        {"transaction_id": tx, "payment_type": "mobile_app"},
        format="json",
    )
    assert pay_res.status_code == 500
    body = pay_res.json()
    assert "error" in body and isinstance(body["error"], str)

    # статус уже waiting_payment (вьюха обновляет его до попытки выдать QR)
    order = WashOrder.objects.get(transaction_id=tx)
    assert order.status == WashOrder.Status.WAITING_PAYMENT
