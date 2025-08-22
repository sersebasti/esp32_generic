# status_server.py (MicroPython)
import adc_scope
import socket, time, ujson, network, ubinascii, gc

def _get_ip_sta():
    try:
        sta = network.WLAN(network.STA_IF)
        if sta.isconnected():
            return sta.ifconfig()[0]
    except Exception:
        pass
    return None

def _get_ssid():
    try:
        sta = network.WLAN(network.STA_IF)
        for key in ("essid", "ssid"):
            v = sta.config(key)
            if isinstance(v, (bytes, bytearray)):
                v = v.decode()
            if v:
                return v
    except Exception:
        pass
    return None

def _rssi():
    try:
        return network.WLAN(network.STA_IF).status('rssi')
    except Exception:
        return None

def _mac_sta():
    try:
        mac = network.WLAN(network.STA_IF).config('mac')
        return ubinascii.hexlify(mac, b':').decode()
    except Exception:
        return "unknown"

def _uptime_s():
    try:
        # ticks_ms overflows, ma per avere secondi correnti basta questo
        return time.ticks_ms() // 1000
    except Exception:
        return 0

def _read_meta():
    # opzionale: solo per hostname
    try:
        import ujson
        with open("wifi.json") as f:
            cfg = ujson.load(f)
        return {
            "hostname": (cfg.get("hostname") or "esp32").strip()
        }
    except Exception:
        return {"hostname":"esp32"}

def _read_config_networks():
    """
    Ritorna una lista di reti dal wifi.json SENZA password.
    Supporta sia:
      - {"networks":[{"ssid":"A","password":"x"}, ...]}
      - {"ssid_1":"A","password_1":"x","ssid_2":"B","password_2":"y", ...}
    """
    out = []
    try:
        with open("wifi.json") as f:
            cfg = ujson.load(f)
    except Exception:
        return out

    nets = cfg.get("networks")
    if isinstance(nets, list):
        for i, n in enumerate(nets):
            ssid = (n.get("ssid") or "").strip()
            if ssid:
                out.append({"ssid": ssid, "priority": i + 1})
    else:
        for k in cfg.keys():
            if isinstance(k, str) and k.startswith("ssid_"):
                try:
                    idx = int(k.split("_", 1)[1])
                except Exception:
                    idx = 0
                ssid = (cfg.get(k) or "").strip()
                if ssid:
                    out.append({"ssid": ssid, "priority": idx})
        out.sort(key=lambda x: x.get("priority", 0))

    current = _get_ssid()
    for n in out:
        n["connected"] = (n["ssid"] == current)
    return out

# --- helpers per POST JSON (senza toccare le GET esistenti) ---
def _read_post_json(req, cl, max_len=4096):
    """
    Estrae il body JSON da una richiesta già letta in 'req'.
    Se Content-Length indica più dati, li legge dal socket.
    Ritorna dict.
    """
    try:
        head, body = req.split(b"\r\n\r\n", 1)
    except ValueError:
        head, body = req, b""
    content_length = 0
    for line in head.split(b"\r\n")[1:]:
        L = line.strip().lower()
        if L.startswith(b"content-length:"):
            try:
                content_length = int(L.split(b":", 1)[1].strip())
            except Exception:
                content_length = 0
            break
    # completa il body se serve
    while len(body) < content_length and len(body) < max_len:
        chunk = cl.recv(min(512, content_length - len(body)))
        if not chunk:
            break
        body += chunk
    if content_length and len(body) < content_length:
        raise ValueError("body_incomplete")
    if not body:
        raise ValueError("empty_body")
    return ujson.loads(body.decode())

def _cfg_read_all():
    try:
        with open("wifi.json") as f:
            return ujson.load(f)
    except Exception:
        return {}

def _cfg_write_all(cfg):
    with open("wifi.json", "w") as f:
        ujson.dump(cfg, f)

def _cfg_format(cfg):
    return "networks" if isinstance(cfg.get("networks"), list) else "legacy"

