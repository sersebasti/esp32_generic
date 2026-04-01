# sensor_manager.py
# Gestione di più sensori di corrente tramite configurazione

from .current_sensor import CurrentSensor
from .voltage_sensor import VoltageSensor
import ujson, os

class CurrentSensorManager:
    def __init__(self, config_path="scope/sensors.json"):
        print("[DEBUG] CurrentSensorManager __init__")
        self.config_path = config_path
        self.sensors = {}
        self.config = self._load_config()
        self._sensor_defs = {}
        print(f"[DEBUG] Loaded config: {self.config}")
        for s in self.config.get("sensors", []):
            sensor_id = s.get("id")
            if sensor_id:
                self._sensor_defs[sensor_id] = s
        print("[DEBUG] Sensors defs loaded:", list(self._sensor_defs.keys()))

    def _load_config(self):
        try:
            with open(self.config_path) as f:
                return ujson.load(f)
        except Exception:
            # Default: un sensore su pin 34
            return {"sensors": [{"id": "s1", "adc_pin": 34}]}

    def _build_sensor(self, s):
        adc_pin = s.get("adc_pin")
        sensor_type = s.get("type", "current")
        if adc_pin is None:
            return None
        if sensor_type == "voltage":
            return VoltageSensor(adc_pin, s)
        return CurrentSensor(adc_pin)

    def get_sensor(self, sensor_id):
        if sensor_id in self.sensors:
            return self.sensors.get(sensor_id)
        s = self._sensor_defs.get(sensor_id)
        if not s:
            return None
        sensor = self._build_sensor(s)
        if sensor is not None:
            self.sensors[sensor_id] = sensor
        return sensor

    def list_sensors(self):
        return list(self._sensor_defs.keys())

    def add_sensor(self, sensor_id, adc_pin, sensor_type="current"):
        if sensor_id in self._sensor_defs:
            return False
        new_def = {"id": sensor_id, "adc_pin": adc_pin, "type": sensor_type}
        if not isinstance(self.config.get("sensors"), list):
            self.config["sensors"] = []
        self.config["sensors"].append(new_def)
        self._sensor_defs[sensor_id] = new_def
        sensor = self._build_sensor(new_def)
        if sensor is not None:
            self.sensors[sensor_id] = sensor
        self._save_config()
        return True

    def _save_config(self):
        try:
            os.mkdir("scope")
        except Exception:
            pass
        with open(self.config_path, "w") as f:
            ujson.dump(self.config, f)
