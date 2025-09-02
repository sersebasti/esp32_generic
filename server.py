# status_server.py (MicroPython)
import socket, time, ujson, network, ubinascii, gc, math, adc_scope, wifi_ui
import wifi_config as wcfg

from http_consts import (
    _HTTP_200_JSON, _HTTP_200_HTML, _HTTP_400,
    _HTTP_204_CORS, _HTTP_200_JSON_CORS
)
import fs_api

BUSY = {"v": False}   # lock globale anti-overlap, mutabile
version = "1.0.0"

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

def _hdr_get(req_bytes, name_lower):
    """Estrae il valore dell'header (in minuscolo), es. b'content-length'."""
    try:
        head = req_bytes.split(b"\r\n\r\n", 1)[0]
        for line in head.split(b"\r\n")[1:]:
            L = line.lower()
            if L.startswith(name_lower + b":"):
                return line.split(b":", 1)[1].strip()
    except:
        pass
    return None

def _body_initial_and_len(req_bytes):
    """Ritorna (body_gia_letto, content_length). Se manca CL → (None, None)."""
    try:
        head, body0 = req_bytes.split(b"\r\n\r\n", 1)
    except ValueError:
        return b"", 0
    v = _hdr_get(req_bytes, b"content-length")
    if v is None:
        return None, None
    try:
        total = int(v)
    except:
        total = 0
    return body0, total


def _parse_path(req_line):
    try:
        parts = req_line.split(" ")
        method = parts[0]
        path = parts[1]
        return method, path
    except Exception:
        return "GET", "/"


# --- Calibrazione: util ---
def _cal_load():
    try:
        import ujson
        with open("calibrate.json") as f:
            return ujson.load(f)
    except:
        return {}

def _cal_save(d):
    import ujson
    with open("calibrate.json", "w") as f:
        ujson.dump(d, f)

def _rms_with_baseline(arr, baseline):
    # RMS della sola componente AC, usando baseline fisso
    s = 0.0
    for v in arr:
        d = v - baseline
        s += d * d
    from math import sqrt
    return sqrt(s / len(arr))

def _fit_k(points):
    # regressione ai minimi quadrati VINCOLATA all'origine (amp = k * rms_counts)
    sxy = 0.0
    sxx = 0.0
    for p in points:
        a = float(p["amps"])
        r = float(p["rms_counts"])
        sxy += a * r
        sxx += r * r
    return (sxy / sxx) if sxx > 0 else 0.0

