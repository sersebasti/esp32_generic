# filename: wifi_connect.py
import network, time, json # type: ignore
from logger import CircularLogger

_log = CircularLogger(path="log.txt", max_bytes=8*1024, echo=True)

# -------- util --------
_STAT_MAP = {
    network.STAT_IDLE       if hasattr(network, "STAT_IDLE") else 0: "IDLE",
    network.STAT_CONNECTING if hasattr(network, "STAT_CONNECTING") else 1: "CONNECTING",
    network.STAT_WRONG_PASSWORD if hasattr(network, "STAT_WRONG_PASSWORD") else 2: "WRONG_PASSWORD",
    network.STAT_NO_AP_FOUND if hasattr(network, "STAT_NO_AP_FOUND") else 3: "NO_AP_FOUND",
    network.STAT_CONNECT_FAIL if hasattr(network, "STAT_CONNECT_FAIL") else 4: "CONNECT_FAIL",
    network.STAT_GOT_IP      if hasattr(network, "STAT_GOT_IP") else 5: "GOT_IP",
}

def _status_str(st):
    return _STAT_MAP.get(st, str(st))


def _config_safe(wlan, **pairs):
    """Set WLAN.config() keys se supportate; ignora le altre."""
    for k, v in pairs.items():
        try:
            wlan.config(**{k: v})
        except Exception:
            pass

def _set_hostname_safe(wlan, host):
    if not host:
        return
    # ESP32 usa di solito 'dhcp_hostname'; su alcuni port può essere 'hostname'
    for key in ("dhcp_hostname", "hostname"):
        try:
            wlan.config(**{key: host})
            return
        except Exception:
            pass

def _get_rssi_safe(wlan):
    try:
        return wlan.status('rssi')
    except Exception:
        return None    

def _networks_from_cfg(cfg):
    """
    Estrae una lista di (ssid, password) da cfg.
    Supporta:
      - campi singoli           ssid/password
      - coppie enumerate        ssid_1/password_1, ssid_2/password_2, ...
      - lista                   networks: [{"ssid":"...","password":"..."}, ...]
    """
    nets = []

    s_single = (cfg.get("ssid") or "").strip()
    if s_single:
        nets.append((s_single, cfg.get("password") or ""))

    idxs = []
    for k in cfg.keys():
        if isinstance(k, str) and k.startswith("ssid_"):
            try: idxs.append(int(k.split("_", 1)[1]))
            except: pass
    for i in sorted(set(idxs)):
        s = (cfg.get("ssid_%d" % i) or "").strip()
        if s:
            nets.append((s, cfg.get("password_%d" % i) or ""))

    lst = cfg.get("networks")
    if isinstance(lst, list):
        for it in lst:
            try:
                s = (it.get("ssid") or "").strip()
                if s:
                    nets.append((s, it.get("password") or ""))
            except: pass

    seen, uniq = set(), []
    for s, p in nets:
        if s in seen: continue
        uniq.append((s, p)); seen.add(s)
    return uniq

def _scan_ssids(sta, max_tries=2):
    """Ritorna mappa ssid -> lista di dict {bssid, channel, rssi} ordinati per rssi."""
    found = {}
    for t in range(max_tries):
        try:
            res = sta.scan()  # [(ssid, bssid, channel, RSSI, authmode, hidden), ...]
        except Exception as e:
            _log.log("WiFi: scan error: %r" % e, "W")
            res = []
        for tup in res or []:
            try:
                ssid = tup[0].decode() if isinstance(tup[0], (bytes, bytearray)) else tup[0]
                ent = {"bssid": tup[1], "channel": tup[2], "rssi": tup[3]}
                found.setdefault(ssid, []).append(ent)
            except Exception:
                pass
        if found: break
        time.sleep_ms(200)
    # ordina per RSSI decrescente
    for k in list(found.keys()):
        found[k].sort(key=lambda x: x["rssi"], reverse=True)
    return found

