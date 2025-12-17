# status_api.py
import gc, network, ubinascii, time, ujson
from core.http_consts import _HTTP_200_JSON
from version import version

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
        with open("wifi.json") as f:
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
