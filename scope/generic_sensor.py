import machine
import time
import math

class GenericSensor:

    @staticmethod
    def _cal_float(sensor, key, default_val):
        try:
            return float(sensor.cal.get(key, default_val))
        except Exception:
            return float(default_val)

    @staticmethod
    def measure_instant_power_pair(voltage_sensor, current_sensor, n=1600, sample_rate_hz=4000, fast=False, phase_shift=None):
        # Inizializza i due ADC (tensione e corrente) una sola volta.
        voltage_sensor._init_adc()
        current_sensor._init_adc()

        # Normalizza i parametri di acquisizione in un range sicuro.
        n = max(32, min(int(n), 4096))
        
        sr = max(200, min(int(sample_rate_hz), 20000))
        # Periodo teorico tra campioni (microsecondi).
        dt_us = int(1_000_000 / sr)

        # ensure mains_freq is defined and initialize phase shift variable
        try:
            mains_freq = float(voltage_sensor.cal.get("mains_freq", 50.0))
        except Exception:
            mains_freq = 50.0
        sh = 0

        v_baseline = GenericSensor._cal_float(voltage_sensor, "baseline_mean", 2048.0)
        i_baseline = GenericSensor._cal_float(current_sensor, "baseline_mean", 2048.0)
        k_v = GenericSensor._cal_float(voltage_sensor, "k_V_per_count", 0.0)
        k_i = GenericSensor._cal_float(current_sensor, "k_A_per_count", 0.0)
        # TODO: in futuro validare calibrazione (es. k_v/k_i != 0) e bloccare la misura con errore esplicito se non pronta.

        
        # Determina lo shift: normalizzazione basata su sample_rate e mains_freq, preservando il segno
        if phase_shift is not None:
            s_in = int(phase_shift)

            samples_per_cycle = max(1, int(round(float(sr) / float(mains_freq))))
            max_shift = max(1, samples_per_cycle // 2)

            # preserva il segno dell'input: riduce il valore modulo samples_per_cycle mantenendo la direzione
            if s_in >= 0:
                s_mod = s_in % samples_per_cycle
                if s_mod > max_shift:
                    s_mod -= samples_per_cycle
                sh = int(s_mod)
            else:
                s_mod = (-s_in) % samples_per_cycle
                if s_mod > max_shift:
                    s_mod -= samples_per_cycle
                sh = -int(s_mod)

        
        # Accumulatori per RMS e potenza attiva istantanea.
        sum_v2 = 0.0
        sum_i2 = 0.0
        sum_p = 0.0

        # Limiti osservati per diagnostica clipping/saturazione ADC.
        v_min = 4095
        v_max = 0
        i_min = 4095
        i_max = 0

        # Acquisizione e calcolo in streaming: non teniamo tutti i campioni in memoria
        if sh == 0:
            # comportamento classico: n coppie v/i
            for _ in range(n):
                v_count = voltage_sensor._read_count()
                i_count = current_sensor._read_count()

                if v_count < v_min:
                    v_min = v_count
                if v_count > v_max:
                    v_max = v_count
                if i_count < i_min:
                    i_min = i_count
                if i_count > i_max:
                    i_max = i_count

                # Rimuove offset e converte in Volt/Ampere istantanei.
                v_inst = (v_count - v_baseline) * k_v
                i_inst = (i_count - i_baseline) * k_i

                # Somme per: Vrms, Irms e P attiva media.
                sum_v2 += v_inst * v_inst
                sum_i2 += i_inst * i_inst
                sum_p += v_inst * i_inst

                if not fast:
                    time.sleep_us(dt_us)
        else:
            # versione con shift: usiamo un piccolo buffer di size abs_sh per allineare i campioni
            abs_sh = abs(sh)
            n_eff = n - abs_sh
            if n_eff <= 0:
                raise ValueError("Phase shift magnitude >= n: increase n or reduce phase_shift")

            if sh > 0:
                # la tensione è in anticipo: leggiamo e memorizziamo i primi 'abs_sh' campioni di tensione
                vbuf = []
                for _ in range(abs_sh):
                    vbuf.append(voltage_sensor._read_count())
                    if not fast:
                        time.sleep_us(dt_us)
                # poi leggiamo n_eff volte: per ciascuna lettura prendiamo il nuovo campione di tensione,
                # lo applichiamo con il campione di corrente letto subito dopo
                for _ in range(n_eff):
                    v_new = voltage_sensor._read_count()
                    vbuf.append(v_new)
                    i_count = current_sensor._read_count()

                    # il campione di tensione allineato è l'ultimo inserito (v_new)
                    v_count = vbuf.pop()

                    if v_count < v_min:
                        v_min = v_count
                    if v_count > v_max:
                        v_max = v_count
                    if i_count < i_min:
                        i_min = i_count
                    if i_count > i_max:
                        i_max = i_count

                    v_inst = (v_count - v_baseline) * k_v
                    i_inst = (i_count - i_baseline) * k_i

                    sum_v2 += v_inst * v_inst
                    sum_i2 += i_inst * i_inst
                    sum_p += v_inst * i_inst

                    if not fast:
                        time.sleep_us(dt_us)
            else:
                # sh < 0 -> la corrente è in anticipo: memorizziamo i primi 'abs_sh' campioni di corrente
                ibuf = []
                for _ in range(abs_sh):
                    ibuf.append(current_sensor._read_count())
                    if not fast:
                        time.sleep_us(dt_us)
                for _ in range(n_eff):
                    i_new = current_sensor._read_count()
                    ibuf.append(i_new)
                    v_count = voltage_sensor._read_count()

                    i_count = ibuf.pop()

                    if v_count < v_min:
                        v_min = v_count
                    if v_count > v_max:
                        v_max = v_count
                    if i_count < i_min:
                        i_min = i_count
                    if i_count > i_max:
                        i_max = i_count

                    v_inst = (v_count - v_baseline) * k_v
                    i_inst = (i_count - i_baseline) * k_i

                    sum_v2 += v_inst * v_inst
                    sum_i2 += i_inst * i_inst
                    sum_p += v_inst * i_inst

                    if not fast:
                        time.sleep_us(dt_us)
        
        # Determina quale numero di campioni usare per il calcolo finale
        n_used = n
        try:
            # se sh è stato definito e diverso da zero, usa n_eff calcolato nel ramo streaming
            if sh != 0:
                n_used = n - abs(sh)
        except Exception:
            n_used = n

        # Grandezze finali: RMS, potenza attiva, apparente e fattore di potenza.
        v_rms = math.sqrt(sum_v2 / n_used) if n_used > 0 else 0.0
        i_rms = math.sqrt(sum_i2 / n_used) if n_used > 0 else 0.0
        p_active = sum_p / n_used if n_used > 0 else 0.0
        p_apparent = v_rms * i_rms
        power_factor = (p_active / p_apparent) if p_apparent > 0 else 0.0

        return {
            "n": n_used,
            "sample_rate_hz": sr,
            "volts_rms": v_rms,
            "amps_rms": i_rms,
            "power_w": p_active,
            "apparent_power_va": p_apparent,
            "power_factor": power_factor,
            "phase_shift_samples": sh,
            "voltage": {
                "baseline_mean": v_baseline,
                "min": v_min,
                "max": v_max,
                "clipping": (v_min < 50) or (v_max > 4040)
            },
            "current": {
                "baseline_mean": i_baseline,
                "min": i_min,
                "max": i_max,
                "clipping": (i_min < 50) or (i_max > 4040)
            }
        }

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
            except OSError:
                pass
        except Exception as e:
            pass
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
        try:
            self._init_adc()
        except Exception:
            return [0]*n, sample_rate_hz
        n = max(32, min(int(n), 4096))
        sr = max(200, min(int(sample_rate_hz), 20000))
        dt_us = int(1_000_000 / sr)
        arr = []
        for i in range(n):
            try:
                arr.append(self._read_count())
            except Exception:
                arr.append(0)
            if not fast:
                import time
                time.sleep_us(dt_us)
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
        try:
            self.adc = machine.ADC(machine.Pin(self.pin))
            self.adc.atten(machine.ADC.ATTN_11DB)
        except Exception as e:
            print(f"[ERROR] Errore in GenericSensor.__init__: {e}")
            self.adc = None

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
