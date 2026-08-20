# wifi/config.py
# Configurazione WiFi separata dal core.

_DEFAULTS = {
    "wifi_json": "wifi/wifi.json",
    "ap_btn_pin": 16,
    "led_blue_pin": 2,
    "led_blue_low": False,
    "led_green_pin": 15,
    "led_green_low": False,
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
LED_BLUE_PIN = int(_cfg_json.get("led_blue_pin", cfg["led_blue_pin"]))
LED_BLUE_LOW = bool(_cfg_json.get("led_blue_low", cfg["led_blue_low"]))
LED_GREEN_PIN = int(_cfg_json.get("led_green_pin", cfg["led_green_pin"]))
LED_GREEN_LOW = bool(_cfg_json.get("led_green_low", cfg["led_green_low"]))
