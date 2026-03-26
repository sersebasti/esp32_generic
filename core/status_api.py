# status_api.py
import gc, network, ubinascii, time, ujson
from core.http_consts import _HTTP_200_JSON
from core.config import WIFI_JSON, feature_enabled
import sys

# LCD1602: inizializzazione globale se feature attiva
lcd = None
try:
    if feature_enabled("lcd_display"):
        from machine import I2C, Pin
        from display.lcd1602 import LCD1602
        i2c = I2C(0, scl=Pin(22), sda=Pin(21))
        lcd = LCD1602(i2c)
except Exception as e:
    print("[LCD] Errore inizializzazione LCD1602:", e)
try:
    sys.modules.pop('core.version', None)
except Exception:
    pass
import core.version
version = core.version.version
print("[DEBUG] Importato version dal file core/version.py:", version)

def _get_ip_sta():
    try:
        sta = network.WLAN(network.STA_IF)
        return sta.ifconfig()[0] if sta.isconnected() else None
    except Exception:
        return None

def _get_ssid():
    try:
        sta = network.WLAN(network.STA_IF)
        if sta.isconnected():
            try:
                return sta.config("essid")
            except Exception:
                return None
        return None
    except Exception:
        return None

def _rssi():
    try:
        sta = network.WLAN(network.STA_IF)
        if sta.isconnected():
            try:
                return sta.status("rssi")
            except Exception:
                return None
        return None
    except Exception:
        return None

def _mac_sta():
    try:
        sta = network.WLAN(network.STA_IF)
        mac = sta.config("mac")
        import ubinascii
        return ubinascii.hexlify(mac, ":").decode()
    except Exception:
        return None

def _uptime_s():
    try:
        return time.ticks_ms() // 1000
    except Exception:
        return None

def _read_meta():
    try:
        with open(WIFI_JSON) as f:
            cfg = ujson.load(f)
        return {"hostname": (cfg.get("hostname") or "esp32").strip()}
    except Exception:
        return {"hostname": "esp32"}

def handle(cl, method, path):
    # /health
    if method == "GET" and path.startswith("/health"):
        cl.send(_HTTP_200_JSON + b'{"ok":true}')
        return True

    # /status
    if method == "GET" and path.startswith("/status"):
        print("[DEBUG] handle /status: version attuale:", version)
        meta = _read_meta()
        payload = {
            "version": version,
            "name": meta["hostname"],
            "ip": _get_ip_sta(),
            "ssid": _get_ssid(),
            "rssi": _rssi(),
            "mac_sta": _mac_sta(),
            "uptime_s": _uptime_s(),
            "heap_free": gc.mem_free()
        }
        cl.send(_HTTP_200_JSON + ujson.dumps(payload).encode())
        return True

    return False
