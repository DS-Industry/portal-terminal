import requests


class LedBoardManager:
    """
    Менеджер управления LED табло через HTTP сервер
    """

    BASE_URL = "http://host.docker.internal:5051"

    @classmethod
    def set_busy(cls):
        """Показать РОБОТ ЗАНЯТ"""
        return cls._post("/busy")

    @classmethod
    def set_free(cls):
        """Показать РОБОТ СВОБОДЕН"""
        return cls._post("/free")

    @classmethod
    def toggle_chain(cls):
        return cls._post("/toggle-chain")

    @classmethod
    def swap_rb(cls):
        return cls._post("/swap-rb")

    @classmethod
    def brighter(cls):
        return cls._post("/brighter")

    @classmethod
    def darker(cls):
        return cls._post("/darker")

    @classmethod
    def _post(cls, path):
        try:
            url = cls.BASE_URL + path
            response = requests.post(url, timeout=3)

            return {
                "success": response.status_code == 200,
                "status": response.status_code,
                "response": response.text
            }

        except Exception as e:
            print(f"[LED] Ошибка подключения к табло: {e}")
            return {
                "success": False,
                "error": str(e)
            }
