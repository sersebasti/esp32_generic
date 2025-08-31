# wifi_manager.py
# Gestore WiFi + avvio server HTTP con health-check e retry robusti

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


class _PrintLogger:
    def info(self, msg):  print("[I]", msg)
    def warn(self, msg):  print("[W]", msg)
    def error(self, msg): print("[E]", msg)


class WiFiManager:
    def __init__(self, wifi_json="wifi.json", log=None):
        self.wifi_json = wifi_json
        self.log = log or _PrintLogger()
        self.leds = LedStatus() if LedStatus else _NullLed()

        # --- PULSANTE ---
        self._btn_pin_num = 16  # D4 sulla tua board -> GPIO4 (cambia se necessario)
        self._btn_flag = False
        self._btn_last_ms = 0  # per debounce
        try:
            self._btn = machine.Pin(self._btn_pin_num, machine.Pin.IN, machine.Pin.PULL_UP)
            # attiva interrupt su fronte di discesa (active-low → premuto = GND)
            self._btn.irq(trigger=machine.Pin.IRQ_FALLING, handler=self._irq_button)
        except Exception as e:
            self.log.warn("Button init failed: %r" % e)
            self._btn = None

    # ---------- UTIL: LED nullo se non disponibile ----------
class _NullLed:
    def show_connecting(self): pass
    def show_connected(self):  pass

# Reinserisco _NullLed dentro la classe correttamente
WiFiManager._NullLed = _NullLed

# ------------------ Metodi interni ------------------

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
        self.log.warn("Impossibile leggere %s: %r" % (self.wifi_json, e))
        return []
    nets = _networks_from_cfg(cfg)
    if not nets:
        self.log.warn("Nessuna rete trovata in %s" % self.wifi_json)
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


def _try_connect(self, ssid, pwd, timeout_s=15):
    """
    Accende STA, prova connessione a (ssid,pwd) fino a timeout_s.
    Ritorna (True, ip) se aggancia; altrimenti (False, None).
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

    self.log.info("Tentativo di connessione a rete '%s'..." % ssid)

    try:
        sta.connect(ssid, pwd)
    except Exception as e:
        self.log.error("Errore connect(): %r" % e)
        return (False, None)

    t0 = time.ticks_ms()
    while not sta.isconnected():
        if time.ticks_diff(time.ticks_ms(), t0) > int(timeout_s * 1000):
            return (False, None)
        time.sleep_ms(120)

    ip = sta.ifconfig()[0]
    return (True, ip)


def _port_open(self, ip, port, timeout_ms=500):
    try:
        s = socket.socket()
        s.settimeout(timeout_ms / 1000)
        s.connect((ip, port))
        s.close()
        return True
    except Exception:
        return False


def _start_server(self, port=80):
    """Avvia il server HTTP se non già in ascolto. Tollera EADDRINUSE."""
    if start_server is None:
        self.log.warn("server.py non disponibile: start_server=None")
        return True

    # IP attuale della STA
    sta = network.WLAN(network.STA_IF)
    ip = sta.ifconfig()[0] if sta and sta.isconnected() else "0.0.0.0"

    # Se già aperto, non rilanciare
    if ip != "0.0.0.0" and self._port_open(ip, port):
        self.log.info("Server già attivo su %s:%d, skip avvio." % (ip, port))
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
        self.log.warn("Thread server non disponibile (%r); provo in foreground" % e)
        # foreground (bloccante): solo per debug!
        try:
            _runner()
            return True
        except OSError as oe:
            # EADDRINUSE: consideriamo "ok"
            if getattr(oe, 'args', [None])[0] == 112:
                self.log.warn("Porta %d occupata: presumo server già su." % port)
                return True
            self.log.error("Avvio server fallito: %r" % oe)
            return False
        except Exception as e2:
            self.log.error("Avvio server fallito: %r" % e2)
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
    # ISR: pochissimo lavoro → solo debounce + flag; niente allocazioni pesanti
    now = time.ticks_ms()
    if time.ticks_diff(now, self._btn_last_ms) > 200:  # debounce 200 ms
        self._btn_last_ms = now
        self._btn_flag = True
        # piccolo feedback (se la tua build stampa dall'IRQ, ok; altrimenti commenta)
        try:
            print("🔘 (IRQ) bottone premuto")
        except Exception:
            pass


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
    """
    BACKOFF_RETRY_MS = 500         # tra tentativi sulla stessa rete
    BACKOFF_NO_NET_S = 5           # nessuna rete configurata
    BACKOFF_ALL_FAIL_S = 2         # tutte le reti fallite
    HEALTH_OK_SLEEP_S = 30         # tutto ok → ricontrollo tra 30s
    SERVER_PORT = 80

    while True:

        self.log.info("Loop WiFiManager attivo, controllo stato...")

        if self.button_pressed(clear=True):
            print("🔘 Bottone premuto → flag rilevato (TODO: azione futura)")

        result = self.check_wifi_and_server(port=SERVER_PORT)
        print("Stato WiFi+server:", result)

        if not result["wifi_ok"]:
            # non connesso → reset + tentativi
            self._reset_wifi()
            self.leds.show_connecting()

            nets = self._load_networks()
            if not nets:
                self.log.warn("Nessuna rete configurata in %s; attendo configurazione." % self.wifi_json)
                time.sleep(BACKOFF_NO_NET_S)
                continue

            connected = False
            for ssid, pwd in nets or []:

                if self.button_pressed(clear=True):
                    print("🔘 Bottone premuto durante i tentativi → (TODO: futura azione)")
                    break  # esci dal for (rimani nel while, gestirai poi)

                ok, ip = self._try_connect(ssid, pwd, timeout_s=15)
                if ok:
                    try:
                        self.leds.show_connected()
                    except Exception:
                        self.log.error("Errore LED connected")

                    msg = "Connesso alla rete '%s' con IP %s" % (ssid, ip)
                    self.log.info(msg); print("✅", msg)

                    try:
                        self._start_server(port=SERVER_PORT)
                    except Exception as e:
                        self.log.error("Start server fallito: %s" % e)

                    connected = True
                    break
                else:
                    print("❌ Connessione fallita a '%s'" % ssid)
                    self.log.info("Connessione fallita a '%s'" % ssid)
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
                            self.log.warn("Server non raggiungibile dopo avvio: %s" % again.get("error"))
                    except Exception as e:
                        self.log.error("Errore avvio server: %s" % e)
                else:
                    # porta aperta ma /health KO: ritenta più tardi
                    self.log.warn("Porta %d aperta ma /health KO; ritento più tardi." % SERVER_PORT)
                    time.sleep(3)
                    continue
            else:
                print("✅ WiFi e server OK. IP:", result["ip"])
                try:
                    self.leds.show_connected()
                except Exception:
                    pass

                for rem in range(HEALTH_OK_SLEEP_S, 0, -1):
                    print("sleeping...", rem)
                    # controllo pulsante durante l'attesa
                    if self.button_pressed(clear=True):
                        print("🔘 Bottone premuto durante il sleep → (TODO: futura azione)")
                        break  # interrompe il countdown e torna al while
                    time.sleep(1)
                continue


# Bind dei metodi alla classe (per mantenere la struttura in un unico file)
WiFiManager._networks_from_cfg = staticmethod(_networks_from_cfg)
WiFiManager._load_networks = _load_networks
WiFiManager._reset_wifi = _reset_wifi
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

