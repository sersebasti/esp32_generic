from .generic_sensor import GenericSensor

class VoltageSensor(GenericSensor):
    def _init_adc(self):
            # Logica base: crea ADC se non esiste
            if hasattr(self, 'adc') and self.adc:
                return
            import machine
            self.adc = machine.ADC(machine.Pin(self.adc_pin))
            self.adc.atten(machine.ADC.ATTN_11DB)

    def _read_count(self):
            self._init_adc()
            s = 0
            for _ in range(4):
                s += self.adc.read()
            return s >> 2
    """
    Sensore di tensione (es. ZMPT1901B), eredita tutta la logica generica.
    """
    def __init__(self, adc_pin, config=None, cal_dir="scope"):
        print(f"[DEBUG] VoltageSensor __init__ adc_pin={adc_pin}")
        try:
            super().__init__(adc_pin)
        except Exception as e:
            print(f"[ERROR] Errore in VoltageSensor.__init__: {e}")
        self.adc_pin = adc_pin
        self.cal_dir = cal_dir
        self.cal_file = f"{cal_dir}/calibrate_{adc_pin}.json"
        self.type = 'voltage'
        self.config = config or {}
        self.cal = self._load_calibration()
        # Qui puoi aggiungere logica specifica per la tensione se serve

    def measure_volts(self, n=1600, sr=4000, fast=False):
        arr, sr = self.sample_counts(n, sr, fast=fast)
        baseline = float(self.cal.get("baseline_mean", sum(arr)/len(arr)))
        rms = self._rms_with_baseline(arr, baseline)
        k = float(self.cal.get("k_V_per_count", 0.0))
        volts = k * rms
        return volts, rms, baseline, min(arr), max(arr)

    # Usa direttamente add_calibration_point di GenericSensor
