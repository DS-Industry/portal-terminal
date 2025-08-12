import json
import pytest
from orders.models import Program, WashOrder, TerminalStatus
import orders.ping_dscloud as pds


# --- helpers for capturing Session.get calls ---

class _DummyRespOK:
    def __init__(self, status_code=200, json_payload=None, text="{}"):
        self.status_code = status_code
        self._json = json_payload if json_payload is not None else {}
        self.text = text

    def raise_for_status(self):
        return None

    def json(self):
        return self._json


class _CapturingSession:
    """
    Заглушка requests.Session, чтобы поймать url/headers и вернуть управляемый ответ.
    """
    def __init__(self, resp: _DummyRespOK):
        self._resp = resp
        self.last_url = None
        self.last_headers = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    # именно GET — так реализовано в ping_dscloud
    def get(self, url, headers=None, timeout=None):
        self.last_url = url
        self.last_headers = headers or {}
        return self._resp


# --- tests ---

@pytest.mark.django_db
def test_dscloud_job_is_silent_while_processing(monkeypatch, program_factory, terminal_status):
    """
    Если есть заказ в PROCESSING — dscloud_job НЕ вызывает send_data_to_dscloud.
    """
    p = Program.objects.first() or program_factory()
    WashOrder.objects.create(
        program=p,
        program_price=p.price,
        transaction_id="tx-proc",
        status=WashOrder.Status.PROCESSING,
    )

    called = {"hits": 0}

    def _no_call():
        called["hits"] += 1
        return {}

    # важно патчить внутри модуля ping_dscloud
    monkeypatch.setattr(pds, "send_data_to_dscloud", _no_call)

    pds.dscloud_job()

    assert called["hits"] == 0


@pytest.mark.django_db
def test_dscloud_job_starts_payed_without_queue(monkeypatch, program_factory, terminal_status):
    """
    Когда мойка свободна и есть PAYED без очереди — dscloud_job должен дернуть start_car_wash.
    Упростим протокол: подтверждение суммы всегда True, данные от DScloud пустые.
    """
    p = Program.objects.first() or program_factory(price=200)
    o = WashOrder.objects.create(
        program=p,
        program_price=p.price,
        transaction_id="tx-payed-free",
        status=WashOrder.Status.PAYED,
        queue_position=None,
    )

    # не лезем в сеть и не ждём подтверждений
    monkeypatch.setattr(pds, "send_data_to_dscloud", lambda: {})  # mobile-сценарий не сработает
    monkeypatch.setattr(pds, "_confirm_sum", lambda expected, max_retries, label: True)
    monkeypatch.setattr(pds, "_set_ts_gvl_sum", lambda ts, v: None)

    started = {"tx": None}
    def _fake_start(order):
        started["tx"] = order.transaction_id

    monkeypatch.setattr(pds, "start_car_wash", _fake_start)

    pds.dscloud_job()

    assert started["tx"] == "tx-payed-free"


@pytest.mark.django_db
def test_send_prices_to_dscloud_builds_payload_and_returns_200(monkeypatch, terminal_status, program_factory):
    """
    send_prices_to_dscloud должен собрать JSON с ценами (int) и отправить GET.
    Проверяем, что вернулся 200 и заголовок 'data' соответствует ожидаемому JSON.
    """
    # две программы с id_service 18 и 19
    program_factory(id_service=18, price=100)
    program_factory(id_service=19, price=200)

    # подготовим «запоминающую» сессию
    dummy_resp = _DummyRespOK(status_code=200)
    cap = _CapturingSession(dummy_resp)

    # подменяем только Session внутри модуля ping_dscloud
    monkeypatch.setattr(pds, "requests", type("R", (), {
        "Session": lambda: cap
    }))

    status = pds.send_prices_to_dscloud()
    assert status == 200

    # проверим, что заголовок 'data' — валидный JSON с нужными значениями (int → строкой)
    sent = cap.last_headers.get("data")
    assert sent is not None
    data = json.loads(sent)
    # ожидаем строки по ключам id_service
    assert data.get("18") == "100"
    assert data.get("19") == "200"


@pytest.mark.django_db
def test_send_data_to_dscloud_headers_and_json(monkeypatch, terminal_status):
    """
    send_data_to_dscloud должен собрать строку data из GVL-полей и вернуть JSON, который отдал сервер.
    """
    # настроим поля терминала
    ts = TerminalStatus.objects.first()
    ts.gvl_sum = 0
    ts.gvl_err = 1
    ts.gvl_time = 2
    ts.gvl_cardnum = 3
    ts.gvl_cardsum = 4
    ts.gvl_source = 5
    ts.save()

    expected_json = {"GVLSum": "0"}

    cap = _CapturingSession(_DummyRespOK(status_code=200, json_payload=expected_json))
    monkeypatch.setattr(pds, "requests", type("R", (), {
        "Session": lambda: cap
    }))

    resp = pds.send_data_to_dscloud()
    assert resp == expected_json

    # проверяем состав строки headers['data']
    headers_data = cap.last_headers.get("data")
    assert headers_data is not None
    # порядок важен не критично, но строки должны содержать все пары ключ:значение
    assert "GVLSum:0" in headers_data
    assert "GVLErr:1" in headers_data
    assert "GVLTime:2" in headers_data
    assert "GVLCardNum:3" in headers_data
    assert "GVLCardSum:4" in headers_data
    assert "GVLSource:5" in headers_data
