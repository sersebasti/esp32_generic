from logger import CircularLogger
from wifi_manager import WiFiManager

log = CircularLogger(path="log.txt", max_bytes=8*1024, echo=True)

if __name__ == "__main__":
    mgr = WiFiManager(log=log, wifi_json="wifi.json")   # ← GPIO collegato al pulsante (active-low)
    mgr.run()