# lcd1602.py
# Driver base per display LCD1602 I2C (PCF8574)
# Adattabile per ESP32/ESP8266/MicroPython

from machine import I2C
import time


# Semplice driver LCD1602 I2C (PCF8574) per MicroPython
class LCD1602:
    def __init__(self, i2c: I2C, addr=0x27):
        self.i2c = i2c
        self.addr = addr
        self.backlight_state = 0x08  # backlight on
        self._init_lcd()

    def _write_byte(self, data):
        self.i2c.writeto(self.addr, bytes([data | self.backlight_state]))

    def _pulse_enable(self, data):
        self._write_byte(data | 0x04)
        time.sleep_us(1)
        self._write_byte(data & ~0x04)
        time.sleep_us(50)

    def _send(self, data, mode=0):
        high = mode | (data & 0xF0)
        low = mode | ((data << 4) & 0xF0)
        self._write4bits(high)
        self._write4bits(low)

    def _write4bits(self, data):
        self._write_byte(data)
        self._pulse_enable(data)

    def _command(self, cmd):
        self._send(cmd, 0)
        time.sleep_ms(2)

    def _init_lcd(self):
        time.sleep_ms(50)
        self._write4bits(0x30)
        time.sleep_ms(5)
        self._write4bits(0x30)
        time.sleep_us(150)
        self._write4bits(0x30)
        self._write4bits(0x20)  # 4 bit mode
        self._command(0x28)     # 2 line, 5x8 dots
        self._command(0x0C)     # display on, cursor off
        self._command(0x06)     # entry mode
        self.clear()

    def clear(self):
        self._command(0x01)
        time.sleep_ms(2)

    def write(self, row: int, col: int, text: str):
        if row not in (0, 1):
            return
        addr = 0x80 + (0x40 * row) + col
        self._command(addr)
        for c in text:
            self._send(ord(c), 0x01)

    def backlight(self, state: bool):
        self.backlight_state = 0x08 if state else 0x00
        self._write_byte(0)

# Esempio di utilizzo (da adattare nel main):
# from machine import I2C, Pin
# i2c = I2C(scl=Pin(22), sda=Pin(21))
# lcd = LCD1602(i2c)
# lcd.write(0, 0, "Hello!")
