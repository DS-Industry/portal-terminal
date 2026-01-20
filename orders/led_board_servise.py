from orders.led_board import LedBoardManager


class LedBoardService:

    @staticmethod
    def set_busy(terminal):
        if not terminal.has_led_board():
            return None
        return LedBoardManager.set_busy()

    @staticmethod
    def set_free(terminal):
        if not terminal.has_led_board():
            return None
        return LedBoardManager.set_free()

    @staticmethod
    def toggle_chain(terminal):
        if not terminal.has_led_board():
            return None
        return LedBoardManager.toggle_chain()

    @staticmethod
    def swap_rb(terminal):
        if not terminal.has_led_board():
            return None
        return LedBoardManager.swap_rb()

    @staticmethod
    def brighter(terminal):
        if not terminal.has_led_board():
            return None
        return LedBoardManager.brighter()

    @staticmethod
    def darker(terminal):
        if not terminal.has_led_board():
            return None
        return LedBoardManager.darker()
