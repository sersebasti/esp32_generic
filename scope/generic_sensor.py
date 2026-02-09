import machine
import time
import math

class GenericSensor:

    @staticmethod
    def fit_k(points, value_key="amps", rms_key="rms_counts"):
            sxy = 0.0
            sxx = 0.0
            for p in points:
                a = float(p[value_key])
                r = float(p[rms_key])
                sxy += a * r
                sxx += r * r
            return (sxy / sxx) if sxx > 0 else 0.0
        
    def __init__(self, pin, samples=100):
        self.pin = pin
        self.samples = samples
        self.adc = machine.ADC(machine.Pin(self.pin))
        self.adc.atten(machine.ADC.ATTN_11DB)

    def read_adc(self):
        return self.adc.read()

    def read_rms(self):
        vals = []
        for _ in range(self.samples):
            v = self.read_adc()
            vals.append(v)
            time.sleep_ms(2)
        mean_sq = sum([x**2 for x in vals]) / self.samples
        rms = math.sqrt(mean_sq)
        return rms
