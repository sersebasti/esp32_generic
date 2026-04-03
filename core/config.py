# core/config.py
# Configurazione centralizzata basata su default codificati.
# Modifica i valori qui per adeguare il comportamento dell'app.
_DEFAULTS = {
    "features": {
        "logger": False,
        "wifi": True,
        "server": True,
        "scope": True,
        "fs": True,
        "display": False,
        "power_sensors": True,
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

# FEATURE_ORDER = (
#     "logger",
#     "wifi",
#     "server",
#     "my_webrepl",
#     "scope",
#     "fs",
#     "display",
#     "power_sensors",
#     "relay",
# )


