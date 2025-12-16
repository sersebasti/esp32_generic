# core/wifi_manager.py
# WiFiManager implementation moved under core

import network, time, json, socket, machine, micropython  # type: ignore

class _NullLog:
    def info(self, *a, **k):
        try: print(*a)
        except: pass
    warn = info
    error = info

try:
    from core.led_status import LedStatus
except Exception:
    try:
        from led_status import LedStatus
    except Exception:
        LedStatus = None

# Prefer core.server, then fallback to root server; keep reason
start_server = None
_server_import_err_core = None
_server_import_err_root = None
try:
    from core.server import start_server  # type: ignore
except Exception as e1:
    _server_import_err_core = e1
    try:
        from server import start_server  # type: ignore
    except Exception as e2:
        _server_import_err_root = e2
        start_server = None

class WiFiManager:
    def __init__(self, wifi_json="wifi.json", log=None):
        self.wifi_json = wifi_json
        self.log = log or _NullLog()
        self.leds = LedStatus() if LedStatus else _NullLed()
        self._rtc_synced = False
        self._setup_mode = False

        self._btn_pin_num = 32
        self._btn_last_ms = 0
        try:
            self._btn = machine.Pin(self._btn_pin_num, machine.Pin.IN, machine.Pin.PULL_UP)
            self._btn.irq(trigger=machine.Pin.IRQ_FALLING, handler=self._irq_button)
        except Exception as e:
            self.log.info(f"Button init failed: {e!r}")
            self._btn = None

class _NullLed:
    def show_connecting(self): pass
    def show_connected(self):  pass
    def green_off(self): pass
    def blue_on(self): pass

WiFiManager._NullLed = _NullLed

def _mac_hex_upper():
    try:
        import ubinascii, network
        mac = network.WLAN(network.STA_IF).config('mac')
        return ubinascii.hexlify(mac).decode().upper()
    except Exception:
        return None

def _ssid_from_mac(prefix="ESP32_", fallback="ESP-SETUP", max_len=32):
    mac_hex = _mac_hex_upper()
    if not mac_hex:
        return fallback
    full = prefix + mac_hex
    if len(full) <= max_len:
        return full
    short = prefix + mac_hex[-6:]
    return short[:max_len]

def _device_name_from_mac(prefix="ESP32_", fallback="ESP-SETUP", max_len=32):
    return _ssid_from_mac(prefix=prefix, fallback=fallback, max_len=max_len)

def _apply_sta_hostname(self, name=None):
    try:
        sta = network.WLAN(network.STA_IF)
    except Exception:
        sta = None
    if not sta:
        return False
    if not name:
        name = _device_name_from_mac(prefix="ESP32_", fallback="ESP-SETUP", max_len=32)
    ok = False
    try:
        sta.active(True)
    except Exception:
        pass
    try:
        sta.config(dhcp_hostname=name); ok = True
    except Exception:
        pass
    if not ok:
        try:
            sta.config(hostname=name); ok = True
        except Exception:
            pass
    if not ok:
        try:
            network.hostname(name)  # type: ignore
            ok = True
        except Exception:
            pass
    if ok:
        try: self.log.info(f"Hostname STA impostato: {name}")
        except Exception: pass
    else:
        try: self.log.info("Impostazione hostname STA non supportata su questa build")
        except Exception: pass
    return ok

def _sync_time_once(self):
    if self._rtc_synced:
        return
    try:
        import ntptime
        ntptime.host = "pool.ntp.org"
        ntptime.settime()
        self._rtc_synced = True
        try:
            self.log.info(f"RTC sincronizzato: UTC={time.gmtime()!r}")
        except Exception:
            pass
    except Exception as e:
        self.log.info(f"NTP sync fallita: {e!r}")

def _networks_from_cfg(cfg):
    nets = []
    s_single = (cfg.get("ssid") or "").strip()
    if s_single:
        nets.append((s_single, cfg.get("password") or ""))
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
    for net in cfg.get("networks", []) or []:
        s = (net.get("ssid") or "").strip()
        if s:
            nets.append((s, net.get("password") or ""))
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
    try:
        ap = network.WLAN(network.AP_IF)
        if ap.active():
            ap.active(False)
    except Exception:
        pass

