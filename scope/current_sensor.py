# current_sensor.py
# Classe per la gestione di un singolo sensore di corrente su un pin ADC

import ujson, math, os
from machine import ADC, Pin

class CurrentSensor:
    def __init__(self, adc_pin, cal_dir="scope"):
        self.adc_pin = adc_pin
        self.cal_dir = cal_dir
        self.cal_file = f"{cal_dir}/calibrate_{adc_pin}.json"
        self.adc = None
        self.adc_width_bits = 12
        self.adc_atten_db = 11
        self._adc_max = (1 << self.adc_width_bits) - 1
        self.cal = self._load_calibration()

    def _init_adc(self):
        if self.adc:
            return
        a = ADC(Pin(self.adc_pin))
        if self.adc_atten_db == 0:
            a.atten(ADC.ATTN_0DB)
        elif self.adc_atten_db == 2:
            a.atten(ADC.ATTN_2_5DB)
        elif self.adc_atten_db == 6:
            a.atten(ADC.ATTN_6DB)
        else:
            a.atten(ADC.ATTN_11DB)
        if self.adc_width_bits == 9:
            a.width(ADC.WIDTH_9BIT)
        elif self.adc_width_bits == 10:
            a.width(ADC.WIDTH_10BIT)
        elif self.adc_width_bits == 11:
            a.width(ADC.WIDTH_11BIT)
        else:
            a.width(ADC.WIDTH_12BIT)
        self.adc = a

    def _read_count(self):
        self._init_adc()
        s = 0
        for _ in range(4):
            s += self.adc.read()
        return s >> 2

    def sample_counts(self, n=512, sample_rate_hz=4000):
        self._init_adc()
        n = max(32, min(int(n), 4096))
        sr = max(200, min(int(sample_rate_hz), 20000))
        dt_us = int(1_000_000 / sr)
        arr = []
        for _ in range(n):
            arr.append(self._read_count())
            time.sleep_us(dt_us)
        return arr, sr

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

    def _load_calibration(self):
        try:
            with open(self.cal_file) as f:
                return ujson.load(f)
        except Exception:
            return {}

    def _save_calibration(self):
        try:
            os.mkdir(self.cal_dir)
        except Exception:
            pass
        with open(self.cal_file, "w") as f:
            ujson.dump(self.cal, f)

    def calibrate_baseline(self, n=1600, sr=4000):
        arr, sr = self.sample_counts(n, sr)
        baseline = sum(arr) / len(arr)
        self.cal["baseline_mean"] = round(baseline, 2)
        self.cal["n0"] = len(arr)
        self.cal["sr0"] = sr
        if "points" not in self.cal:
            self.cal["points"] = []
        self._save_calibration()
        return self.cal["baseline_mean"]

    def add_calibration_point(self, amps, n=1600, sr=4000):
        arr, sr = self.sample_counts(n, sr)
        baseline = float(self.cal.get("baseline_mean", sum(arr)/len(arr)))
        rms = self._rms_with_baseline(arr, baseline)
        pt = {"amps": float(amps), "rms_counts": round(rms, 2)}
        pts = self.cal.get("points", [])
        pts = pts if isinstance(pts, list) else []
        pts.append(pt)
        self.cal["points"] = pts
        k = self._fit_k(pts)
        self.cal["k_A_per_count"] = round(k, 9)
        self._save_calibration()
        return pt, self.cal["k_A_per_count"]

    def _rms_with_baseline(self, arr, baseline):
        s = 0.0
        for v in arr:
            d = v - baseline
            s += d * d
        return math.sqrt(s / len(arr))

    def _fit_k(self, points):
        sxy = 0.0
        sxx = 0.0
        for p in points:
            a = float(p["amps"])
            r = float(p["rms_counts"])
            sxy += a * r
            sxx += r * r
        return (sxy / sxx) if sxx > 0 else 0.0

    def measure_amps(self, n=1600, sr=4000):
        arr, sr = self.sample_counts(n, sr)
        baseline = float(self.cal.get("baseline_mean", sum(arr)/len(arr)))
        rms = self._rms_with_baseline(arr, baseline)
        k = float(self.cal.get("k_A_per_count", 0.0))
        amps = k * rms
        return amps, rms, baseline, min(arr), max(arr)

    def compare_baseline(self, n=1600, sr=4000):
        arr, sr = self.sample_counts(n, sr)
        mean_now = sum(arr) / len(arr)
        baseline = self.cal.get("baseline_mean", None)
        diff = mean_now - baseline if baseline is not None else None
        return baseline, mean_now, diff