def start_server(preferred_port=80, fallback_port=8080, verbose=True):
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
        
        BUSY["v"] = False

       
        while True:
            try:
                cl, addr = s.accept()
            except OSError:
                continue
            try:
                cl.settimeout(3.0)
                req = cl.recv(1024)
                if not req:
                    cl.close(); continue
                line = req.split(b"\r\n", 1)[0].decode("utf-8", "ignore")
                method, path = _parse_path(line)

                if method == "OPTIONS":
                    # Preflight CORS: permette ai browser di fare POST/PUT da pagine locali
                    cl.send(_HTTP_204_CORS)
                    continue

                if method == "GET" and path.startswith("/health"):
                    cl.send(_HTTP_200_JSON + b'{"ok":true}')    

                elif method == "GET" and path.startswith("/status"):
                    payload = {
                        "version": version,
                        "name": meta["hostname"],
                        "ip": _get_ip_sta(),
                        "ssid": _get_ssid(),
                        "rssi": _rssi(),
                        "mac_sta": _mac_sta(),
                        "uptime_s": _uptime_s(),
                        "heap_free": gc.mem_free()
                    }
                    cl.send(_HTTP_200_JSON + ujson.dumps(payload).encode())

                elif method == "GET" and path.startswith("/wifi/ui"):
                    cl.send(_HTTP_200_HTML + wifi_ui.page())


                                # ---- ENDPOINTS Wi-Fi ----
                elif method == "GET" and path.startswith("/wifi/scan"):
                    # Elenco reti disponibili (scan della STA)
                    payload = wcfg.scan()
                    cl.send(_HTTP_200_JSON + ujson.dumps(payload).encode())

                elif method == "GET" and path.startswith("/wifi/list"):
                    # Elenco reti configurate su wifi.json (senza password)
                    payload = {
                        "configured_networks": wcfg.configured_networks_no_password()
                    }
                    cl.send(_HTTP_200_JSON + ujson.dumps(payload).encode())

                elif method == "POST" and path.startswith("/wifi/add"):
                    # Body JSON: {"ssid":"...", "password":"...", "priority": <int|omesso>}
                    try:
                        body = _read_post_json(req, cl)
                        ok, msg = wcfg.add_network(
                            body.get("ssid"),
                            body.get("password"),
                            body.get("priority")
                        )
                        cl.send(_HTTP_200_JSON + ujson.dumps({"ok": ok, "message": msg}).encode())
                    except Exception:
                        cl.send(_HTTP_200_JSON + ujson.dumps({"ok": False, "message": "invalid_request"}).encode())

                elif method == "POST" and path.startswith("/wifi/delete"):
                    # Body JSON: {"ssid":"..."}
                    try:
                        body = _read_post_json(req, cl)
                        ok, msg = wcfg.delete_network(body.get("ssid"))
                        cl.send(_HTTP_200_JSON + ujson.dumps({"ok": ok, "message": msg}).encode())
                    except Exception:
                        cl.send(_HTTP_200_JSON + ujson.dumps({"ok": False, "message": "invalid_request"}).encode())

                elif method == "GET" and path.startswith("/adc/scope_counts"):
                    if not adc_scope:
                        cl.send(_HTTP_200_JSON + b'{"ok":false,"err":"adc_scope_module_missing"}')
                    else:
                        if BUSY["v"]:
                            cl.send(_HTTP_200_JSON + b'{"ok":false,"err":"busy"}')
                        else:
                            BUSY["v"] = True
                            try:
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
                                cl.send(_HTTP_200_JSON + payload.encode())
                            finally:
                                BUSY["v"] = False
                    
                elif method == "GET" and path.startswith("/calibrate"):
                    # default acquisizione
                    n = 1600
                    sr = 4000
                    amp = None

                    if "?" in path:
                        q = path.split("?", 1)[1]
                        for p in q.split("&"):
                            if "=" in p:
                                k, v = p.split("=", 1)
                                if k == "n": n = int(v)
                                elif k in ("sr", "sample_rate_hz"): sr = int(v)
                                elif k == "amp":
                                    try:
                                        amp = float(v)
                                    except:
                                        amp = None

                    cal = _cal_load()

                    # Nessun parametro: restituisci lo stato
                    if amp is None:
                        if "points" not in cal: cal["points"] = []
                        resp = {"ok": True, "cal": cal,
                                "hint": "usa /calibrate?amp=0 per baseline, /calibrate?amp=<A> per aggiungere un punto"}
                        cl.send(_HTTP_200_JSON + ujson.dumps(resp).encode())

                    # amp == 0: salva baseline (media a riposo)
                    elif amp == 0.0:
                        if BUSY["v"]:
                            cl.send(_HTTP_200_JSON + b'{"ok":false,"err":"busy"}')
                        else:
                            BUSY["v"] = True
                            try:
                                arr, sr = adc_scope.sample_counts(n, sr)
                                baseline = sum(arr) / len(arr)
                                cal["baseline_mean"] = round(baseline, 2)
                                cal["n0"] = len(arr); cal["sr0"] = sr
                                if "points" not in cal: cal["points"] = []
                                _cal_save(cal)
                                resp = {"ok": True, "saved": {"baseline_mean": cal["baseline_mean"], "n0": cal["n0"], "sr0": cal["sr0"]}}
                                cl.send(_HTTP_200_JSON + ujson.dumps(resp).encode())
                            finally:
                                BUSY["v"] = False

                    # amp > 0: acquisisci RMS (detrend con baseline) e aggiungi punto, poi rifitta k
                    else:
                        if BUSY["v"]:
                            cl.send(_HTTP_200_JSON + b'{"ok":false,"err":"busy"}')
                        else:
                            BUSY["v"] = True
                            try:
                                arr, sr = adc_scope.sample_counts(n, sr)
                                baseline = float(cal.get("baseline_mean", sum(arr)/len(arr)))  # fallback se manca
                                rms = _rms_with_baseline(arr, baseline)
                                pt = {"amps": float(amp), "rms_counts": round(rms, 2)}
                                pts = cal.get("points", [])
                                pts.append(pt)
                                cal["points"] = pts
                                k = _fit_k(pts)  # A per count
                                cal["k_A_per_count"] = round(k, 9)
                                _cal_save(cal)

                                mn = min(arr); mx = max(arr)
                                clipping = (mn < 50) or (mx > 4040)
                                resp = {
                                    "ok": True,
                                    "added": pt,
                                    "k_A_per_count": cal["k_A_per_count"],
                                    "num_points": len(pts),
                                    "baseline_mean": round(baseline, 2),
                                    "min": int(mn), "max": int(mx), "clipping": bool(clipping)
                                }
                                cl.send(_HTTP_200_JSON + ujson.dumps(resp).encode())
                            finally:
                                BUSY["v"] = False           
                    
                elif method == "GET" and path.startswith("/amps"):
                    if BUSY["v"]:
                        cl.send(_HTTP_200_JSON + b'{"ok":false,"err":"busy"}')
                    else:
                        BUSY["v"] = True
                        try:
                            n = 1600; sr = 4000
                            if "?" in path:
                                q = path.split("?", 1)[1]
                                for p in q.split("&"):
                                    if "=" in p:
                                        k, v = p.split("=", 1)
                                        if k == "n": n = int(v)
                                        elif k in ("sr", "sample_rate_hz"): sr = int(v)

                            cal = _cal_load()
                            k = float(cal.get("k_A_per_count", 0.0))
                            if k <= 0:
                                cl.send(_HTTP_200_JSON + b'{"ok":false,"err":"no_model"}')
                            else:
                                arr, sr = adc_scope.sample_counts(n, sr)
                                baseline = float(cal.get("baseline_mean", sum(arr)/len(arr)))
                                rms = _rms_with_baseline(arr, baseline)
                                amps = k * rms
                                mn = min(arr); mx = max(arr)
                                clipping = (mn < 50) or (mx > 4040)
                                out = {
                                    "ok": True,
                                    "amps_rms": round(amps, 3),
                                    "rms_counts": round(rms, 2),
                                    "baseline_mean": round(baseline, 2),
                                    "min": int(mn), "max": int(mx), "clipping": bool(clipping)
                                }
                                cl.send(_HTTP_200_JSON + ujson.dumps(out).encode())
                        finally:
                            BUSY["v"] = False

                
                elif method == "POST" and path.startswith("/calibrate/delete"):
                    try:
                        body = _read_post_json(req, cl)
                        idx = body.get("index", None)
                        amp = body.get("amps", None)
                        rms = body.get("rms_counts", None)

                        cal = _cal_load()
                        pts = cal.get("points", []) or []

                        removed = None

                        # 1) remove by index if provided
                        if isinstance(idx, int) and 0 <= idx < len(pts):
                            removed = pts.pop(idx)
                        # 2) fallback: remove by exact pair match
                        elif (amp is not None) and (rms is not None):
                            for i, p in enumerate(pts):
                                try:
                                    if float(p.get("amps")) == float(amp) and float(p.get("rms_counts")) == float(rms):
                                        removed = pts.pop(i)
                                        break
                                except Exception:
                                    pass

                        if removed is None:
                            cl.send(_HTTP_200_JSON_CORS + ujson.dumps({"ok": False, "err": "not_found"}).encode())
                        else:
                            # recompute k if points remain
                            cal["points"] = pts
                            if pts:
                                k = _fit_k(pts)
                                cal["k_A_per_count"] = round(k, 9)
                            else:
                                cal["k_A_per_count"] = 0.0
                            _cal_save(cal)
                            resp = {
                                "ok": True,
                                "removed": removed,
                                "num_points": len(pts),
                                "k_A_per_count": cal.get("k_A_per_count", 0.0)
                            }
                            cl.send(_HTTP_200_JSON_CORS + ujson.dumps(resp).encode())
                    except Exception:
                        try:
                            cl.send(_HTTP_200_JSON_CORS + b'{"ok":false,"err":"invalid_request"}')
                        except Exception:
                            pass

                elif method == "POST" and path.startswith("/calibrate/reset"):
                    try:
                        import os
                        os.remove("calibrate.json")
                    except:
                        pass
                    cl.send(_HTTP_200_JSON + b'{"ok":true}')

                elif path.startswith("/fs/"):
                    # delega a fs_api
                    handled = fs_api.handle(cl, method, path, req, _read_post_json, _body_initial_and_len)
                    if not handled:
                        cl.send(_HTTP_400)
                    continue

                elif method == "POST" and path.startswith("/reboot"):
                    cl.send(_HTTP_200_JSON + b'{"ok":true}')
                    try: cl.close()
                    except: pass
                    import machine # type: ignore
                    machine.reset()            


                else:
                    cl.send(_HTTP_400)
            except Exception:
                try: cl.close()
                except Exception: pass
                continue
            finally:
                try: cl.close()
                except Exception: pass
                gc.collect()
    finally:
        try: s.close()
        except Exception: pass
    
