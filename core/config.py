# core/config.py
# Configurazione centralizzata basata su default codificati.
# Modifica i valori qui per adeguare il comportamento dell'app.
_DEFAULTS = {
    "features": {
        "logger": True,
        "server": True,
        "wifi": True,
        "scope": True,
        "fs": False,
        "display": True,
        "power_sensors": False,
        "relay": False,
        "my_webrepl": False
    },
}

cfg = dict(_DEFAULTS)


def feature_enabled(name):
    try:
        feats = cfg.get("features", {})
        return bool(feats.get(name, False))
    except Exception:
        return False

# Feature startup order (used by core.feature_runner)
FEATURE_ORDER = (
    "logger",
    "my_webrepl",
    "server",
    "wifi",
    "scope",
    "fs",
    "display",
    "power_sensors",
    "relay",
)


