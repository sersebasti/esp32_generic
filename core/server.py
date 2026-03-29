import socket, gc, ujson, network
from core.http_consts import (_HTTP_200_JSON, _HTTP_200_HTML, _HTTP_400, _HTTP_204_CORS)
try:
    from core.busy_lock import set_busy
except Exception:
    from busy_lock import set_busy
from core import status_api, wifi_api, system_api
try:
    import scope.adc_api as adc_api
except Exception:
    adc_api = None
try:
    import fs.api as fs_api
except Exception:
    fs_api = None
try:
    import power_sensors.power_sensors_api as power_sensors_api
except Exception:
    power_sensors_api = None
try:
    import my_webrepl.webrepl_api as webrepl_api
except Exception:
    webrepl_api = None

from core.config import feature_enabled

def _hdr_get(req_bytes, name_lower):
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
    try:
        head, body0 = req_bytes.split(b"\r\n\r\n", 1)
    except ValueError:
        return b"", 0
    v = _hdr_get(req_bytes, b"content-length")
    if v is None:
        return body0, None
    try:
        return body0, int(v)
    except:
        return body0, None

def _read_post_json(req, cl, max_len=4096):
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

def _parse_path(line):
    try:
        parts = line.split(" ")
        method = parts[0]
        path = parts[1]
        # Alcuni client (es. captive portal) inviano target assoluto:
        # GET http://192.168.4.1/wifi/ui HTTP/1.1
        # Normalizza sempre a path origin-form: /wifi/ui
        if path.startswith("http://") or path.startswith("https://"):
            slash = path.find("/", path.find("://") + 3)
            if slash >= 0:
                path = path[slash:]
            else:
                path = "/"
        if not path.startswith("/"):
            path = "/" + path
        return method, path
    except Exception:
        return "GET", "/"

def _client_ip(addr):
    try:
        if isinstance(addr, tuple) and len(addr) > 0:
            return str(addr[0])
    except Exception:
        pass
    return "?"

def start_server(preferred_port=80, fallback_port=8080, verbose=True):
    try:
        set_busy(False)
    except Exception:
        pass
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
            try:
                sta = network.WLAN(network.STA_IF)
                ip = sta.ifconfig()[0] if sta.isconnected() else "0.0.0.0"
            except Exception:
                ip = "0.0.0.0"
            print("Status server su http://%s:%d/status" % (ip, bound))
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
                if verbose:
                    try:
                        print("[HTTP] %s %s %s" % (_client_ip(addr), method, path))
                    except Exception:
                        pass
                if method == "OPTIONS":
                    cl.send(_HTTP_204_CORS)
                    if verbose:
                        try: print("[HTTP] 204 OPTIONS")
                        except Exception: pass
                    continue
                if method == "GET" and path.startswith("/favicon.ico"):
                    cl.send(_HTTP_204_CORS)
                    if verbose:
                        try: print("[HTTP] 204 favicon")
                        except Exception: pass
                    continue
                if path.startswith("/fs/"):
                    if fs_api is None:
                        cl.send(_HTTP_400)
                        if verbose:
                            try: print("[HTTP] 400 /fs/* (fs_api non disponibile)")
                            except Exception: pass
                    else:
                        handled = fs_api.handle(cl, method, path, req, _read_post_json, _body_initial_and_len)
                        if not handled:
                            cl.send(_HTTP_400)
                            if verbose:
                                try: print("[HTTP] 400 /fs/* non gestita")
                                except Exception: pass
                        elif verbose:
                            try: print("[HTTP] OK fs_api")
                            except Exception: pass
                    continue
                if status_api.handle(cl, method, path):
                    if verbose:
                        try: print("[HTTP] OK status_api")
                        except Exception: pass
                elif wifi_api.handle(cl, method, path, req, _read_post_json):
                    if verbose:
                        try: print("[HTTP] OK wifi_api")
                        except Exception: pass
                elif (adc_api is not None) and adc_api.handle(cl, method, path, req, _read_post_json):
                    if verbose:
                        try: print("[HTTP] OK adc_api")
                        except Exception: pass
                elif (
                    (power_sensors_api is not None)
                    and feature_enabled("power_sensors")
                    and power_sensors_api.handle_power_sensor(cl, method, path, req, _read_post_json)
                ):
                    if verbose:
                        try: print("[HTTP] OK power_sensors_api")
                        except Exception: pass
                elif (
                    webrepl_api is not None
                    and feature_enabled("webrepl")
                    and webrepl_api.handle_webrepl(cl, method, path, req, _read_post_json)
                ):
                    if verbose:
                        try: print("[HTTP] OK webrepl_api")
                        except Exception: pass
                elif system_api.handle(cl, method, path):
                    if verbose:
                        try: print("[HTTP] OK system_api")
                        except Exception: pass
                else:
                    cl.send(_HTTP_400)
                    if verbose:
                        try: print("[HTTP] 400 route non trovata: %s %s" % (method, path))
                        except Exception: pass
            except Exception as e:
                err_no = None
                try:
                    if isinstance(e, OSError) and len(e.args) > 0:
                        err_no = e.args[0]
                except Exception:
                    err_no = None
                # Timeout/socket transient: evita rumore e continua
                if err_no not in (110, 116):
                    if verbose:
                        try: print("[HTTP] EXC %r" % (e,))
                        except Exception: pass
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
