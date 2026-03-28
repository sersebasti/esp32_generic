# Classe di manager per sensori di potenza PZEM004T
from power_sensor.pzem004t import PZEM004T

class PowerSensorManager:
    def __init__(self, uart_id=1, tx=17, rx=16, baudrate=9600):
        self.sensor = PZEM004T(uart_id=uart_id, tx=tx, rx=rx, baudrate=baudrate)

    def read_all(self):
        return {
            'voltage': self.sensor.read_voltage(),
            'current': self.sensor.read_current(),
            'power': self.sensor.read_power(),
            'energy': self.sensor.read_energy(),
        }
