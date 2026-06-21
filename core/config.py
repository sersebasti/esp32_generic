# core/config.py
# Configurazione centralizzata basata su default codificati.
# Modifica i valori qui per adeguare il comportamento dell'app.
_DEFAULTS = {
    "features": {
        "logger": False,
        "wifi": True,
        "server": True,
        "scope": False,
        "fs": True,
        "display": False,
        "power_sensors": False,
        "relay": False,
        "my_webrepl": False,
        "pzem_017": True          
    },
}

cfg = dict(_DEFAULTS)


def feature_enabled(name):
    try:
        feats = cfg.get("features", {})
        return bool(feats.get(name, False))
    except Exception:
        return False
