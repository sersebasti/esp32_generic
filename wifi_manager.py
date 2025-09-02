# wifi_manager.py
# Gestore WiFi + avvio server HTTP con health-check e retry robusti
# Setup mode one-shot: bottone → LED verde OFF, LED blu fisso, STA OFF, AP ON, server attivo
# Dopo l’ingresso in setup, run() termina (nessun ciclo ulteriore).

import network, time, json, socket, machine, micropython  # type: ignore

# LED di stato (facoltativo)
try:
    from led_status import LedStatus
except Exception:
    LedStatus = None

# Server HTTP (facoltativo)
try:
    from server import start_server
except Exception:
    start_server = None


# ---------------- Classe principale ----------------
class WiFiManager:
    def __init__(self, wifi_json="wifi.json", log=None):
        self.wifi_json = wifi_json
        self.log = log
        self.leds = LedStatus() if LedStatus else _NullLed()
        self._rtc_synced = False
        self._setup_mode = False  # one-shot finché non si riavvia

        # --- PULSANTE ---
        self._btn_pin_num = 32  # cambia se necessario
        self._btn_flag = False
        self._btn_last_ms = 0  # per debounce
        try:
            self._btn = machine.Pin(self._btn_pin_num, machine.Pin.IN, machine.Pin.PULL_UP)
            # active-low → premuto = GND
            self._btn.irq(trigger=machine.Pin.IRQ_FALLING, handler=self._irq_button)
        except Exception as e:
            self.log.info(f"Button init failed: {e!r}")
            self._btn = None


# ---------- UTIL: LED nullo se non disponibile ----------
class _NullLed:
    def show_connecting(self): pass
    def show_connected(self):  pass
    # API opzionali per setup-mode
    def green_off(self): pass
    def blue_on(self): pass

# esponi _NullLed come attributo della classe
WiFiManager._NullLed = _NullLed


# ------------------ Metodi interni (def → bind a fondo) ------------------
def _mac_hex_upper():
    """Ritorna il MAC STA come stringa es: 'A1B2C3D4E5F6' (o None se non disponibile)."""
    try:
        import ubinascii, network
        mac = network.WLAN(network.STA_IF).config('mac')  # bytes(6)
        return ubinascii.hexlify(mac).decode().upper()
    except Exception:
        return None

def _ssid_from_mac(prefix="ESP32_", fallback="ESP-SETUP", max_len=32):
    """Costruisce un SSID dal MAC. Se troppo lungo, usa gli ultimi 6 hex; altrimenti fallback."""
    mac_hex = _mac_hex_upper()
    if not mac_hex:
        return fallback
    full = prefix + mac_hex                 # es. ESP32_A1B2C3D4E5F6
    if len(full) <= max_len:
        return full
    short = prefix + mac_hex[-6:]           # es. ESP32_D4E5F6
    return short[:max_len]


def _sync_time_once(self):
    if self._rtc_synced:
        return
    try:
        import ntptime
        ntptime.host = "pool.ntp.org"   # opzionale
        ntptime.settime()               # setta l'RTC a UTC
        self._rtc_synced = True
        try:
            self.log.info(f"RTC sincronizzato: UTC={time.gmtime()!r}")
        except Exception:
            pass
    except Exception as e:
        self.log.info(f"NTP sync fallita: {e!r}")


def _networks_from_cfg(cfg):
    """
    Estrae [(ssid, password), ...] da più formati possibili:
      - singolo:            ssid/password
      - enumerati:          ssid_1/password_1, ssid_2/password_2, ...
      - lista:              networks: [{"ssid":"...","password":"..."}, ...]
    """
    nets = []

    # singolo
    s_single = (cfg.get("ssid") or "").strip()
    if s_single:
        nets.append((s_single, cfg.get("password") or ""))

    # enumerati
    idxs = []
    for k in cfg.keys():
        if isinstance(k, str) and k.startswith("ssid_"):
            try:
                idxs.append(int(k.split("_", 1)[1]))
            except Exception:
                pass
    for i in sorted(set(idxs)):
        s = (cfg.get("ssid_%d" % i) or "").strip()
        if s:
            nets.append((s, cfg.get("password_%d" % i) or ""))

    # lista
    for net in cfg.get("networks", []) or []:
        s = (net.get("ssid") or "").strip()
        if s:
            nets.append((s, net.get("password") or ""))

    # dedup preservando ordine
    seen, out = set(), []
    for ssid, pwd in nets:
        if ssid not in seen:
            out.append((ssid, pwd))
            seen.add(ssid)
    return out


