import ujson
from machine import Pin


class RelayManager:
    def __init__(self, config_path="relay/relay.json"):
        self.config_path = config_path
        self.config = self._load_config()
        self.pin_num = int(self.config.get("pin", 13))
        self.active_low = bool(self.config.get("active_low", True))
        self.initial_state = self.config.get("initial_state", "off")
        self.pin = Pin(self.pin_num, Pin.OUT)
        self._is_on = False
        self.set_state(self.initial_state == "on")

    def _load_config(self):
        try:
            with open(self.config_path) as f:
                return ujson.load(f)
        except Exception:
            return {
                "pin": 13,
                "active_low": True,
                "initial_state": "off",
            }

    def _write_output(self, enabled):
        if self.active_low:
            self.pin.value(0 if enabled else 1)
        else:
            self.pin.value(1 if enabled else 0)

    def set_state(self, enabled):
        self._is_on = bool(enabled)
        self._write_output(self._is_on)
        return self.status()

    def on(self):
        return self.set_state(True)

    def off(self):
        return self.set_state(False)

    def toggle(self):
        return self.set_state(not self._is_on)

    def is_on(self):
        return self._is_on

    def status(self):
        return {
            "ok": True,
            "pin": self.pin_num,
            "active_low": self.active_low,
            "is_on": self._is_on,
            "output": self.pin.value(),
        }