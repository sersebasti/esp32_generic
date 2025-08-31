# main.py
from logger import RollingLogger
from wifi_manager import WiFiManager

log = RollingLogger(path="log.txt", max_bytes=8*1024, backups=1, echo=True)

if __name__ == "__main__":
    mgr = WiFiManager(log=log, wifi_json="wifi.json", check_interval=30, heartbeat=True)
    mgr.run()