def _load_networks(self):
    try:
        with open(self.wifi_json) as f:
            cfg = json.load(f)
    except Exception as e:
        self.log.info(f"Impossibile leggere {self.wifi_json}: {e!r}")
        return []
    nets = _networks_from_cfg(cfg)
    if not nets:
        self.log.info(f"Nessuna rete trovata in {self.wifi_json}")
    return nets


def _reset_wifi(self):
    # STA
    try:
        sta = network.WLAN(network.STA_IF)
        if sta.active():
            try:
                sta.disconnect()
            except Exception:
                pass
            sta.active(False)
    except Exception:
        pass

    # AP
    try:
        ap = network.WLAN(network.AP_IF)
        if ap.active():
            ap.active(False)
    except Exception:
        pass


def _ap_enable(self, essid="ESP-SETUP", password="12345678"):
    try:
        # Se usi il default, genera SSID basato su MAC; se passi un nome custom, lo mantengo
        if not essid or essid == "ESP-SETUP":
            try:
                essid = _ssid_from_mac(prefix="ESP32_", fallback="ESP-SETUP", max_len=32)
            except Exception:
                pass

        ap = network.WLAN(network.AP_IF)
        ap.active(True)

        # Imposta un'opzione per volta: alcune build non accettano più kwargs insieme
        ap.config(essid=essid)
        if password:
            # WPA2-PSK se password presente (>=8 char in genere)
            ap.config(password=password)
            try:
                # AUTH_WPA_WPA2_PSK = 3 su ESP32
                ap.config(authmode=3)
            except Exception:
                pass
        else:
            # rete open
            try:
                ap.config(authmode=0)  # OPEN
            except Exception:
                pass

        ip = ap.ifconfig()[0]
        # mantengo il logging com'era per non cambiare il comportamento/format
        self.log.info("AP attivo su")
        return ip
    except Exception as e:
        self.log.info("AP enable fallito")
        return None

def _ap_disable(self):
    try:
        ap = network.WLAN(network.AP_IF)
        if ap.active():
            ap.active(False)
            self.log.info("AP disattivato")
    except Exception as e:
        self.log.info(f"AP disable fallito: {e!r}")


def _enter_setup_once(self):
    """
    Entra in setup mode una sola volta: LED verde OFF, blu fisso; STA OFF; AP ON; server ON.
    Dopo aver predisposto tutto, ritorna al chiamante (il chiamante deciderà se uscire dal loop).
    """
    if self._setup_mode:
        return
    self._setup_mode = True
    self.log.info("🔧 Setup mode → STA OFF, AP ON, server attivo")
    

    # LED: verde OFF, blu fisso (se disponibili)
    try:
        if hasattr(self.leds, "show_ap"):
            self.leds.show_ap()

    except Exception:
        pass
    print("LED: verde OFF, blu fisso")

    # Spegni STA
    try:
        sta = network.WLAN(network.STA_IF)
        if sta.active():
            try:
                sta.disconnect()
            except Exception:
                 pass
            sta.active(False)
    except Exception:
         pass
    print("WiFi STA disattivata")

    # Accendi AP + server
    ip_ap = self._ap_enable()
    try:
        self._start_server(port=80)
    except Exception as e:
        self.log.info(f"Start server fallito: {e!r}")
        
    if not ip_ap:
        ip_ap = "192.168.4.1"
        
    print("UI WiFi: http://%s/wifi/ui" % ip_ap)


