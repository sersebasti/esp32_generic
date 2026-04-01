# wifi/feature.py

from wifi.wifi_manager import WiFiManager
from wifi.config import WIFI_JSON


def start(context=None):
    log = None
    if isinstance(context, dict):
        log = context.get("log")
    mgr = WiFiManager(log=log, wifi_json=WIFI_JSON)
    if isinstance(context, dict):
        context["wifi_manager"] = mgr
    return {"wifi_manager": mgr}
