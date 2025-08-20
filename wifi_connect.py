# filename: wifi_connect.py
import network, time, json
from logger import RollingLogger

_log = RollingLogger(path="log.txt", max_bytes=8*1024, backups=1)

def _networks_from_cfg(cfg):
    """
    Estrae una lista di (ssid, password) da cfg.
    Supporta:
      - campi singoli:           ssid / password
      - coppie enumerate:        ssid_1/password_1, ssid_2/password_2, ...
      - lista:                   networks: [{"ssid":"...","password":"..."}, ...]
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
    lst = cfg.get("networks")
    if isinstance(lst, list):
        for it in lst:
            try:
                s = (it.get("ssid") or "").strip()
                if s:
                    nets.append((s, it.get("password") or ""))
            except Exception:
                pass

    # deduplica preservando ordine
    seen = set()
    uniq = []
    for s, p in nets:
        if s in seen:
            continue
        uniq.append((s, p))
        seen.add(s)
    return uniq

def connect_from_json(path="wifi.json", timeout=10, force_reconnect=True):
    """
    Tenta la connessione Wi-Fi leggendo le reti da 'path'.
    - timeout: secondi per ogni rete
    - force_reconnect: scollega se già connesso
    Ritorna: (True, ip) o (False, None)
    """
    try:
        with open(path) as f:
            cfg = json.load(f)
    except Exception as e:
        print("wifi.json error:", e)
        try:
            _log.log("WiFi: error reading %s: %r" % (path, e), "E")
        except Exception:
            pass
        return False, None

    host = (cfg.get("hostname") or "").strip() or None
    nets = _networks_from_cfg(cfg)
    if not nets:
        print("SSID mancante nel json")
        try:
            _log.log("WiFi: nessuna rete valida nel json", "E")
        except Exception:
            pass
        return False, None

    sta = network.WLAN(network.STA_IF)
    sta.active(True)

    # opzionale: disattiva power-save per più stabilità in fase setup
    try:
        sta.config(pm=0xa11140)
    except Exception:
        pass

    # hostname (se supportato)
    if host:
        try:
            sta.config(dhcp_hostname=host)
            _log.log("WiFi: set hostname '%s'" % host)
        except Exception:
            pass

    # se già connesso, scollega per applicare eventuali cambi
    if force_reconnect and sta.isconnected():
        try:
            prev_ip = sta.ifconfig()[0]
        except Exception:
            prev_ip = "?"
        _log.log("WiFi: was connected (ip=%s) -> disconnecting" % prev_ip)
        try:
            sta.disconnect()
        except Exception as e:
            _log.log("WiFi: disconnect failed: %r" % e, "W")
        time.sleep(0.2)

    # prova le reti
    for (ssid, pwd) in nets:
        _log.log("WiFi: connecting to '%s' (timeout %ss)" % (ssid, timeout))
        try:
            sta.disconnect()
        except Exception:
            pass
        sta.connect(ssid, pwd)

        t0 = time.ticks_ms()
        while (not sta.isconnected()) and time.ticks_diff(time.ticks_ms(), t0) < timeout * 1000:
            time.sleep(0.2)

        if sta.isconnected():
            # SSID effettivo (se esposto)
            ssid_now = None
            for key in ("essid", "ssid"):
                try:
                    v = sta.config(key)
                    if isinstance(v, (bytes, bytearray)):
                        v = v.decode()
                    if v:
                        ssid_now = v
                        break
                except Exception:
                    pass

            ip, mask, gw, dns = sta.ifconfig()
            try:
                rssi = sta.status('rssi')
            except Exception:
                rssi = None

            if ssid_now and ssid_now != ssid:
                _log.log(
                    "WiFi: connected to '%s' (expected '%s') ip=%s gw=%s%s" %
                    (ssid_now, ssid, ip, gw, (" rssi=%sdBm" % rssi) if rssi is not None else ""),
                    "W"
                )
            else:
                _log.log(
                    "WiFi: connected to '%s' ip=%s gw=%s dns=%s%s" %
                    (ssid, ip, gw, dns, (" rssi=%sdBm" % rssi) if rssi is not None else "")
                )

            print("✅ Connesso! IP:", ip)
            return True, ip
        else:
            try:
                st = sta.status()
            except Exception:
                st = None
            _log.log("WiFi: connect failed for '%s' (status=%r)" % (ssid, st), "W")
            time.sleep(0.2)

    _log.log("WiFi: all candidates failed", "E")
    print("❌ Connessione fallita su tutte le reti")
    return False, None

def _unique_ssid(base="ESP32_SETUP"):
    """Crea SSID con suffisso MAC (es: ESP32_SETUP_AB12)."""
    try:
        ap = network.WLAN(network.AP_IF); ap.active(True)
        mac = ap.config('mac')  # bytes
        suffix = "%02X%02X" % (mac[-2], mac[-1])
        return "%s_%s" % (base, suffix)
    except Exception:
        return base

def start_ap_mode(ssid=None, password="12345678", channel=6):
    """Accende l'Access Point e RITORNA l'oggetto WLAN(AP)."""
    if not ssid:
        ssid = _unique_ssid("ESP32_SETUP")

    # spegni STA per evitare conflitti
    try:
        sta = network.WLAN(network.STA_IF)
        sta.active(False)
    except Exception:
        pass

    ap = network.WLAN(network.AP_IF)
    ap.active(False)
    time.sleep_ms(100)
    ap.active(True)

    try:
        ap.config(essid=ssid, password=password, authmode=network.AUTH_WPA_WPA2_PSK,
                  channel=channel, hidden=0, max_clients=5)
    except Exception:
        # fallback per firmware più vecchi
        ap.config(essid=ssid, password=password, authmode=network.AUTH_WPA2_PSK)

    try:
        ap.ifconfig(("192.168.4.1","255.255.255.0","192.168.4.1","8.8.8.8"))
    except Exception:
        pass

    _log.log("AP attivo: SSID=%s, IP=%s" % (ssid, ap.ifconfig()[0]))
    print("Access Point creato: SSID=%s, password=%s" % (ssid, password))
    return ap