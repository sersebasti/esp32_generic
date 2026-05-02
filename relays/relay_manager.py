import ujson
import time
from machine import Pin


class Relay:
    def __init__(self, relay_conf):
        self.id = relay_conf.get("id")
        self.pin_num = int(relay_conf.get("pin", 13))
        self.active_low = bool(relay_conf.get("active_low", True))
        self.initial_state = relay_conf.get("initial_state", "off")
        self.pin = Pin(self.pin_num, Pin.OUT)
        self.feedback_pin_num = relay_conf.get("feedback_pin")
        self.feedback_invert = bool(relay_conf.get("feedback_invert", False))
        self.feedback_settle_ms = int(relay_conf.get("feedback_settle_ms", 30))
        self.feedback_samples = int(relay_conf.get("feedback_samples", 3))
        self.feedback_pin = None
        try:
            if self.feedback_pin_num is not None:
                self.feedback_pin = Pin(int(self.feedback_pin_num), Pin.IN, Pin.PULL_UP)
        except Exception:
            self.feedback_pin = None
        self._is_on = False
        self._last_real_state = None
        self.set_state(self.initial_state == "on")

    def _write_output(self, enabled):
        if self.active_low:
            self.pin.value(0 if enabled else 1)
        else:
            self.pin.value(1 if enabled else 0)

    def set_state(self, enabled):
        enabled = bool(enabled)
        changed = enabled != self._is_on
        self._is_on = enabled
        if changed:
            self._write_output(self._is_on)
        if changed and self.feedback_pin is not None and self.feedback_settle_ms > 0:
            time.sleep_ms(self.feedback_settle_ms)
        return self.status()

    def on(self):
        return self.set_state(True)

    def off(self):
        return self.set_state(False)

    def toggle(self):
        return self.set_state(not self._is_on)

    def _read_feedback_once(self):
        if self.feedback_pin is None:
            return None
        high_reads = 0
        samples = self.feedback_samples if self.feedback_samples > 0 else 1
        for index in range(samples):
            high_reads += 1 if self.feedback_pin.value() else 0
            if index + 1 < samples:
                time.sleep_ms(2)
        value = high_reads >= ((samples // 2) + 1)
        if self.feedback_invert:
            value = not value
        return value

    def real_state(self):
        if self.feedback_pin is not None:
            try:
                first_value = self._read_feedback_once()
                second_value = self._read_feedback_once()
                if first_value == second_value:
                    self._last_real_state = first_value
                    return first_value
                if self._last_real_state is not None:
                    return self._last_real_state
                self._last_real_state = second_value
                return second_value
            except Exception:
                return None
        return None

    def status(self):
        return {
            "id": self.id,
            "is_on": self._is_on,
            "pin": self.pin_num,
            "feedback_pin": self.feedback_pin_num,
            "feedback_invert": self.feedback_invert,
            "real_state": self.real_state(),
        }


class RelayManager:
    def __init__(self, config_path="relays/relays.json"):
        self.config_path = config_path
        self._relay_defs = self._load_config()
        self._relays = {}

    def _load_config(self):
        try:
            with open(self.config_path) as f:
                data = ujson.load(f)
                return {r["id"]: r for r in data.get("relays", []) if "id" in r}
        except Exception:
            return {}

    def get(self, relay_id):
        if relay_id in self._relays:
            return self._relays[relay_id]
        conf = self._relay_defs.get(relay_id)
        if conf:
            relay = Relay(conf)
            self._relays[relay_id] = relay
            return relay
        return None

    def status(self, relay_id=None):
        if relay_id:
            relay = self.get(relay_id)
            return relay.status() if relay else {"error": "not found"}
        return [self.get(rid).status() for rid in self._relay_defs]

    def on(self, relay_id):
        relay = self.get(relay_id)
        return relay.on() if relay else {"error": "not found"}

    def off(self, relay_id):
        relay = self.get(relay_id)
        return relay.off() if relay else {"error": "not found"}

    def toggle(self, relay_id):
        relay = self.get(relay_id)
        return relay.toggle() if relay else {"error": "not found"}