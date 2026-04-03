import ujson
from machine import Pin


class Relay:
    def __init__(self, relay_conf):
        self.id = relay_conf.get("id")
        self.pin_num = int(relay_conf.get("pin", 13))
        self.active_low = bool(relay_conf.get("active_low", True))
        self.initial_state = relay_conf.get("initial_state", "off")
        self.pin = Pin(self.pin_num, Pin.OUT)
        self._is_on = False
        self.set_state(self.initial_state == "on")

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

    def status(self):
        return {"id": self.id, "is_on": self._is_on, "pin": self.pin_num}


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