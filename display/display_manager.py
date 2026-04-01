import ujson
from machine import I2C, Pin

from display.lcd1602 import LCD1602


def load_display_config(config_path="display/display.json"):
    try:
        with open(config_path) as f:
            return ujson.load(f)
    except Exception:
        return {
            "i2c_id": 0,
            "scl": 22,
            "sda": 21,
            "addr": 0x27,
        }


def create_lcd(config_path="display/display.json"):
    cfg = load_display_config(config_path)
    i2c_id = int(cfg.get("i2c_id", 0))
    scl_pin = int(cfg.get("scl", 22))
    sda_pin = int(cfg.get("sda", 21))
    addr = int(cfg.get("addr", 0x27))
    i2c = I2C(i2c_id, scl=Pin(scl_pin), sda=Pin(sda_pin))
    return LCD1602(i2c, addr=addr)