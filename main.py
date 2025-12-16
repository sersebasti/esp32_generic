from core.logger import CircularLogger
from wifi_manager import WiFiManager
from config import LOG_PATH, LOG_MAX_BYTES, WIFI_JSON

log = CircularLogger(path=LOG_PATH, max_bytes=LOG_MAX_BYTES, echo=True)

if __name__ == "__main__":
    mgr = WiFiManager(log=log, wifi_json=WIFI_JSON)
    mgr.run()