def _try_connect(self, ssid, pwd, timeout_s=15, cancel_cb=None):
    """
    Prova a connettersi a (ssid,pwd) fino a timeout_s.
    Se cancel_cb() → True, annulla subito e ritorna (False, None, "cancelled").
    Ritorna: (ok:bool, ip:str|None, reason:str|None)
    """
    sta = network.WLAN(network.STA_IF)
    try:
        sta.active(True)
    except Exception:
        pass

    # disconnessione preventiva
    try:
        sta.disconnect()
    except Exception:
        pass

    self.log.info(f"Tentativo di connessione a rete '{ssid}'...")

    try:
        sta.connect(ssid, pwd)
    except Exception as e:
        self.log.info(f"Errore connect(): {e!r}")
        return (False, None, "error")

    t0 = time.ticks_ms()
    while not sta.isconnected():
        # controllo cancellazione immediata
        if cancel_cb and cancel_cb():
            self.log.info("Connessione annullata dal pulsante")
            try:
                sta.disconnect()
            except Exception:
                pass
            return (False, None, "cancelled")

        if time.ticks_diff(time.ticks_ms(), t0) > int(timeout_s * 1000):
            return (False, None, "timeout")

        time.sleep_ms(80)  # reattivo ma non invasivo

    ip = sta.ifconfig()[0]
    return (True, ip, None)


def _port_open(self, ip, port, timeout_ms=500):
    try:
        s = socket.socket()
        s.settimeout(timeout_ms / 1000.0)
        s.connect((ip, port))
        s.close()
        return True
    except Exception:
        return False


def _start_server(self, port=80):
    """Avvia il server HTTP se non già in ascolto. Tollera EADDRINUSE."""
    if start_server is None:
        self.log.info("server.py non disponibile: start_server=None")
        return True

    # IP attuale: preferisci STA, altrimenti AP (se attivo)
    try:
        sta = network.WLAN(network.STA_IF)
    except Exception:
        sta = None
    try:
        ap = network.WLAN(network.AP_IF)
    except Exception:
        ap = None

    if sta and sta.isconnected():
        ip = sta.ifconfig()[0]
    elif ap and ap.active():
        ip = ap.ifconfig()[0]
    else:
        ip = "0.0.0.0"

    # Se già aperto su quell'IP, non rilanciare
    if ip != "0.0.0.0" and self._port_open(ip, port):
        self.log.info("Server già attivo, skip avvio.")
        return True

    def _runner():
        # Se il tuo server.py consente port=..., usalo; altrimenti prova senza
        try:
            start_server(port=port)
        except TypeError:
            start_server()

    try:
        import _thread
        _thread.start_new_thread(_runner, ())
        return True
    except Exception as e:
        self.log.info(f"Thread server non disponibile ({e!r}); provo in foreground")
        # foreground (bloccante): solo per debug!
        try:
            _runner()
            return True
        except OSError as oe:
            # EADDRINUSE: consideriamo "ok" (codice può variare, es. 98/112)
            if getattr(oe, 'args', [None])[0] in (98, 112):
                self.log.info(f"Porta {port} occupata: presumo server già su.")
                return True
            self.log.info(f"Avvio server fallito: {oe!r}")
            return False
        except Exception as e2:
            self.log.info(f"Avvio server fallito: {e2!r}")
            return False



# ------------------ HEALTH CHECK ------------------

