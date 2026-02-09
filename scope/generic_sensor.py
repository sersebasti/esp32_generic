import machine
import time
import math

class GenericSensor:

    def add_calibration_point(self, value, n=1600, sr=4000, fast=False, value_key="amps", rms_key="rms_counts", k_key="k_A_per_count"):
        arr, sr = self.sample_counts(n, sr, fast=fast)
        baseline = float(self.cal.get("baseline_mean", sum(arr)/len(arr)))
        rms = self._rms_with_baseline(arr, baseline)
        pt = {value_key: float(value), rms_key: round(rms, 2)}
        pts = self.cal.get("points", [])
        pts = pts if isinstance(pts, list) else []
        pts.append(pt)
        self.cal["points"] = pts
        k = self.fit_k(pts, value_key=value_key, rms_key=rms_key)
        self.cal[k_key] = round(k, 9)
        self._save_calibration()
        return pt, self.cal[k_key]

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

    def compare_baseline(self, n=1600, sr=4000, fast=False):
        arr, sr = self.sample_counts(n, sr, fast=fast)
        mean_now = sum(arr) / len(arr)
        baseline = self.cal.get("baseline_mean", None)
        diff = mean_now - baseline if baseline is not None else None
        return baseline, mean_now, diff

    def reset_calibration(self):
        try:
            import os
            try:
                os.stat(self.cal_file)
                os.remove(self.cal_file)
                print(f"[DEBUG] File {self.cal_file} cancellato.")
            except OSError:
                print(f"[DEBUG] File {self.cal_file} non esiste, nessuna cancellazione.")
        except Exception as e:
            print("[DEBUG] Errore cancellazione file:", e)
        self.cal = {}

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
