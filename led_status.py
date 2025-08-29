# led_status.py

# === Configurazione LED (ESP32 di default) ===
LED_BLUE_PIN  = 2      # LED blu su GPIO2
LED_BLUE_LOW  = False  # active HIGH

LED_GREEN_PIN = 15     # pin libero per LED verde
LED_GREEN_LOW = False

try:
    from machine import Pin, Timer  # type: ignore
except Exception:
    Pin = None
    Timer = None


def _alloc_timer():
    """
    Restituisce un Timer valido provando -1,0,1,2,... a seconda della porta.
    Ritorna None se non disponibile.
    """
    if Timer is None:
        return None
    # Ordine: -1 (soft/virtual su alcune build), poi hardware 0..7
    for tid in (-1, 0, 1, 2, 3, 4, 5, 6, 7):
        try:
            return Timer(tid)
        except Exception:
            pass
    return None


class Led:
    def __init__(self, pin_no, active_low=True):
        self.ok = (Pin is not None)
        if not self.ok:
            return
        self.active_low = active_low
        self.pin = Pin(pin_no, Pin.OUT)
        self.off()

    def on(self):
        if self.ok:
            self.pin.value(0 if self.active_low else 1)

    def off(self):
        if self.ok:
            self.pin.value(1 if self.active_low else 0)

    def toggle(self):
        if self.ok:
            self.pin.value(1 - self.pin.value())


class Blinker:
    """Gestisce lampeggio tramite Timer hardware"""
    def __init__(self, led, period_ms=400):
        self.led = led
        self.period = period_ms
        self.timer = None
        self.running = False

    def start(self):
        if not self.led.ok or self.running:
            return
        tm = _alloc_timer()
        if tm is None:
            # Nessun timer disponibile → fallback: blu fisso
            self.led.on()
            return
        self.timer = tm
        self.timer.init(
            period=self.period,
            mode=Timer.PERIODIC,
            callback=lambda t: self.led.toggle()
        )
        self.running = True

    def stop(self, leave_on=None):
        if self.timer:
            try:
                self.timer.deinit()
            except Exception:
                pass
        self.timer = None
        self.running = False
        if leave_on is True:
            self.led.on()
        if leave_on is False:
            self.led.off()


class LedStatus:
    """
    Gestione LED di stato per WiFi:
      - blu: lampeggia durante tentativi
      - blu: fisso in AP
      - verde: acceso quando connesso
    """

    def __init__(self,
                 blue_pin=LED_BLUE_PIN, blue_low=LED_BLUE_LOW,
                 green_pin=LED_GREEN_PIN, green_low=LED_GREEN_LOW):
        self.blue = Led(blue_pin, blue_low)
        self.green = Led(green_pin, green_low)
        self._blinker = Blinker(self.blue)

    def show_connected(self):
        """Verde ON, Blu OFF"""
        self._blinker.stop(leave_on=False)
        self.blue.off()
        self.green.on()

    def show_connecting(self):
        """Blu lampeggia, Verde OFF"""
        self.green.off()
        self._blinker.start()

    def show_ap(self):
        """Blu fisso, Verde OFF"""
        self._blinker.stop(leave_on=True)
        self.green.off()
