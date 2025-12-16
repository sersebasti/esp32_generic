# config.py
# Parametri di configurazione centralizzati

WIFI_JSON = "wifi.json"
LOG_PATH = "log.txt"
LOG_MAX_BYTES = 8*1024
BTN_PIN = 32

# FTP auto-start configuration (runs after HTTP server starts)
FTP_AUTOSTART = False
FTP_PORT = 21
# Optional credentials; when set, FTP requires login
FTP_USER = "admin"  # e.g., "admin"
FTP_PASS = "admin"  # e.g., "secret"
# config.py
# Export constants from core.config (backed by config.json if present)
try:
	from core.config import cfg
except Exception:
	cfg = {
		"wifi_json": "wifi.json",
		"log_path": "log.txt",
		"log_max_bytes": 8 * 1024,
		"btn_pin": 32,
	}

WIFI_JSON = cfg.get("wifi_json", "wifi.json")
LOG_PATH = cfg.get("log_path", "log.txt")
LOG_MAX_BYTES = int(cfg.get("log_max_bytes", 8 * 1024))
BTN_PIN = int(cfg.get("btn_pin", 32))
