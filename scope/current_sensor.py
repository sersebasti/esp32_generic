# current_sensor.py
# Classe per la gestione di un singolo sensore di corrente su un pin ADC

import ujson, math, os
from machine import ADC, Pin
from scope.generic_sensor import GenericSensor

class CurrentSensor(GenericSensor):
    def __init__(self, adc_pin, cal_dir="scope"):
        print(f"[DEBUG] CurrentSensor __init__ adc_pin={adc_pin}")
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






    def reset_calibration(self):
        # Cancella il file e azzera self.cal
            # Cancella il file di calibrazione se esiste, stampa errori
            try:
                try:
                    os.stat(self.cal_file)
                    os.remove(self.cal_file)
                    print("[DEBUG] File {} cancellato.".format(self.cal_file))
                except OSError:
                    print("[DEBUG] File {} non esiste, nessuna cancellazione.".format(self.cal_file))
            except Exception as e:
                print("[DEBUG] Errore cancellazione file:", e)
            self.cal = {}

    def calibrate_baseline(self, n=1600, sr=4000, fast=False):
        arr, sr = self.sample_counts(n, sr, fast=fast)
        baseline = sum(arr) / len(arr)
        self.cal["baseline_mean"] = round(baseline, 2)
        self.cal["n0"] = len(arr)
        self.cal["sr0"] = sr
        if "points" not in self.cal:
            self.cal["points"] = []
        self._save_calibration()
        return self.cal["baseline_mean"]

    def add_calibration_point(self, amps, n=1600, sr=4000, fast=False):
        arr, sr = self.sample_counts(n, sr, fast=fast)
        baseline = float(self.cal.get("baseline_mean", sum(arr)/len(arr)))
        rms = self._rms_with_baseline(arr, baseline)
        pt = {"amps": float(amps), "rms_counts": round(rms, 2)}
        pts = self.cal.get("points", [])
        pts = pts if isinstance(pts, list) else []
        pts.append(pt)
        self.cal["points"] = pts
        k = GenericSensor.fit_k(pts, value_key="amps", rms_key="rms_counts")
        self.cal["k_A_per_count"] = round(k, 9)
        self._save_calibration()
        return pt, self.cal["k_A_per_count"]


    # _fit_k is now in GenericSensor as fit_k (static method)

    def measure_amps(self, n=1600, sr=4000, fast=False):
        arr, sr = self.sample_counts(n, sr, fast=fast)
        baseline = float(self.cal.get("baseline_mean", sum(arr)/len(arr)))
        rms = self._rms_with_baseline(arr, baseline)
        k = float(self.cal.get("k_A_per_count", 0.0))
        amps = k * rms
        return amps, rms, baseline, min(arr), max(arr)

    def compare_baseline(self, n=1600, sr=4000, fast=False):
        arr, sr = self.sample_counts(n, sr, fast=fast)
        mean_now = sum(arr) / len(arr)
        baseline = self.cal.get("baseline_mean", None)
        diff = mean_now - baseline if baseline is not None else None
        return baseline, mean_now, diff
