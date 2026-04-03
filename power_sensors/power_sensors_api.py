# power_sensors_api.py
# Endpoint HTTP semplice per leggere i dati da tutti i sensori di potenza configurati

import ujson, os
from core.http_consts import _HTTP_200_JSON, _HTTP_200_JSON_CORS
try:
    import ustruct as struct
except Exception:
    import struct

from power_sensors.pzem004t import PZEM004T

# Carica configurazione sensori
with open('power_sensors/power_sensors.json') as f:
    sensors_config = ujson.load(f)

# Istanzia tutti i sensori
sensors = {}
for cfg in sensors_config:
    sensors[cfg['id']] = PZEM004T(
        uart_id=cfg.get('uart_id', 1),
        tx=cfg.get('tx', 17),
        rx=cfg.get('rx', 16),
        baudrate=cfg.get('baudrate', 9600)
    )

def get_all_power_sensors():
    result = {}
    for sid, sensor in sensors.items():
        result[sid] = sensor.read_all()
    return result

def get_power_sensor(sensor_id):
    sensor = sensors.get(sensor_id)
    if sensor:
        return sensor.read_all()
    return None

def handle_power_sensor(cl, method, path, req=None, _read_post_json=None):
    import ujson
    try:
        if method == "GET" and (path.split("?", 1)[0] == "/power_sensor"):
            sensor_id = "pz1"
            if "?" in path:
                q = path.split("?", 1)[1]
                for p in q.split("&"):
                    if "=" in p:
                        k, v = p.split("=", 1)
                        if k == "id":
                            sensor_id = v
            try:
                data = get_power_sensor(sensor_id)
            except Exception as e:
                cl.send(_HTTP_200_JSON + ujson.dumps({"ok": False, "err": "sensor_exception", "msg": str(e)}).encode())
                return True
            if data:
                cl.send(_HTTP_200_JSON + ujson.dumps({"ok": True, "data": data}).encode())
            else:
                cl.send(_HTTP_200_JSON + ujson.dumps({"ok": False, "err": "sensor_not_found"}).encode())
            return True
        return False
    except Exception as e:
        cl.send(_HTTP_200_JSON + ujson.dumps({"ok": False, "err": "server_exception", "msg": str(e)}).encode())
        return True

# Esempio di endpoint HTTP con MicroPython (picoweb, uasyncio, ecc.)
# Qui solo funzione, da integrare in un server HTTP secondo il framework usato