def connect_from_json(path="wifi.json", timeout=12, force_reconnect=True, retries_per_ssid=2):
    """
    Tenta la connessione Wi-Fi leggendo le reti da 'path'.
    - timeout: secondi per tentativo
    - force_reconnect: scollega se già connesso
    - retries_per_ssid: tentativi per SSID (con piccolo backoff)
    Ritorna: (True, ip) o (False, None)
    """
    try:
        with open(path) as f:
            cfg = json.load(f)
    except Exception as e:
        print("wifi.json error:", e)
        try: _log.log("WiFi: error reading %s: %r" % (path, e), "E")
        except Exception: pass
        return False, None

    host = (cfg.get("hostname") or "").strip() or None
    country = (cfg.get("country") or "IT").strip()  # default IT
    nets = _networks_from_cfg(cfg)
    if not nets:
        print("SSID mancante nel json")
        try: _log.log("WiFi: nessuna rete valida nel json", "E")
        except Exception: pass
        return False, None

    sta = network.WLAN(network.STA_IF)
    sta.active(True)

    # Power-save (su alcune build 8266 non esiste → safe)
    _config_safe(sta, pm=0xa11140)

    # Country (su 8266 spesso non c'è → safe)
    _config_safe(sta, country=country)
    # Log informativo (non sappiamo se applicato, ma utile comunque)
    try: _log.log("WiFi: set country='%s'" % country)
    except Exception: pass

    # Aumenta TX power se disponibile
    for key, val in (("txpower", 78), ("tx_power", 78)):  # ~ max su alcuni port
        try:
            sta.config(**{key: val})
            _log.log("WiFi: tx power set via '%s'=%s" % (key, val))
            break
        except Exception:
            pass

    # Hostname (se supportato)
    _set_hostname_safe(sta, host)
    try:
        if host:
            _log.log("WiFi: set hostname '%s'" % host)
    except Exception:
        pass    

    if force_reconnect and sta.isconnected():
        try: prev_ip = sta.ifconfig()[0]
        except Exception: prev_ip = "?"
        _log.log("WiFi: was connected (ip=%s) -> disconnecting" % prev_ip)
        try: sta.disconnect()
        except Exception as e: _log.log("WiFi: disconnect failed: %r" % e, "W")
        time.sleep(0.2)

    # Scan preliminare per info canale/RSSI
    scan_map = _scan_ssids(sta)
    if scan_map:
        msg = []
        for s in set([n[0] for n in nets]):
            if s in scan_map:
                top = scan_map[s][0]
                msg.append("%s(ch=%s,rssi=%sdBm)" % (s, top["channel"], top["rssi"]))
        if msg:
            _log.log("WiFi: seen SSIDs -> " + ", ".join(msg))

    # Prova le reti
    for (ssid, pwd) in nets:
        # se non rilevata allo scan, logga e usa timeout ridotto al primo tentativo
        seen = scan_map.get(ssid)
        ch = seen[0]["channel"] if seen else None
        rssi = seen[0]["rssi"] if seen else None
        if not seen:
            _log.log("WiFi: '%s' non vista allo scan (provo comunque)" % ssid, "W")
        elif ch in (12, 13):
            _log.log("WiFi: '%s' su canale %d (assicurati country=IT/EU su device & AP)" % (ssid, ch), "W")

        for attempt in range(1, retries_per_ssid+1):
            eff_timeout = timeout if (seen or attempt > 1) else max(5, timeout//2)

            _log.log("WiFi: connecting to '%s' (attempt %d/%d, timeout %ss)%s%s" %
                     (ssid, attempt, retries_per_ssid, eff_timeout,
                      (" ch=%d" % ch) if ch else "",
                      (" rssi=%sdBm" % rssi) if rssi is not None else ""))

            try: sta.disconnect()
            except Exception: pass

            # Nota: su alcuni firmware aiuta dare un piccolo delay prima di connect
            time.sleep_ms(120)
            sta.connect(ssid, pwd)

            t0 = time.ticks_ms()
            while (not sta.isconnected()) and time.ticks_diff(time.ticks_ms(), t0) < eff_timeout * 1000:
                time.sleep(0.2)

            if sta.isconnected():
                # SSID effettivo
                ssid_now = None
                for key in ("essid", "ssid"):
                    try:
                        v = sta.config(key)
                        if isinstance(v, (bytes, bytearray)): v = v.decode()
                        if v: ssid_now = v; break
                    except Exception: pass

                ip, mask, gw, dns = sta.ifconfig()
                rssi_now = _get_rssi_safe(sta)

                if ssid_now and ssid_now != ssid:
                    _log.log("WiFi: connected to '%s' (expected '%s') ip=%s gw=%s%s"
                             % (ssid_now, ssid, ip, gw, (" rssi=%sdBm" % rssi_now) if rssi_now is not None else ""), "W")
                else:
                    _log.log("WiFi: connected to '%s' ip=%s gw=%s dns=%s%s"
                             % (ssid, ip, gw, dns, (" rssi=%sdBm" % rssi_now) if rssi_now is not None else ""))
                print("✅ Connesso! IP:", ip)
                return True, ip

            # fallito
            try: st = sta.status()
            except Exception: st = None
            _log.log("WiFi: connect failed for '%s' (status=%r -> %s)"
                     % (ssid, st, _status_str(st)), "W")

            # backoff breve
            time.sleep_ms(250 + attempt*150)

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

    ap = network.WLAN(network.AP_IF)
    sta = network.WLAN(network.STA_IF)

    # Tentativo 1: AP+STA (non spengo lo STA)
    try:
        ap.active(False)
        time.sleep_ms(80)
        ap.active(True)
        try:
            ap.config(essid=ssid, password=password,
                      authmode=network.AUTH_WPA_WPA2_PSK,
                      channel=channel, hidden=0, max_clients=5)
        except Exception:
            ap.config(essid=ssid, password=password, authmode=network.AUTH_WPA2_PSK)
        try:
            ap.ifconfig(("192.168.4.1","255.255.255.0","192.168.4.1","8.8.8.8"))
        except Exception:
            pass
    except Exception:
        # Fallback: spegni STA e riprova
        try:
            sta.active(False)
        except Exception:
            pass
        ap.active(False)
        time.sleep_ms(80)
        ap.active(True)
        try:
            ap.config(essid=ssid, password=password,
                      authmode=network.AUTH_WPA_WPA2_PSK,
                      channel=channel, hidden=0, max_clients=5)
        except Exception:
            ap.config(essid=ssid, password=password, authmode=network.AUTH_WPA2_PSK)
        try:
            ap.ifconfig(("192.168.4.1","255.255.255.0","192.168.4.1","8.8.8.8"))
        except Exception:
            pass

    _log.log("AP attivo: SSID=%s, IP=%s" % (ssid, ap.ifconfig()[0]))
    print("Access Point creato: SSID=%s, password=%s" % (ssid, password))
    return ap