def check_wifi_and_server(self, host=None, port=80, timeout=2.0, retries=2):
    """
    Verifica:
      - Wi-Fi connesso
      - server raggiungibile (GET /health)
    Se host è None, usa l'IP STA (self-check).
    Ritorna: {wifi_ok, ip, server_ok, health, error}
    """
    sta = network.WLAN(network.STA_IF)
    wifi_ok = bool(sta.isconnected())
    ip = sta.ifconfig()[0] if wifi_ok else None

    target_host = host or ip
    result = {"wifi_ok": wifi_ok, "ip": ip, "server_ok": False, "health": None, "error": None}

    if not wifi_ok:
        result["error"] = "wifi_not_connected"
        return result
    if not target_host:
        result["error"] = "no_target_host"
        return result

    last_err = None
    for _ in range(max(1, retries)):
        try:
            s = socket.socket()
            s.settimeout(timeout)
            s.connect((target_host, port))
            # HTTP/1.0, Host opzionale in MicroPython
            host_hdr = target_host if isinstance(target_host, str) else "localhost"
            req = b"GET /health HTTP/1.0\r\nHost: %s\r\n\r\n" % host_hdr.encode()
            s.send(req)

            chunks = []
            start = time.ticks_ms()
            while True:
                chunk = s.recv(512)
                if not chunk:
                    break
                chunks.append(chunk)
                # safety limit
                if sum(len(c) for c in chunks) > 8192:
                    break
                if time.ticks_diff(time.ticks_ms(), start) > int(timeout * 1000):
                    break
            s.close()

            data = b"".join(chunks)
            if not data:
                last_err = "empty_response"
                continue

            sep = data.find(b"\r\n\r\n")
            if sep < 0:
                last_err = "bad_headers"
                continue

            header = data[:sep]
            body = data[sep + 4:]
            status_line = header.split(b"\r\n", 1)[0]
            if b"200" not in status_line:
                last_err = "http_status_not_200: " + status_line.decode(errors="ignore")
                continue

            try:
                health = json.loads(body.decode())
            except Exception:
                health = {"raw": body.decode(errors="ignore")}

            result["server_ok"] = True
            result["health"] = health
            result["error"] = None
            return result

        except Exception as e:
            last_err = e
            time.sleep_ms(150)

    result["error"] = str(last_err)
    return result


def _irq_button(self, pin):
    now = time.ticks_ms()
    if time.ticks_diff(now, self._btn_last_ms) > 200:  # debounce
        self._btn_last_ms = now
        self._btn_flag = True
        # niente print qui dentro!


def button_pressed(self, clear=True):
    """Ritorna True se è stato premuto; se clear=True azzera il flag."""
    if self._btn_flag:
        if clear:
            self._btn_flag = False
        return True
    return False


# ------------------ LOOP PRINCIPALE ------------------

