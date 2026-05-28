from .client import OptiApiClient
from .exceptions import OptiAuthError, OptiRequestError
from .config import OptiConfig


class OptiService:
    def __init__(self):
        self.client = OptiApiClient(OptiConfig.BASE_URL)
        self.login = OptiConfig.LOGIN
        self.password = OptiConfig.PASSWORD
        self.poi_id = OptiConfig.POI_ID
        self.service_id = OptiConfig.SERVICE_ID
        self.access_token = None

    # ---------- AUTH ----------

    def authorize(self):
        response = self.client.post(
            "/external/v1/auth",
            data={
                "login": self.login,
                "password": self.password,
            },
        )

        if response.status_code != 200:
            raise OptiAuthError(f"Auth failed: {response.text}")

        data = response.json()
        self.access_token = data["access_token"]
        return data

    def _auth_headers(self):
        if not self.access_token:
            self.authorize()

        return {
            "Authorization": f"Bearer {self.access_token}"
        }

    # ---------- ORDERS ----------

    def create_order(self, items: list[dict]):
        response = self.client.post(
            "/external/v1/orders",
            json={
                "poi_id": self.poi_id,
                "items": items,
            },
            headers=self._auth_headers(),
        )

        if response.status_code != 200:
            raise OptiRequestError(response.text)

        return response.json()

    def get_order(self, order_id: str):
        response = self.client.get(
            f"/external/v1/orders/{order_id}",
            headers=self._auth_headers(),
        )

        if response.status_code != 200:
            raise OptiRequestError(response.text)

        return response.json()

    def get_order_qr(self, order_id: str):
        response = self.client.get(
            f"/external/v1/orders/{order_id}/qr",
            headers=self._auth_headers(),
        )

        if response.status_code != 200:
            raise OptiRequestError(response.text)

        return response.json()

    def cancel_order(self, order_id: str):
        response = self.client.delete(
            f"/external/v1/orders/{order_id}",
            headers=self._auth_headers(),
        )

        if response.status_code != 200:
            raise OptiRequestError(response.text)

        return response.json()