def _ap_enable(self, essid="ESP-SETUP", password="12345678"):
    try:
        if not essid or essid == "ESP-SETUP":
            try:
                essid = _ssid_from_mac(prefix="ESP32_", fallback="ESP-SETUP", max_len=32)
            except Exception:
                pass
        ap = network.WLAN(network.AP_IF)
        ap.active(True)
        ap.config(essid=essid)
        if password and len(password) >= 8:
            ap.config(password=password)
            try:
                ap.config(authmode=3)
            except Exception:
                pass
        else:
            try:
                ap.config(authmode=0)
            except Exception:
                pass
        ip = ap.ifconfig()[0]
        self.log.info(f"AP attivo: SSID='{essid}' IP={ip}")
        return ip
    except Exception as e:
        self.log.info(f"AP enable fallito: {e!r}")
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
    if self._setup_mode:
        return
    self._setup_mode = True
    self.log.info("🔧 Setup mode → STA OFF, AP ON, server attivo")
    try:
        if hasattr(self.leds, "show_ap"):
            self.leds.show_ap()
    except Exception:
        pass
    print("LED: verde OFF, blu fisso")
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
    ip_ap = self._ap_enable()
    try:
        self._start_server(port=80, allow_foreground=False)
    except Exception as e:
        self.log.info(f"Start server fallito: {e!r}")
    if not ip_ap:
        ip_ap = "192.168.4.1"
    print("UI WiFi: http://%s/wifi/ui" % ip_ap)

def _try_connect(self, ssid, pwd, timeout_s=15, cancel_cb=None):
    sta = network.WLAN(network.STA_IF)
    try:
        sta.active(True)
    except Exception:
        pass
    try:
        sta.disconnect()
    except Exception:
        pass
    try:
        self._apply_sta_hostname(_device_name_from_mac(prefix="ESP32_", fallback="ESP-SETUP", max_len=32))
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
        if cancel_cb and cancel_cb():
            self.log.info("Connessione annullata dal pulsante")
            try:
                sta.disconnect()
            except Exception:
                pass
            return (False, None, "cancelled")
        if time.ticks_diff(time.ticks_ms(), t0) > int(timeout_s * 1000):
            return (False, None, "timeout")
        time.sleep_ms(80)
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

def _current_ip():
    try:
        sta = network.WLAN(network.STA_IF)
    except Exception:
        sta = None
    try:
        ap = network.WLAN(network.AP_IF)
    except Exception:
        ap = None
    if sta and sta.isconnected():
        return sta.ifconfig()[0]
    if ap and ap.active():
        return ap.ifconfig()[0]
    return "0.0.0.0"

def _maybe_start_ftp(self):
    try:
        import config as _cfg
    except Exception:
        _cfg = None
    enabled = bool(getattr(_cfg, "FTP_AUTOSTART", False)) if _cfg else False
    if not enabled:
        return False
    port = int(getattr(_cfg, "FTP_PORT", 21)) if _cfg else 21
    ip = _current_ip()
    if ip != "0.0.0.0" and self._port_open(ip, port):
        try: self.log.info(f"FTP già attivo sulla porta {port}")
        except Exception: pass
        return True
    try:
        try:
            import core.uftpd as uftpd
        except Exception:
            import uftpd as uftpd  # type: ignore
        if port != 21:
            try:
                uftpd.restart(port=port)
            except Exception:
                pass
        try: self.log.info(f"FTP avviato sulla porta {port}")
        except Exception: pass
        return True
    except Exception as e:
        try: self.log.info(f"FTP avvio fallito: {e!r}")
        except Exception: pass
        return False

def _start_server(self, port=80, allow_foreground=False):
    if start_server is None:
        # Log detailed reason and attempt minimal fallback server
        try:
            self.log.info("server.py non disponibile: start_server=None")
            if _server_import_err_core:
                self.log.info(f"Core server import error: {_server_import_err_core!r}")
            if _server_import_err_root:
                self.log.info(f"Root server import error: {_server_import_err_root!r}")
        except Exception:
            pass

        try:
            ok = self._fallback_start_server(port=port)
            return ok
        except Exception as e:
            self.log.info(f"Fallback server failed: {e!r}")
            return False
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
    if ip != "0.0.0.0" and (self._port_open(ip, port) or self._port_open(ip, 8080)):
        self.log.info("Server già attivo (80/8080), skip avvio.")
        try:
            self._maybe_start_ftp()
        except AttributeError:
            pass
        except Exception as e:
            try: self.log.info(f"FTP start skipped: {e!r}")
            except Exception: pass
        return True
    def _runner():
        start_server(preferred_port=port, fallback_port=8080, verbose=True)
    try:
        import _thread
        _thread.start_new_thread(_runner, ())
        try:
            self._maybe_start_ftp()
        except AttributeError:
            pass
        except Exception as e:
            try: self.log.info(f"FTP start skipped: {e!r}")
            except Exception: pass
        return True
    except Exception as e:
        self.log.info(f"Thread server non disponibile ({e!r})")
        if not allow_foreground:
            return False
        try:
            _runner()
            try:
                self._maybe_start_ftp()
            except AttributeError:
                pass
            except Exception as e:
                try: self.log.info(f"FTP start skipped: {e!r}")
                except Exception: pass
            return True
        except OSError as oe:
            if getattr(oe, 'args', [None])[0] in (98, 112):
                self.log.info(f"Porta occupata: presumo server già su.")
                return True
            self.log.info(f"Avvio server fallito: {oe!r}")
            return False
        except Exception as e2:
            self.log.info(f"Avvio server fallito: {e2!r}")
            return False

