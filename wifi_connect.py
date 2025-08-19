# filename: wifi_connect.py
import network, time, json
from logger import RollingLogger

_log = RollingLogger(path="log.txt", max_bytes=8*1024, backups=1)

def _networks_from_cfg(cfg):
    """
    Ritorna una lista di tuple (ssid, password) dall'oggetto cfg.

    Formati supportati:
      - campi singoli:           ssid / password
      - coppie enumerate:        ssid_1/password_1, ssid_2/password_2, ...
      - lista di reti:           networks: [{"ssid":"...","password":"..."}, ...]

    Ordine di prova: singolo -> enumerati (ordinati per indice) -> lista.
    Duplicati rimossi mantenendo il primo.
    """
    nets = []

    # forma singola
    s_single = (cfg.get("ssid") or "").strip()
    if s_single:
        nets.append((s_single, cfg.get("password") or ""))

    # forma enumerata ssid_N/password_N
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

    # forma lista
    lst = cfg.get("networks")
    if isinstance(lst, list):
        for it in lst:
            try:
                s = (it.get("ssid") or "").strip()
                if s:
                    nets.append((s, it.get("password") or ""))
            except Exception:
                pass

    # deduplica preservando l'ordine
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

    - timeout:         secondi concessi per *ogni rete* provata
    - force_reconnect: se già connesso fa disconnect() prima di tentare

    Ritorna: (True, ip) oppure (False, None)
    """
    # carica config
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

    # hostname (se supportato)
    if host:
        try:
            sta.config(dhcp_hostname=host)
            _log.log("WiFi: set hostname '%s'" % host)
        except Exception:
            pass

    # se già connesso, scollega (per applicare davvero eventuale cambio rete)
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

    # prova reti in ordine
    for (ssid, pwd) in nets:
        _log.log("WiFi: connecting to '%s' (timeout %ss)" % (ssid, timeout))
        try:
            sta.disconnect()
        except Exception:
            pass
        sta.connect(ssid, pwd)

        t0 = time.ticks_ms()
        while not sta.isconnected() and time.ticks_diff(time.ticks_ms(), t0) < timeout * 1000:
            time.sleep(0.2)

        if sta.isconnected():
            # SSID reale (se esposto)
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
            st = None
            try:
                st = sta.status()
            except Exception:
                pass
            _log.log("WiFi: connect failed for '%s' (status=%r)" % (ssid, st), "W")
            time.sleep(0.2)

    _log.log("WiFi: all candidates failed", "E")
    print("❌ Connessione fallita su tutte le reti")
    return False, None