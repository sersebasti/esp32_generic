import socket, gc, ujson, network
from http_consts import (_HTTP_200_JSON, _HTTP_200_HTML, _HTTP_400, _HTTP_204_CORS)
try:
    from core.busy_lock import BUSY
except Exception:
    from busy_lock import BUSY
import status_api, wifi_api, adc_api, system_api
import fs_api

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
        return method, path
    except Exception:
        return "GET", "/"

def start_server(preferred_port=80, fallback_port=8080, verbose=True):
    BUSY["v"] = False
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
                if method == "OPTIONS":
                    cl.send(_HTTP_204_CORS)
                    continue
                if path.startswith("/fs/"):
                    handled = fs_api.handle(cl, method, path, req, _read_post_json, _body_initial_and_len)
                    if not handled:
                        cl.send(_HTTP_400)
                    continue
                if status_api.handle(cl, method, path):
                    pass
                elif wifi_api.handle(cl, method, path, req, _read_post_json):
                    pass
                elif adc_api.handle(cl, method, path, req, _read_post_json):
                    pass
                elif system_api.handle(cl, method, path):
                    pass
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