def _fallback_start_server(self, port=80):
    """Minimal blocking HTTP server providing /health and /wifi/ui placeholders.
    This is used only if importing the main server fails.
    """
    import socket
    s = socket.socket()
    try:
        s.setsockopt(0, 2, 1)  # may no-op on lwIP
    except Exception:
        pass
    try:
        s.bind(('0.0.0.0', port))
    except OSError as e:
        # 112 ~ EADDRINUSE on many MicroPython builds → try 8080
        try:
            s.bind(('0.0.0.0', 8080))
            port = 8080
        except Exception:
            s.close()
            raise e
    s.listen(2)
    self.log.info(f"Fallback HTTP server listening on {port}")
    while True:
        cl, addr = s.accept()
        try:
            req = cl.recv(512)
            # crude parse
            if b"/health" in req:
                body = json.dumps({"ok": True, "ts": time.time()})
                cl.send(b"HTTP/1.0 200 OK\r\nContent-Type: application/json\r\n\r\n" + body.encode())
            elif b"/wifi/ui" in req:
                html = "<html><body><h1>WiFi UI Fallback</h1></body></html>"
                cl.send(b"HTTP/1.0 200 OK\r\nContent-Type: text/html\r\n\r\n" + html.encode())
            else:
                cl.send(b"HTTP/1.0 200 OK\r\nContent-Type: text/plain\r\n\r\nESP32 Fallback Server")
        except Exception:
            pass
        try:
            cl.close()
        except Exception:
            pass

def check_wifi_and_server(self, host=None, port=80, timeout=2.0, retries=2):
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
    if time.ticks_diff(now, self._btn_last_ms) > 100:
        self._btn_last_ms = now
        try:
            self._btn_press_start = now
        except Exception:
            self._btn_press_start = now

def button_pressed(self, clear=True, long_ms=800):
    if not getattr(self, "_btn", None):
        return False
    try:
        if self._btn.value() == 0:
            start = getattr(self, "_btn_press_start", None)
            if start is None:
                self._btn_press_start = time.ticks_ms()
                return False
            dur = time.ticks_diff(time.ticks_ms(), start)
            if dur >= long_ms:
                if clear:
                    self._btn_press_start = None
                return True
        else:
            self._btn_press_start = None
    except Exception:
        return False
    return False

def _scan_rssi_map(self, timeout_ms=2500):
    rssi_map = {}
    try:
        sta = network.WLAN(network.STA_IF)
        sta.active(True)
        t0 = time.ticks_ms()
        res = sta.scan()
        while res is None and time.ticks_diff(time.ticks_ms(), t0) < timeout_ms:
            time.sleep_ms(100)
            try: res = sta.scan()
            except Exception: break
        if not res:
            return rssi_map
        for tup in res:
            try:
                ssid_bytes = tup[0]
                rssi = int(tup[3])
                ssid = ssid_bytes.decode() if isinstance(ssid_bytes, (bytes, bytearray)) else str(ssid_bytes)
                if (ssid not in rssi_map) or (rssi > rssi_map[ssid]):
                    rssi_map[ssid] = rssi
            except Exception:
                continue
    except Exception:
        pass
    return rssi_map

def _prioritize_by_scan(self, nets):
    rssi_map = self._scan_rssi_map()
    if not rssi_map:
        return nets
    with_rssi = []
    without_rssi = []
    for ssid, pwd in nets:
        if ssid in rssi_map:
            with_rssi.append((ssid, pwd, rssi_map[ssid]))
        else:
            without_rssi.append((ssid, pwd))
    with_rssi.sort(key=lambda t: t[2], reverse=True)
    prioritized = [(s, p) for (s, p, _) in with_rssi] + without_rssi
    return prioritized

