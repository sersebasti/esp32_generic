# wifi/config.py
# Configurazione WiFi separata dal core.

_DEFAULTS = {
    "wifi_json": "wifi/wifi.json",
    "ap_btn_pin": 16,
}

cfg = dict(_DEFAULTS)


def _load_wifi_json(path):
    try:
        import ujson
        with open(path) as f:
            return ujson.load(f) or {}
    except Exception:
        return {}


WIFI_JSON = cfg.get("wifi_json", "wifi/wifi.json")
_cfg_json = _load_wifi_json(WIFI_JSON)
AP_BTN_PIN = int(_cfg_json.get("ap_btn_pin", cfg.get("ap_btn_pin", 27)))