def _cfg_get_list(cfg):
    """Ritorna lista [(ssid,pwd)] e formato."""
    fmt = _cfg_format(cfg)
    lst = []
    if fmt == "networks":
        for n in (cfg.get("networks") or []):
            ssid = (n.get("ssid") or "").strip()
            pwd  = n.get("password") or ""
            if ssid:
                lst.append((ssid, pwd))
    else:
        pairs = []
        for k in cfg.keys():
            if isinstance(k, str) and k.startswith("ssid_"):
                try: idx = int(k.split("_",1)[1])
                except: idx = 0
                ssid = (cfg.get(k) or "").strip()
                if ssid:
                    pwd = cfg.get("password_%d" % idx, "")
                    pairs.append((idx, ssid, pwd))
        pairs.sort(key=lambda t: t[0] or 0)
        lst = [(ssid, pwd) for _, ssid, pwd in pairs]
    return fmt, lst

def _cfg_set_list(cfg, fmt, items):
    """items = [(ssid,pwd)] riscrive nel formato originale senza toccare altri campi."""
    if fmt == "networks":
        cfg["networks"] = [{"ssid": s, "password": p} for (s, p) in items]
    else:
        # pulisci vecchie chiavi ssid_N/password_N
        to_del = []
        for k in list(cfg.keys()):
            if isinstance(k, str) and (k.startswith("ssid_") or k.startswith("password_")):
                to_del.append(k)
        for k in to_del:
            try: del cfg[k]
            except: pass
        # riscrivi contiguo da 1..N
        for i, (s, p) in enumerate(items, start=1):
            cfg["ssid_%d" % i] = s
            cfg["password_%d" % i] = p

def _add_network(ssid, password, priority=None):
    ssid = (ssid or "").strip()
    if not ssid:
        return False, "missing_ssid", None, 0
    password = password or ""
    cfg = _cfg_read_all()
    fmt, lst = _cfg_get_list(cfg)

    # già presente?
    for (s, _) in lst:
        if s == ssid:
            return False, "exists", fmt, len(lst)

    # inserimento
    if isinstance(priority, int) and priority >= 1 and priority <= (len(lst)+1):
        lst.insert(priority-1, (ssid, password))
    else:
        lst.append((ssid, password))

    _cfg_set_list(cfg, fmt, lst)
    _cfg_write_all(cfg)
    return True, "added", fmt, len(lst)

def _delete_network(ssid):
    ssid = (ssid or "").strip()
    if not ssid:
        return False, "missing_ssid", None, 0
    cfg = _cfg_read_all()
    fmt, lst = _cfg_get_list(cfg)

    new = [(s, p) for (s, p) in lst if s != ssid]
    if len(new) == len(lst):
        return False, "not_found", fmt, len(lst)

    _cfg_set_list(cfg, fmt, new)
    _cfg_write_all(cfg)
    return True, "deleted", fmt, len(new)

_HTTP_200_JSON = (
    b"HTTP/1.1 200 OK\r\n"
    b"Content-Type: application/json\r\n"
    b"Cache-Control: no-store\r\n"
    b"Access-Control-Allow-Origin: *\r\n"
    b"Connection: close\r\n\r\n"
)

_HTTP_200_HTML = (
    b"HTTP/1.1 200 OK\r\n"
    b"Content-Type: text/html; charset=utf-8\r\n"
    b"Cache-Control: no-store\r\n"
    b"Access-Control-Allow-Origin: *\r\n"
    b"Connection: close\r\n\r\n"
)

_HTTP_400 = b"HTTP/1.1 400 Bad Request\r\nContent-Type: text/plain\r\nCache-Control: no-store\r\nConnection: close\r\n\r\nBad Request"


def _parse_path(req_line):
    try:
        parts = req_line.split(" ")
        method = parts[0]
        path = parts[1]
        return method, path
    except Exception:
        return "GET", "/"

