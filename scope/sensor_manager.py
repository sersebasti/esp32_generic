# sensor_manager.py
# Gestione di più sensori di corrente tramite configurazione

from .current_sensor import CurrentSensor
import ujson, os

class CurrentSensorManager:
    def __init__(self, config_path="scope/sensors.json"):
        self.config_path = config_path
        self.sensors = {}
        self.config = self._load_config()
        self._init_sensors()

    def _load_config(self):
        try:
            with open(self.config_path) as f:
                return ujson.load(f)
        except Exception:
            # Default: un sensore su pin 34
            return {"sensors": [{"id": "s1", "adc_pin": 34}]}

    def _init_sensors(self):
        for s in self.config.get("sensors", []):
            sensor_id = s.get("id")
            adc_pin = s.get("adc_pin")
            if sensor_id and adc_pin is not None:
                self.sensors[sensor_id] = CurrentSensor(adc_pin)

    def get_sensor(self, sensor_id):
        return self.sensors.get(sensor_id)

    def list_sensors(self):
        return list(self.sensors.keys())

    def add_sensor(self, sensor_id, adc_pin):
        if sensor_id in self.sensors:
            return False
        self.sensors[sensor_id] = CurrentSensor(adc_pin)
        self.config["sensors"].append({"id": sensor_id, "adc_pin": adc_pin})
        self._save_config()
        return True

    def _save_config(self):
        try:
            os.mkdir("scope")
        except Exception:
            pass
        with open(self.config_path, "w") as f:
            ujson.dump(self.config, f)
