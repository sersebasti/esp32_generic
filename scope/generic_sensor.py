import machine
import time
import math

class GenericSensor:

    def _save_calibration(self):
        try:
            import os
            os.mkdir(self.cal_dir)
        except Exception:
            pass
        with open(self.cal_file, "w") as f:
            import ujson
            ujson.dump(self.cal, f)

    def _load_calibration(self):
        try:
            with open(self.cal_file) as f:
                import ujson
                return ujson.load(f)
        except Exception:
            return {}

    def _rms_with_baseline(self, arr, baseline):
        s = 0.0
        for v in arr:
            d = v - baseline
            s += d * d
        return math.sqrt(s / len(arr))

    def stats_counts(self, arr):
        n = len(arr)
        s = sum(arr)
        mean = s / n
        acc = 0.0
        for v in arr:
            dv = v - mean
            acc += dv * dv
        rms = math.sqrt(acc / n)
        return mean, rms

    def sample_counts(self, n=512, sample_rate_hz=4000, fast=False):
        import gc
        print(f"[DEBUG] sample_counts n={n}, sample_rate_hz={sample_rate_hz}, fast={fast}")
        print(f"[DEBUG] Memoria libera prima: {gc.mem_free()} allocata: {gc.mem_alloc()}")
        self._init_adc()
        n = max(32, min(int(n), 4096))
        sr = max(200, min(int(sample_rate_hz), 20000))
        dt_us = int(1_000_000 / sr)
        arr = []
        for i in range(n):
            arr.append(self._read_count())
            if i < 5:
                print(f"[DEBUG] sample_counts[{i}] = {arr[-1]}")
            if not fast:
                import time
                time.sleep_us(dt_us)
        print(f"[DEBUG] Memoria libera dopo: {gc.mem_free()} allocata: {gc.mem_alloc()}")
        return arr, sr

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
