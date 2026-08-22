import ujson
from machine import I2C, Pin

from display.lcd1602 import LCD1602
from display.sh1106_min import SH1106DisplayAdapter
from display.ssd1306_min import SSD1306DisplayAdapter


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
    i2c_freq = int(cfg.get("freq", 100000))
    addr = int(cfg.get("addr", 0x27))
    driver = str(cfg.get("driver", "auto")).lower()
    oled_width = int(cfg.get("width", 128))
    oled_height = int(cfg.get("height", 64))
    col_offset = int(cfg.get("col_offset", 2))
    i2c = I2C(i2c_id, scl=Pin(scl_pin), sda=Pin(sda_pin), freq=i2c_freq)

    if driver == "sh1106":
        return SH1106DisplayAdapter(i2c, addr=addr, width=oled_width, height=oled_height, col_offset=col_offset)

    # Auto: 0x3C/0x3D sono tipici di OLED SSD1306.
    if driver == "ssd1306" or (driver == "auto" and addr in (0x3C, 0x3D, 60, 61)):
        return SSD1306DisplayAdapter(i2c, addr=addr, width=oled_width, height=oled_height)

    return LCD1602(i2c, addr=addr)