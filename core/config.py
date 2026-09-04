# core/config.py
# Configurazione centralizzata basata su default codificati.
# Modifica i valori qui per adeguare il comportamento dell'app.
_DEFAULTS = {
    "mdns_hostname": "controllo-relay",
    "mdns_http_port": 80,
    "features": {
        "logger": False,
        "wifi": True,
        "server": True,
        "mdns": True,
        "scope": False,
        "fs": True,
        "display": False,
        "power_sensors": False,
        "relay": False,
        "my_webrepl": False,
        "pzem_017": False
    },
}

cfg = dict(_DEFAULTS)
MDNS_HOSTNAME = cfg["mdns_hostname"]
MDNS_HTTP_PORT = cfg["mdns_http_port"]


def feature_enabled(name):
    try:
        feats = cfg.get("features", {})
        return bool(feats.get(name, False))
    except Exception:
        return False
