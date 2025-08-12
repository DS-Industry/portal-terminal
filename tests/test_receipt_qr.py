import pytest

from orders import receipt_qr
from orders.models import ReceiptServerConfig, Program, WashOrder


@pytest.mark.django_db
def test_send_receipt_request_success(monkeypatch, program_factory, terminal_status):
    """
    При успешном ответе от сервера чеков возвращается QR-код (строка).
    """
    p = Program.objects.first() or program_factory()
    order = WashOrder.objects.create(
        program=p, program_price=p.price, transaction_id="tx-r1",
        status=WashOrder.Status.PAYED,
    )
    ReceiptServerConfig.objects.create(ip_address="127.0.0.1:5000")

    class _RespOK:
        def raise_for_status(self): ...
        def json(self): return {"qr": "QR-SUCCESS"}

    # ВАЖНО: мок именно POST
    monkeypatch.setattr("orders.receipt_qr.requests.post", lambda *a, **k: _RespOK())

    qr = receipt_qr.send_receipt_request(order)
    assert qr == "QR-SUCCESS"
    

@pytest.mark.django_db
def test_send_receipt_request_network_error(monkeypatch, program_factory):
    """
    Ошибка сети → возвращается None.
    """
    p = Program.objects.first() or program_factory()
    order = WashOrder.objects.create(
        program=p, program_price=p.price, transaction_id="tx-r2",
        status=WashOrder.Status.PAYED,
    )
    ReceiptServerConfig.objects.create(ip_address="127.0.0.1:5000")

    def _raise_error(*a, **k):
        raise Exception("network fail")

    monkeypatch.setattr("orders.receipt_qr.requests.get", _raise_error)
    qr = receipt_qr.send_receipt_request(order)
    assert qr is None


@pytest.mark.django_db
def test_send_receipt_request_no_config_returns_none(program_factory):
    """
    Если в ReceiptServerConfig нет записей → возвращается None.
    """
    p = Program.objects.first() or program_factory()
    order = WashOrder.objects.create(
        program=p, program_price=p.price, transaction_id="tx-r3",
        status=WashOrder.Status.PAYED,
    )
    qr = receipt_qr.send_receipt_request(order)
    assert qr is None
