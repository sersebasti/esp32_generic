# test_lcd1602.py
# Esempio minimo per testare LCD1602 I2C con ESP32 e MicroPython

from machine import I2C, Pin
from display.lcd1602 import LCD1602
import time

# Imposta i pin I2C standard per ESP32
# SDA = 21, SCL = 22

i2c = I2C(0, scl=Pin(22), sda=Pin(21))
lcd = LCD1602(i2c)

# Prova a scrivere un messaggio
lcd.write(0, 0, "Ciao ESP32!")
time.sleep(2)
lcd.write(1, 0, "LCD1602 OK")
