# wifi/wifi_manager.py
# WiFiManager implementation

import network, time, json, socket, machine  # type: ignore
from wifi.utils import apply_sta_hostname, device_name_from_mac

class _NullLog:
    def info(self, *a, **k):
        try: print(*a)
        except: pass
    warn = info
    error = info

try:
    from wifi.wifi_led_status import LedStatus
except Exception:
    try:
        from wifi_led_status import LedStatus
    except Exception:
        LedStatus = None

# Read button pin and wifi json path from wifi config, with resilient fallbacks
try:
    from wifi.config import AP_BTN_PIN as _CFG_AP_BTN_PIN  # type: ignore
    from wifi.config import WIFI_JSON as _CFG_WIFI_JSON  # type: ignore
except Exception:
    try:
        from config import AP_BTN_PIN as _CFG_AP_BTN_PIN  # type: ignore
        from config import WIFI_JSON as _CFG_WIFI_JSON  # type: ignore
    except Exception:
        _CFG_AP_BTN_PIN = 32
        _CFG_WIFI_JSON = "wifi/wifi.json"

class WiFiManager:
    def __init__(self, wifi_json=None, log=None):
        self.wifi_json = wifi_json or _CFG_WIFI_JSON
        self.log = log or _NullLog()
        self.leds = LedStatus() if LedStatus else _NullLed()
        self._rtc_synced = False
        self._setup_mode = False

        self._AP_BTN_PIN_num = int(_CFG_AP_BTN_PIN)
        self._btn_last_ms = 0
        try:
            self._btn = machine.Pin(self._AP_BTN_PIN_num, machine.Pin.IN, machine.Pin.PULL_UP)
            self._btn.irq(trigger=machine.Pin.IRQ_FALLING, handler=self._irq_button)
        except Exception as e:
            self.log.info(f"Button init failed: {e!r}")
            self._btn = None

    def _sync_time_once(self):
        if self._rtc_synced:
            return
        try:
            import ntptime
            ntptime.host = "pool.ntp.org"
            ntptime.settime()
            self._rtc_synced = True
            try:
                self.log.info("RTC sincronizzato: UTC=%r" % (time.gmtime(),))
            except Exception:
                pass
        except Exception as e:
            self.log.info("NTP sync fallita: %r" % (e,))

    @staticmethod
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
            self.log.info("Impossibile leggere %s: %r" % (self.wifi_json, e))
            return []
        nets = self._networks_from_cfg(cfg)
        if not nets:
            self.log.info("Nessuna rete trovata in %s" % self.wifi_json)
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

    def _ap_enable(self, essid="ESP-SETUP", password=""):
        try:
            if not essid or essid == "ESP-SETUP":
                essid = device_name_from_mac(prefix="ESP32_", fallback="ESP-SETUP", max_len=32)
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
            self.log.info("AP attivo: SSID='%s' IP=%s" % (essid, ip))
            return ip
        except Exception as e:
            self.log.info("AP enable fallito: %r" % (e,))
            return None

    def _ap_disable(self):
        try:
            ap = network.WLAN(network.AP_IF)
            if ap.active():
                ap.active(False)
                self.log.info("AP disattivato")
        except Exception as e:
            self.log.info("AP disable fallito: %r" % (e,))

    def _enter_setup_once(self):
        if self._setup_mode:
            return
        self._setup_mode = True
        self.log.info("Setup mode: STA OFF, AP ON")
        try:
            if hasattr(self.leds, "show_ap"):
                self.leds.show_ap()
        except Exception:
            pass
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
        ip_ap = self._ap_enable()
        if not ip_ap:
            ip_ap = "192.168.4.1"
        try:
            if self._port_open(ip_ap, 80):
                self.log.info("UI WiFi: http://%s/wifi/ui" % ip_ap)
            elif self._port_open(ip_ap, 8080):
                self.log.info("UI WiFi: http://%s:8080/wifi/ui" % ip_ap)
            else:
                self.log.info("UI WiFi: server non raggiungibile su 80/8080")
        except Exception:
            pass

    def _try_connect(self, ssid, pwd, timeout_s=15, cancel_cb=None):
        sta = network.WLAN(network.STA_IF)
        try:
            if not sta.active():
                sta.active(True)
        except Exception as e:
            self.log.info("Errore sta.active(True): %r" % (e,))
            return (False, None, "wifi_init_error")
        try:
            sta.disconnect()
        except Exception:
            pass
        apply_sta_hostname(self.log)
        self.log.info("Tentativo di connessione a rete '%s'..." % ssid)
        try:
            sta.connect(ssid, pwd)
        except Exception as e:
            self.log.info("Errore connect(): %r" % (e,))
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

    def _current_ip(self):
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
            import core.config as _cfg
        except Exception:
            _cfg = None
        enabled = bool(getattr(_cfg, "FTP_AUTOSTART", False)) if _cfg else False
        if not enabled:
            return False
        port = int(getattr(_cfg, "FTP_PORT", 21)) if _cfg else 21
        ip = self._current_ip()
        if ip != "0.0.0.0" and self._port_open(ip, port):
            try:
                self.log.info("FTP gia attivo sulla porta %s" % port)
            except Exception:
                pass
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
            try:
                self.log.info("FTP avviato sulla porta %s" % port)
            except Exception:
                pass
            return True
        except Exception as e:
            try:
                self.log.info("FTP avvio fallito: %r" % (e,))
            except Exception:
                pass
            return False

    def check_wifi_and_server(self, host=None, port=80, timeout=2.0, retries=2):
        try:
            sta = network.WLAN(network.STA_IF)
            wifi_ok = bool(sta.isconnected())
            ip = sta.ifconfig()[0] if wifi_ok else None
        except Exception as e:
            return {"wifi_ok": False, "ip": None, "server_ok": False, "health": None, "error": "wifi_init_error:%r" % (e,)}
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
            try:
                if not sta.active():
                    sta.active(True)
            except Exception:
                return rssi_map
            t0 = time.ticks_ms()
            res = sta.scan()
            while res is None and time.ticks_diff(time.ticks_ms(), t0) < timeout_ms:
                time.sleep_ms(100)
                try:
                    res = sta.scan()
                except Exception:
                    break
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
        try:
            from app.app_logic import run_wifi_loop
            return run_wifi_loop(self)
        except Exception:
            return None

class _NullLed:
    def show_connecting(self): pass
    def show_connected(self):  pass
    # Minimal interface used by WiFiManager; real LEDs handled by LedStatus

WiFiManager._NullLed = _NullLed



