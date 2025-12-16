# core/wifi_manager.py
# Shim module to expose WiFiManager under core package

try:
    from wifi_manager import WiFiManager as _WiFiManager
except Exception:
    _WiFiManager = None

class WiFiManager(_WiFiManager):
    pass
