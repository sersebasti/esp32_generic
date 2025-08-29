# wifi_manager.py
import time, network
from wifi_connect import connect_from_json, start_ap_mode
from led_status import LedStatus

try:
    from status_server import start_status_server
except Exception:
    start_status_server = None

class WiFiManager:
    """
    Gestisce: connessione, reconnect, AP di configurazione, heartbeat e status server.
    Compatibile ESP32/ESP8266.
    """
    def __init__(self, logger, wifi_json="wifi.json", check_interval=30, heartbeat=True):
        self.log = logger
        self.wifi_json = wifi_json
        self.check_interval = int(check_interval)
        self.heartbeat = heartbeat
        self.leds = LedStatus()
        self.status_started = False

    # --- util ---
    def _ts(self):
        try:
            t = time.localtime()
            return "%02d:%02d:%02d" % (t[3], t[4], t[5])
        except Exception:
            return "t+%dms" % time.ticks_ms()

    def _wifi_is_ok(self):
        sta = network.WLAN(network.STA_IF)
        return sta.active() and sta.isconnected() and sta.ifconfig()[0] not in (None, "", "0.0.0.0")

    def _try_reconnect(self):
        ok, ip = connect_from_json(self.wifi_json, timeout=15)
        return ok, ip

    def _start_config_ap_with_fallback(self):
        ap = None
        try:
            ap = start_ap_mode(ssid="ESP32_SETUP", password="12345678", channel=6)
        except Exception as e:
            self.log.error("start_ap_mode() raised: %r" % e)
            ap = None

        if not ap:
            try:
                sta = network.WLAN(network.STA_IF)
                try: sta.active(False)
                except Exception: pass

                ap = network.WLAN(network.AP_IF)
                ap.active(False); time.sleep_ms(100); ap.active(True)
                try:
                    ap.config(essid="ESP32_1_SETUP", password="12345678",
                              authmode=network.AUTH_WPA_WPA2_PSK,
                              channel=6, hidden=0, max_clients=5)
                except Exception:
                    ap.config(essid="ESP32_1_SETUP", password="12345678",
                              authmode=network.AUTH_WPA2_PSK)
                try:
                    ap.ifconfig(("192.168.4.1","255.255.255.0","192.168.4.1","8.8.8.8"))
                except Exception:
                    pass
            except Exception as e:
                self.log.error("Local AP fallback failed: %r" % e)
                ap = None
        return ap

    def _ensure_status(self):
        if self.status_started or (start_status_server is None):
            return
        try:
            import _thread
            _thread.start_new_thread(start_status_server, ())
            self.status_started = True
            print("Status endpoint attivo: GET /health, GET /status")
        except Exception as e:
            print("Status server non avviato:", e)

    def _sleep_adaptive(self):
        # mentre AP attivo → retry più frequenti
        try:
            ap = network.WLAN(network.AP_IF)
            secs = 5 if ap.active() else self.check_interval
        except Exception:
            secs = self.check_interval
        for _ in range(int(secs)):
            time.sleep(1)

    # --- loop principale ---
    def run(self):
        prev_ok = False
        while True:
            try:
                connected = self._wifi_is_ok()

                # Heartbeat
                if self.heartbeat:
                    if connected:
                        sta = network.WLAN(network.STA_IF)
                        ip_now = sta.ifconfig()[0]
                        try:
                            rssi = sta.status('rssi')
                            print("[%s] HB connected ip=%s rssi=%sdBm" % (self._ts(), ip_now, rssi))
                        except Exception:
                            print("[%s] HB connected ip=%s" % (self._ts(), ip_now))
                    else:
                        print("[%s] HB not connected" % self._ts())

                if connected:
                    # LED stato
                    self.leds.show_connected()
                    # spegni AP se rimasto acceso
                    try:
                        ap = network.WLAN(network.AP_IF)
                        if ap.active():
                            ap.active(False)
                            print("AP spento: STA connesso")
                    except Exception:
                        pass

                    if not prev_ok:
                        sta = network.WLAN(network.STA_IF)
                        self.log.info("WiFi restored (ip=%s)" % sta.ifconfig()[0])
                        prev_ok = True
                        self._ensure_status()

                else:
                    # Tentativi
                    self.leds.show_connecting()
                    if prev_ok:
                        self.log.warn("WiFi lost; trying reconnect")

                    # assicurati STA attivo (anche con AP acceso)
                    try:
                        sta = network.WLAN(network.STA_IF)
                        sta.active(True)
                    except Exception:
                        pass

                    ok, ip = self._try_reconnect()
                    prev_ok = ok
                    if ok:
                        self.log.info("Reconnected (ip=%s)" % ip)
                        # spegni AP se acceso
                        try:
                            ap = network.WLAN(network.AP_IF)
                            if ap.active():
                                ap.active(False)
                                print("AP spento dopo reconnect riuscito")
                        except Exception:
                            pass
                        self._ensure_status()
                        time.sleep_ms(200)
                        continue
                    else:
                        self.log.error("Reconnect failed")
                        # Fallback: AP di configurazione
                        ap = self._start_config_ap_with_fallback()

                    if ap and ap.active():
                        self.leds.show_ap()
                        try:
                            ip_ap = ap.ifconfig()[0]
                        except Exception:
                            ip_ap = "192.168.4.1"
                        print("Access Point attivo per configurazione! IP:", ip_ap)

                        if start_status_server and False:
                            # (se vuoi servire anche qui qualcosa)
                            pass

                        # Se hai un portale di configurazione:
                        try:
                            from web_ap import start_web_ap
                        except Exception:
                            start_web_ap = None

                        if start_web_ap:
                            start_web_ap()  # ritorna al termine
                            try: ap.active(False)
                            except Exception: pass

                            ok, ip = self._try_reconnect()
                            prev_ok = ok
                            if ok:
                                self.log.info("Connected post-setup (ip=%s)" % ip)
                                self._ensure_status()
                                continue
                            else:
                                self.log.warn("Post-setup connect failed; lascio AP attivo e riprovo più tardi")
                                continue
                        else:
                            print("Apri http://%s per la configurazione (se web_ap non è presente, resta solo l'AP)." % ip_ap)
                            continue
                    else:
                        self.log.error("Impossibile avviare AP di configurazione")
                        time.sleep(5)
                        continue

                self._sleep_adaptive()

            except Exception as e:
                self.log.error("Errore nel ciclo WiFi: %r" % e)
                time.sleep(5)