def run(self):
    """
    Ciclo di sorveglianza:
      - se Wi-Fi non connesso → prova reti da wifi.json
      - se Wi-Fi ok ma server KO → prova ad avviare server senza toccare il Wi-Fi
      - se tutto ok → LED connected e pausa più lunga
      - bottone one-shot → entra in setup e termina
    """
    BACKOFF_RETRY_MS = 500        # tra tentativi sulla stessa rete
    BACKOFF_NO_NET_S = 5          # nessuna rete configurata
    BACKOFF_ALL_FAIL_S = 2        # tutte le reti fallite
    HEALTH_OK_SLEEP_S = 5         # tutto ok → ricontrollo tra N secondi
    SERVER_PORT = 80

    while True:

        self.log.info("Loop WiFiManager attivo")

        # 1) Bottone premuto subito → entra in setup e TERMINA
        if (not self._setup_mode) and self.button_pressed(clear=False):
            self.log.info("🔘 Bottone premuto all'inizio loop → entro in setup")
            #self._enter_setup_once()
            break  # uscita dal while

        result = self.check_wifi_and_server(port=SERVER_PORT)
        print("Stato WiFi+server: %s" % (result,))

        if not result["wifi_ok"]:
            self.log.info("Wi-Fi non connesso provo a connettermi...")
            self._reset_wifi()
            try:
                self.leds.show_connecting()
            except Exception:
                pass

            nets = self._load_networks()
            if not nets:
                self.log.info(f"Nessuna rete configurata in {self.wifi_json}; attendo configurazione: ")
                time.sleep(BACKOFF_NO_NET_S)
                continue

            connected = False

            for ssid, pwd in nets or []:

                self.log.info(f"Provo rete '{ssid}'...")

                # 2) Bottone premuto prima del tentativo → setup e TERMINA
                if self.button_pressed(clear=False):
                    self.log.info("🔘 Bottone Access Point premuto premuto → entro in setup")
                    break  # esce dal for e dal while

                ok, ip, reason = self._try_connect(
                    ssid, pwd, timeout_s=15,
                    # peek: non consumare qui, decide _try_connect
                    cancel_cb=lambda: self.button_pressed(clear=False)
                )

                if ok:
                    try:
                        self.leds.show_connected()
                    except Exception:
                        self.log.info("Errore LED connected")

                    self.log.info(f"Connesso alla rete '{ssid}' con IP {ip}")
                    print("✅ Connesso alla rete '%s' con IP %s" % (ssid, ip))
                    

                    try:
                        self._sync_time_once()   # sincronizza RTC una volta
                    except Exception as e:
                        self.log.info(f"NTP sync fallita: {e!r}")

                    try:
                        self._start_server(port=SERVER_PORT)
                    except Exception as e:
                        self.log.info(f"Start server fallito: {e!r}")

                    # try:
                    #     import uftpd
                    #     self.log.info("FTP server avviato su %s:21" % ip)
                    # except Exception as e:
                    #     self.log.error("Errore avvio FTP: %s" % e)    

                    connected = True
                    break
                else:
                    # 3) Tentativo annullato dal bottone → setup e TERMINA
                    if reason == "cancelled":
                        self.log.info("Connessione annullata dal pulsante → entro in setup")
                        #self._enter_setup_once()
                        break  # esce dal for e dal while

                    print("❌ Connessione fallita a '%s' (%s)" % (ssid, reason or "fail"))
                    #self.log.info("Connessione fallita a '%s' (%s)", ssid, reason)
                    time.sleep_ms(BACKOFF_RETRY_MS)

            if not connected:
                time.sleep(BACKOFF_ALL_FAIL_S)
                continue

        else:
            # Wi-Fi OK
            ip = result.get("ip")
            if not result["server_ok"]:
                # server KO → prova ad avviare se la porta non risulta già aperta
                if ip and not self._port_open(ip, SERVER_PORT):
                    try:
                        self._start_server(port=SERVER_PORT)
                        time.sleep(1)
                        again = self.check_wifi_and_server(port=SERVER_PORT)
                        if again.get("server_ok"):
                            print("✅ Server avviato con successo.")
                        else:
                            self.log.info(f"Server non raggiungibile dopo avvio: {again.get('error')}")
                    except Exception as e:
                        self.log.info(f"Errore avvio server: {e}")
                else:
                    # porta aperta ma /health KO: ritenta più tardi
                    self.log.info(f"Porta {SERVER_PORT} aperta ma /health KO; ritento più tardi.")
                    time.sleep(3)
                    continue
            else:
                print("✅ WiFi e server OK. IP: %s" % result["ip"])
                try:
                    self.leds.show_connected()
                except Exception:
                    pass

                for rem in range(HEALTH_OK_SLEEP_S, 0, -1):
                    print("sleeping... %s" % (rem,))
                    # 4) Bottone premuto durante lo sleep → setup e TERMINA
                    if self.button_pressed(clear=False):
                        self.log.info("🔘 Bottone premuto durante lo sleep → entro in setup")
                        #self._enter_setup_once()
                        break
                    time.sleep(1)
                continue

    print("---- fine ciclo while----\n")
    self._enter_setup_once()

    while True:
        self.log.info("Loop Access Point attivo")
        print("Sono in AP mode\n")
        time.sleep(1) 




# ------------------ Bind dei metodi alla classe ------------------
WiFiManager._sync_time_once = _sync_time_once
WiFiManager._networks_from_cfg = staticmethod(_networks_from_cfg)
WiFiManager._load_networks = _load_networks
WiFiManager._reset_wifi = _reset_wifi
WiFiManager._ap_enable = _ap_enable
WiFiManager._ap_disable = _ap_disable
WiFiManager._enter_setup_once = _enter_setup_once
WiFiManager._try_connect = _try_connect
WiFiManager._port_open = _port_open
WiFiManager._start_server = _start_server
WiFiManager.check_wifi_and_server = check_wifi_and_server
WiFiManager._irq_button = _irq_button
WiFiManager.button_pressed = button_pressed
WiFiManager.run = run


# --------- Esempio di esecuzione diretta ---------
if __name__ == "__main__":
    wm = WiFiManager()
    wm.run()
