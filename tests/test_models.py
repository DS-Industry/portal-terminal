import uuid
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from orders.models import (
    Program,
    TerminalStatus,
    WashOrder,
    WashSettings,
    ReceiptServerConfig,
)


@pytest.mark.django_db
def test_program_str():
    p = Program.objects.create(
        name="Стандарт",
        price=Decimal("150.00"),
        description="Базовая программа",
        duration=12,
        id_service=101,
    )
    assert str(p) == "Стандарт — 12 мин"


@pytest.mark.django_db
def test_terminal_status_singleton_and_str():
    first = TerminalStatus.objects.create(
        identifier=9999,
        car_wash_identifier=1,
        name="Робот #1",
        mobile_app_qr_code="STATIC-QR",
        bay_number=1,
        gvl_sum=0,
        gvl_err=0,
        gvl_time=0,
        gvl_cardnum=0,
        gvl_cardsum=0,
        gvl_source=0,
    )
    assert str(first) == "Робот #1 (ID: 9999)"

    # вторая запись должна падать из-за clean() → ValidationError
    with pytest.raises(ValidationError):
        TerminalStatus.objects.create(
            identifier=10000,
            car_wash_identifier=2,
            name="Робот #2",
            bay_number=2,
        )


@pytest.mark.django_db
def test_washsettings_singleton_and_str():
    ws = WashSettings.objects.create(delay_between_washes=7)
    assert str(ws) == "Глобальные настройки мойки"

    with pytest.raises(ValidationError):
        WashSettings.objects.create(delay_between_washes=10)


@pytest.mark.django_db
def test_receipt_server_config_singleton_and_str():
    r = ReceiptServerConfig.objects.create(ip_address="127.0.0.1:5000")
    assert str(r) == "Receipt Server: 127.0.0.1:5000"

    with pytest.raises(ValidationError):
        ReceiptServerConfig.objects.create(ip_address="10.0.0.2:6000")


@pytest.mark.django_db
def test_washorder_str_default_and_mobile_qr_flag():
    prog = Program.objects.create(
        name="Премиум",
        price=Decimal("300.00"),
        description="Глубокая мойка",
        duration=20,
        id_service=202,
    )
    tx = str(uuid.uuid4())
    order = WashOrder.objects.create(
        program=prog,
        program_price=prog.price,
        transaction_id=tx,
        # status по умолчанию 'created'
    )
    assert str(order) == f"Заказ {tx} - {prog.name}"

    # При статусе MOBILE_QR_REQUEST должен появляться специальный суффикс
    order.status = WashOrder.Status.MOBILE_QR_REQUEST
    order.save()
    assert str(order) == f"Заказ {tx} (Старое Моб. приложение) - {prog.name}"
