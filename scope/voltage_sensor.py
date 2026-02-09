from .generic_sensor import GenericSensor

class VoltageSensor(GenericSensor):
    """
    Sensore di tensione (es. ZMPT1901B), eredita tutta la logica generica.
    """
    def __init__(self, adc_pin, config=None):
        try:
            super().__init__(adc_pin)
        except Exception as e:
            print(f"[ERROR] Errore in VoltageSensor.__init__: {e}")
        self.type = 'voltage'
        self.config = config or {}
        # Qui puoi aggiungere logica specifica per la tensione se serve

    # Se serve logica hardware-specific, aggiungila qui
    # Altrimenti eredita tutto da GenericSensor
