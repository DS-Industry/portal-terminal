import requests


class OptiApiClient:
    def __init__(self, base_url: str, timeout: int = 5):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def post(self, path: str, *, data=None, json=None, headers=None):
        return requests.post(
            self.base_url + path,
            data=data,
            json=json,
            headers=headers,
            timeout=self.timeout,
        )

    def get(self, path: str, *, headers=None):
        return requests.get(
            self.base_url + path,
            headers=headers,
            timeout=self.timeout,
        )

    def delete(self, path: str, *, headers=None):
        return requests.delete(
            self.base_url + path,
            headers=headers,
            timeout=self.timeout,
        )