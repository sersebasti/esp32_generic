# test_pzem004t.py
# Esempio di utilizzo del modulo PZEM-004T su ESP32 (MicroPython)
from power_sensor.pzem004t import PZEM004T
import time

# Configura i pin UART secondo il tuo wiring
pzem = PZEM004T(uart_id=1, tx=17, rx=16, baudrate=9600)

while True:
    print("--- LETTURA PZEM-004T ---")
    result = pzem.read_all()
    print("Risultato read_all():", result)
    time.sleep(2)
