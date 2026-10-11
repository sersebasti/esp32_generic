# power_sensors_api.py
# Endpoint HTTP semplice per leggere i dati da tutti i sensori di potenza configurati

import ujson, os
import time
from machine import UART
from core.http_consts import _HTTP_200_JSON, _HTTP_200_JSON_CORS
try:
    import ustruct as struct
except Exception:
    import struct

from power_sensors.pzem004t import PZEM004T

# Carica configurazione sensori
with open('power_sensors/power_sensors.json') as f:
    sensors_config = ujson.load(f)

# Create one UART per hardware port and share it among sensors on that bus.
sensors = {}
uart_buses = {}
uart_settings = {}
uart_addresses = {}
uart_sensor_counts = {}
for cfg in sensors_config:
    sensor_id = cfg['id']
    uart_id = cfg.get('uart_id', 1)
    tx = cfg.get('tx', 17)
    rx = cfg.get('rx', 16)
    baudrate = cfg.get('baudrate', 9600)
    slave_addr = cfg.get('slave_addr', 0xF8)
    settings = (tx, rx, baudrate)

    if uart_id in uart_settings and uart_settings[uart_id] != settings:
        raise ValueError("Sensors sharing UART{} must use the same TX, RX and baudrate".format(uart_id))
    if uart_id not in uart_buses:
        uart_buses[uart_id] = UART(uart_id, baudrate=baudrate, tx=tx, rx=rx, timeout=100)
        uart_settings[uart_id] = settings
        uart_addresses[uart_id] = set()
        uart_sensor_counts[uart_id] = 0
        time.sleep(1)
    if not 1 <= slave_addr <= 0xF8:
        raise ValueError("Invalid slave_addr for sensor {}".format(sensor_id))
    if slave_addr in uart_addresses[uart_id]:
        raise ValueError("Duplicate slave_addr {} on UART{}".format(slave_addr, uart_id))
    uart_addresses[uart_id].add(slave_addr)
    uart_sensor_counts[uart_id] += 1

    sensors[cfg['id']] = PZEM004T(
        uart_id=uart_id,
        tx=tx,
        rx=rx,
        baudrate=baudrate,
        slave_addr=slave_addr,
        uart=uart_buses[uart_id]
    )

for uart_id, sensor_count in uart_sensor_counts.items():
    if sensor_count > 1 and 0xF8 in uart_addresses[uart_id]:
        raise ValueError("UART{} multi-sensor bus requires slave_addr 1..247 for every sensor".format(uart_id))

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
