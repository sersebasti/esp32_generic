# core/config.py
# Configurazione centralizzata basata su default codificati.
# Modifica i valori qui per adeguare il comportamento dell'app.
_DEFAULTS = {
    "wifi_json": "core/wifi.json",
    "log_path": "log.txt",
    "log_max_bytes": 8 * 1024,
    "btn_pin": 32,
    "ftp_autostart": False,
    "ftp_port": 21,
    "ftp_user": "admin",
    "ftp_pass": "admin",
    "features": {
        "scope": True,
        "fs_api": True,
    },
}

cfg = dict(_DEFAULTS)


def feature_enabled(name):
    try:
        feats = cfg.get("features", {})
        return bool(feats.get(name, False))
    except Exception:
        return False

# Export constant-style aliases for convenience
WIFI_JSON = cfg.get("wifi_json", "core/wifi.json")
LOG_PATH = cfg.get("log_path", "log.txt")
LOG_MAX_BYTES = int(cfg.get("log_max_bytes", 8 * 1024))
BTN_PIN = int(cfg.get("btn_pin", 32))

FTP_AUTOSTART = bool(cfg.get("ftp_autostart", False))
FTP_PORT = int(cfg.get("ftp_port", 21))
FTP_USER = cfg.get("ftp_user") or None
FTP_PASS = cfg.get("ftp_pass") or None
