# logger/config.py
# Configurazione logger separata dal core.

_DEFAULTS = {
    "log_path": "log.txt",
    "log_max_bytes": 8 * 1024,
}

cfg = dict(_DEFAULTS)

LOG_PATH = cfg.get("log_path", "log.txt")
LOG_MAX_BYTES = int(cfg.get("log_max_bytes", 8 * 1024))
