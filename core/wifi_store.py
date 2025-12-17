# wifi_store.py
# Utilità per leggere/scrivere wifi.json e gestire le reti Wi‑Fi (scan, add, delete)
# Compatibile con MicroPython (ujson, network)

import ujson as json
import network
from core.config import WIFI_JSON

# ---------- Lettura/Scrittura file ----------

def read_all(path=None):
    """Legge wifi.json; se mancante, ritorna {}."""
    try:
        p = path or WIFI_JSON
        with open(p) as f:
            return json.load(f)
    except Exception:
        return {}

def write_all(cfg, path=None):
    """Scrive wifi.json sovrascrivendo il contenuto."""
    p = path or WIFI_JSON
    with open(p, "w") as f:
        json.dump(cfg, f)

# ---------- Normalizzazione formati ----------

def _format_of(cfg):
    """Rileva il formato: 'networks' (lista di dict) o 'legacy' (ssid_1/password_1)."""
    return "networks" if isinstance(cfg.get("networks"), list) else "legacy"

def as_list(cfg):
    """
    Ritorna (fmt, lst) dove:
      - fmt ∈ {'networks','legacy'}
      - lst = [(ssid, password), ...] in ordine di priorità
    """
    fmt = _format_of(cfg)
    out = []
    if fmt == "networks":
        for n in (cfg.get("networks") or []):
            ssid = (n.get("ssid") or "").strip()
            if ssid:
                out.append((ssid, n.get("password") or ""))
    else:
        pairs = []
        for k in cfg.keys():
            if isinstance(k, str) and k.startswith("ssid_"):
                try:
                    idx = int(k.split("_", 1)[1])
                except Exception:
                    idx = 0
                ssid = (cfg.get(k) or "").strip()
                if ssid:
                    pwd = cfg.get("password_%d" % idx, "")
                    pairs.append((idx, ssid, pwd))
        pairs.sort(key=lambda t: t[0] or 0)
        out = [(ssid, pwd) for _, ssid, pwd in pairs]
    return fmt, out

def set_list(cfg, fmt, items):
    """
    Scrive items = [(ssid, password), ...] nel formato indicato,
    senza toccare altri campi del JSON.
    """
    if fmt == "networks":
        cfg["networks"] = [{"ssid": s, "password": p} for (s, p) in items]
    else:
        # pulisci chiavi legacy esistenti
        for k in list(cfg.keys()):
            if isinstance(k, str) and (k.startswith("ssid_") or k.startswith("password_")):
                try:
                    del cfg[k]
                except Exception:
                    pass
        for i, (s, p) in enumerate(items, start=1):
            cfg["ssid_%d" % i] = s
            cfg["password_%d" % i] = p

# ---------- Operazioni di alto livello ----------

def configured_networks_no_password(path=None):
    """
    Ritorna lista di dict per UI/API, senza password:
      [{"ssid": "...", "priority": 1, "connected": bool}, ...]
    """
    import sys
    cfg = read_all(path)
    fmt, lst = as_list(cfg)

    # SSID corrente (se connesso in STA)
    current = None
    try:
        sta = network.WLAN(network.STA_IF)
        for key in ("essid", "ssid"):
            try:
                val = sta.config(key)
                if isinstance(val, (bytes, bytearray)):
                    val = val.decode()
                if val:
                    current = val
                    break
            except Exception:
                pass
    except Exception:
        pass

    out = []
    for i, (s, _p) in enumerate(lst, start=1):
        out.append({"ssid": s, "priority": i, "connected": (s == current)})
    return out

def add_network(ssid, password, priority=None, path=None):
    """
    Aggiunge una rete. Se 'priority' è valida (1..len+1) inserisce in posizione,
    altrimenti accoda. Ritorna (ok:bool, message:str).
    """
    ssid = (ssid or "").strip()
    if not ssid:
        return False, "missing_ssid"
    password = password or ""

    cfg = read_all(path)
    fmt, lst = as_list(cfg)

    # già presente?
    for (s, _p) in lst:
        if s == ssid:
            return False, "exists"

    if isinstance(priority, int) and 1 <= priority <= (len(lst) + 1):
        lst.insert(priority - 1, (ssid, password))
    else:
        lst.append((ssid, password))

    set_list(cfg, fmt, lst)
    write_all(cfg, path)
    return True, "added"

def delete_network(ssid, path=None):
    """
    Elimina una rete per SSID. Ritorna (ok:bool, message:str).
    """
    ssid = (ssid or "").strip()
    if not ssid:
        return False, "missing_ssid"

    cfg = read_all(path)
    fmt, lst = as_list(cfg)

    new = [(s, p) for (s, p) in lst if s != ssid]
    if len(new) == len(lst):
        return False, "not_found"

    set_list(cfg, fmt, new)
    write_all(cfg, path)
    return True, "deleted"

# ---------- Scan reti ----------

def _auth_name(code):
    try:
        return {
            0: "OPEN",
            1: "WEP",
            2: "WPA-PSK",
            3: "WPA2-PSK",
            4: "WPA/WPA2-PSK",
            5: "WPA2-ENT",
        }.get(int(code), str(code))
    except Exception:
        return str(code)

def scan():
    """
    Ritorna lista di reti disponibili ordinate per RSSI decrescente:
      [{"ssid": "...", "rssi": -55, "auth": "WPA2-PSK", "open": False}, ...]
    """
    nets = []
    try:
        sta = network.WLAN(network.STA_IF)
        sta.active(True)
        raw = sta.scan()  # [(ssid,bssid,channel,rssi,auth,hidden), ...]
        seen = set()
        for t in raw:
            try:
                ssid = t[0].decode() if isinstance(t[0], (bytes, bytearray)) else str(t[0])
                if not ssid or ssid in seen:
                    continue
                seen.add(ssid)
                nets.append({
                    "ssid": ssid,
                    "rssi": int(t[3]),
                    "auth": _auth_name(t[4]),
                    "open": (int(t[4]) == 0),
                })
            except Exception:
                pass
        nets.sort(key=lambda x: x.get("rssi", -999), reverse=True)
    except Exception:
        pass
    return nets