def run(self):
    SERVER_PORT        = 80
    FALLBACK_PORT      = 8080
    BACKOFF_RETRY_MS   = 500
    BACKOFF_NO_NET_S   = 5
    BACKOFF_ALL_FAIL_S = 2
    HEALTH_OK_SLEEP_S  = 5
    self.log.info("WiFiManager avviato: modalità 'never auto-AP'")
    while True:
        if (not self._setup_mode) and self.button_pressed(clear=True, long_ms=800):
            self.log.info("🔘 Pulsante (long-press) → setup mode")
            break
        result = self.check_wifi_and_server(port=SERVER_PORT)
        if not result.get("server_ok"):
            fallback_res = self.check_wifi_and_server(port=FALLBACK_PORT)
            if fallback_res.get("server_ok"):
                result = fallback_res
        wifi_ok  = result.get("wifi_ok")
        ip       = result.get("ip")
        srv_ok   = result.get("server_ok")
        if not wifi_ok:
            try:
                self.leds.show_connecting()
            except Exception:
                pass
            self._reset_wifi()
            nets = self._load_networks()
            if not nets:
                self.log.info(f"Nessuna rete in {self.wifi_json}. Riprovo tra {BACKOFF_NO_NET_S}s.")
                time.sleep(BACKOFF_NO_NET_S)
                continue
            nets = self._prioritize_by_scan(nets)
            connected = False
            for ssid, pwd in nets:
                if self.button_pressed(clear=True, long_ms=800):
                    self.log.info("🔘 Pulsante durante tentativi → setup mode")
                    connected = False
                    break
                ok, ip_new, reason = self._try_connect(
                    ssid, pwd, timeout_s=15,
                    cancel_cb=lambda: self.button_pressed(clear=False, long_ms=800)
                )
                if ok:
                    self._ap_disable()
                    try:
                        self.leds.show_connected()
                    except Exception:
                        pass
                    self.log.info(f"Connesso a '{ssid}' con IP {ip_new}")
                    try:
                        self._sync_time_once()
                    except Exception:
                        pass
                    try:
                        self._start_server(port=SERVER_PORT, allow_foreground=False)
                    except Exception as e:
                        self.log.info(f"Start server fallito: {e!r}")
                    connected = True
                    break
                else:
                    self.log.info(f"Connessione fallita a '{ssid}' ({reason or 'fail'})")
                    time.sleep_ms(BACKOFF_RETRY_MS)
            if not connected:
                time.sleep(BACKOFF_ALL_FAIL_S)
                continue
        else:
            self._ap_disable()
            if not srv_ok:
                if ip and not (self._port_open(ip, SERVER_PORT) or self._port_open(ip, FALLBACK_PORT)):
                    try:
                        self._start_server(port=SERVER_PORT, allow_foreground=False)
                        time.sleep(1)
                        again = self.check_wifi_and_server(port=SERVER_PORT)
                        if not again.get("server_ok"):
                            again = self.check_wifi_and_server(port=FALLBACK_PORT)
                        if not again.get("server_ok"):
                            self.log.info(f"Server ancora KO: {again.get('error')}")
                    except Exception as e:
                        self.log.info(f"Errore avvio server: {e!r}")
            else:
                try:
                    self.leds.show_connected()
                except Exception:
                    pass
                for _ in range(HEALTH_OK_SLEEP_S):
                    if self.button_pressed(clear=True, long_ms=800):
                        self.log.info("🔘 Pulsante durante idle → setup mode")
                        wifi_ok = False
                        break
                    time.sleep(1)
                else:
                    continue
                break
    self._enter_setup_once()
    while True:
        self.log.info("Loop Access Point attivo (setup)")
        time.sleep(1)

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
WiFiManager._fallback_start_server = _fallback_start_server
WiFiManager.check_wifi_and_server = check_wifi_and_server
WiFiManager._irq_button = _irq_button
WiFiManager.button_pressed = button_pressed
WiFiManager.run = run
WiFiManager._apply_sta_hostname = _apply_sta_hostname
WiFiManager._prioritize_by_scan = _prioritize_by_scan
WiFiManager._scan_rssi_map = _scan_rssi_map
WiFiManager._current_ip = _current_ip
WiFiManager._maybe_start_ftp = _maybe_start_ftp