def start_status_server(preferred_port=80, fallback_port=8080, verbose=True):
    meta = _read_meta()
    bound = None
    s = socket.socket()
    try:
        try:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        except Exception:
            pass

        try:
            s.bind(("0.0.0.0", preferred_port))
            bound = preferred_port
        except OSError:
            s.bind(("0.0.0.0", fallback_port))
            bound = fallback_port

        s.listen(2)
        s.settimeout(0.5)

        if verbose:
            ip = _get_ip_sta() or "0.0.0.0"
            print("Status server su http://%s:%d/status" % (ip, bound))

        while True:
            try:
                cl, addr = s.accept()
            except OSError:
                continue
            try:
                cl.settimeout(1.0)
                req = cl.recv(1024)
                if not req:
                    cl.close(); continue
                line = req.split(b"\r\n", 1)[0].decode("utf-8", "ignore")
                method, path = _parse_path(line)

                if method == "GET" and path.startswith("/health"):
                    cl.send(_HTTP_200_TXT)

                elif method == "GET" and path.startswith("/status"):
                    payload = {
                        "name": meta["hostname"],
                        "ip": _get_ip_sta(),
                        "ssid": _get_ssid(),
                        "rssi": _rssi(),
                        "mac_sta": _mac_sta(),
                        "uptime_s": _uptime_s(),
                        "heap_free": gc.mem_free()
                    }
                    cl.send(_HTTP_200_JSON + ujson.dumps(payload).encode())

                elif method == "GET" and path.startswith("/wifi/list"):
                    payload = {
                        "hostname": meta["hostname"],
                        "configured_networks": _read_config_networks()
                    }
                    cl.send(_HTTP_200_JSON + ujson.dumps(payload).encode())

                elif method == "POST" and path.startswith("/wifi/add"):
                    try:
                        body = _read_post_json(req, cl)
                        ssid = body.get("ssid")
                        password = body.get("password")
                        prio = body.get("priority", None)
                        ok, msg, fmt, count = _add_network(ssid, password, prio if isinstance(prio, int) else None)
                        resp = {"ok": ok, "message": msg, "format": fmt, "count": count}
                        cl.send(_HTTP_200_JSON + ujson.dumps(resp).encode())
                    except Exception as e:
                        cl.send(_HTTP_200_JSON + ujson.dumps({"ok": False, "message": "invalid_request"}).encode())

                elif method == "POST" and path.startswith("/wifi/delete"):
                    try:
                        body = _read_post_json(req, cl)
                        ssid = body.get("ssid")
                        ok, msg, fmt, count = _delete_network(ssid)
                        resp = {"ok": ok, "message": msg, "format": fmt, "count": count}
                        cl.send(_HTTP_200_JSON + ujson.dumps(resp).encode())
                    except Exception as e:
                        cl.send(_HTTP_200_JSON + ujson.dumps({"ok": False, "message": "invalid_request"}).encode())

                elif method == "GET" and path.startswith("/adc/scope_counts"):
                    if not adc_scope:
                        cl.send(_HTTP_200_JSON + b'{"ok":false,"err":"adc_scope_module_missing"}'); 
                        continue
                    n = 1024; sr = 4000
                    if "?" in path:
                        try:
                            q = path.split("?",1)[1]
                            for p in q.split("&"):
                                if "=" in p:
                                    k,v = p.split("=",1)
                                    if k == "n":  n = int(v)
                                    if k in ("sr","sample_rate_hz"): sr = int(v)
                        except Exception:
                            pass
                    payload = adc_scope.json_dump_counts(n=n, sample_rate_hz=sr)
                    cl.send(_HTTP_200_JSON + payload)
                    
            
                    
                

                else:
                    cl.send(_HTTP_400)
            except Exception:
                try: cl.close()
                except Exception: pass
                continue
            finally:
                try: cl.close()
                except Exception: pass
    finally:
        try: s.close()
        except Exception: pass
        
        
        
        
        
'''
# lista reti configurate
curl http://<IP-ESP>/wifi/list

# aggiungi (append)
curl -X POST http://<IP-ESP>/wifi/add \
  -H "Content-Type: application/json" \
  -d '{"ssid":"NuovaRete","password":"segretissima"}'

# aggiungi in testa (priority=1)
curl -X POST http://<IP-ESP>/wifi/add \
  -H "Content-Type: application/json" \
  -d '{"ssid":"RetePrioritaria","password":"pwd","priority":1}'

# cancella
curl -X POST http://<IP-ESP>/wifi/delete \
  -H "Content-Type: application/json" \
  -d '{"ssid":"NuovaRete"}'
'''

