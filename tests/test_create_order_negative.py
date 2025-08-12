import pytest
from django.urls import reverse

@pytest.mark.django_db
def test_create_order_unknown_program_returns_404(api_client):
    res = api_client.post(
        reverse("create-order"), {"program_id": 999999}, format="json"
    )
    assert res.status_code == 404
