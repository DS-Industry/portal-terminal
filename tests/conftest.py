# tests/conftest.py
import uuid
import pytest
from model_bakery import baker
from rest_framework.test import APIClient


@pytest.fixture(autouse=True)
def _disable_apscheduler_background(monkeypatch):
    """
    Не даём поднимать фоновые шедулеры/потоки в тестах.
    """
    try:
        import orders.start_carwash as sc
        monkeypatch.setattr(sc, "_scheduler", None, raising=False)
    except Exception:
        pass
    yield


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def program_factory(db):
    def _make(
        name="Стандарт",
        price=100,
        duration=5,
        description="",
        id_service=1,
    ):
        return baker.make(
            "orders.Program",
            name=name,
            price=price,
            duration=duration,
            description=description,
            id_service=id_service,
        )
    return _make


@pytest.fixture
def wash_settings(db):
    # глобальная задержка между мойками (делаем минимальной)
    return baker.make("orders.WashSettings", delay_between_washes=1)


@pytest.fixture
def receipt_config(db):
    # адрес API печати чеков (мокаем далее requests.post)
    return baker.make("orders.ReceiptServerConfig", ip_address="127.0.0.1:5000")


@pytest.fixture
def terminal_status(db):
    """
    Единственная запись состояния терминала (синглтон).
    Важно: car_wash_identifier — целое число.
    """
    return baker.make(
        "orders.TerminalStatus",
        identifier=9999,
        car_wash_identifier=1,
        name="Robot #1",
        bay_number=1,
        mobile_app_qr_code="STATIC-QR-STRING",
        gvl_cardnum=0, gvl_cardsum=0, gvl_sum=0, gvl_err=0, gvl_time=0, gvl_source=0,
    )


@pytest.fixture
def make_processing_order(db, program_factory):
    """
    Создаёт заказ в статусе PROCESSING — имитируем «мойка занята».
    """
    def _make():
        prog = program_factory(price=250, id_service=250)
        return baker.make(
            "orders.WashOrder",
            program=prog,
            program_price=prog.price,
            status="processing",
            transaction_id=str(uuid.uuid4()),
            payment_type=None,
        )
    return _make


@pytest.fixture
def mock_send_receipt(monkeypatch):
    """
    Мок печати чека: send_receipt_request увидит успешный ответ и вернёт QR-строку.
    """
    class DummyResp:
        def raise_for_status(self): ...
        def json(self): return {"qr": "QR-CODE-STRING"}

    def fake_post(*args, **kwargs):
        return DummyResp()

    import orders.receipt_qr as rq
    # подменим только модуль requests внутри receipt_qr
    monkeypatch.setattr(
        rq, "requests", type("R", (), {"post": staticmethod(fake_post)})
    )
    return True


@pytest.fixture
def mock_loyalty_ok(monkeypatch):
    """
    Успешный сценарий списания по карте лояльности.
    """
    class DummyResp:
        def raise_for_status(self): ...
        def json(self): return {"errcode": 200, "errmes": ""}

    def fake_post(*args, **kwargs):
        return DummyResp()

    import orders.payments as pay
    monkeypatch.setattr(
        pay, "requests", type("R", (), {"post": staticmethod(fake_post)})
    )
    # гарантируем наличие хост/порта в модуле payments
    monkeypatch.setattr(pay, "CARWASH_IP", "127.0.0.1")
    monkeypatch.setattr(pay, "CARWASH_PORT", "8000")
    return True


@pytest.fixture
def mock_loyalty_fail(monkeypatch):
    """
    Неуспешный сценарий списания по карте лояльности.
    """
    class DummyResp:
        def raise_for_status(self): ...
        def json(self): return {"errcode": 500, "errmes": "Недостаточно средств"}

    def fake_post(*args, **kwargs):
        return DummyResp()

    import orders.payments as pay
    monkeypatch.setattr(
        pay, "requests", type("R", (), {"post": staticmethod(fake_post)})
    )
    monkeypatch.setattr(pay, "CARWASH_IP", "127.0.0.1")
    monkeypatch.setattr(pay, "CARWASH_PORT", "8000")
    return True


@pytest.fixture
def mock_session_get(monkeypatch):
    """
    Счётчик вызовов GET к DScloud (используется в ping_dscloud).
    """
    counter = {"count": 0, "args": [], "kwargs": []}

    def fake_get(*args, **kwargs):
        counter["count"] += 1
        counter["args"].append(args)
        counter["kwargs"].append(kwargs)

        class DummyResp:
            status_code = 200
            text = "{}"
            def raise_for_status(self): ...
            def json(self): return {"GVLSum": "0"}

        return DummyResp()

    try:
        import orders.ping_dscloud as pds
        monkeypatch.setattr(
            pds, "requests", type("R", (), {"get": staticmethod(fake_get)})
        )
    except Exception:
        # если модуль не используется в конкретном тесте — просто вернём счётчик
        pass
    return counter
