# filename: web_ap.py
import socket, time, ujson, machine

try:
    from logger import RollingLogger
    log = RollingLogger(path="log.txt", max_bytes=8*1024, backups=1)
except Exception:
    class _Dummy:
        def info(self,*a,**k): pass
        def warn(self,*a,**k): pass
        def error(self,*a,**k): pass
        def log(self,*a,**k): pass
    log = _Dummy()

FORM_HTML = b"""<!DOCTYPE html>
<html><head><meta name="viewport" content="width=device-width, initial-scale=1">
<title>ESP32 WiFi Setup</title></head>
<body>
  <h2>Configura Wi-Fi</h2>
  <form action="/save" method="post">
    <label>SSID: <input name="ssid"></label><br>
    <label>Password: <input name="password" type="password"></label><br>
    <input type="submit" value="Salva">
  </form>
  <p>Oppure invia JSON a <code>/save_json</code>:
  <pre>{"hostname":"esp32_1","networks":[{"ssid":"MyWiFi","password":"mypass"}]}</pre></p>
</body></html>
"""

HTTP_200 = b"HTTP/1.1 200 OK\r\nContent-Type: text/html\r\nCache-Control: no-store\r\nConnection: close\r\n\r\n"
HTTP_TXT = b"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nCache-Control: no-store\r\nConnection: close\r\n\r\n"
HTTP_400 = b"HTTP/1.1 400 Bad Request\r\nContent-Type: text/plain\r\nCache-Control: no-store\r\nConnection: close\r\n\r\nBad Request"

def _url_decode(s):
    s = s.replace('+', ' ')
    out = bytearray(); i = 0
    while i < len(s):
        c = s[i]
        if c == '%' and i+2 < len(s):
            try:
                out.append(int(s[i+1:i+3], 16)); i += 3; continue
            except Exception: pass
        out.append(ord(c)); i += 1
    return out.decode()

def _parse_form(body):
    params = {}
    for pair in body.split('&'):
        if '=' in pair:
            k, v = pair.split('=', 1)
            params[k] = _url_decode(v)
    return params

def _read_http(sock):
    # leggi header
    data = b""
    while b"\r\n\r\n" not in data:
        chunk = sock.recv(512)
        if not chunk: break
        data += chunk
        if len(data) > 4096: break
    head, _, rest = data.partition(b"\r\n\r\n")
    if not head:
        return "GET / HTTP/1.1", {}, b""
    lines = head.split(b"\r\n")
    request_line = lines[0].decode("utf-8", "ignore")
    headers = {}
    for h in lines[1:]:
        if b":" in h:
            k, v = h.split(b":", 1)
            headers[k.strip().lower()] = v.strip().decode()
    # calcola body
    try:
        content_length = int(headers.get(b'content-length', headers.get('content-length', "0")))
    except Exception:
        content_length = 0
    body = rest
    while len(body) < content_length:
        chunk = sock.recv(512)
        if not chunk: break
        body += chunk
    return request_line, headers, body

def _write_wifi_json(ssid, password, hostname=None):
    cfg = {"networks":[{"ssid":ssid,"password":password}]}
    if hostname: cfg["hostname"] = hostname
    with open("wifi.json","w") as f:
        ujson.dump(cfg, f)
    log.info("Salvato wifi.json per SSID='%s'" % ssid)

def _write_wifi_json_raw(obj):
    with open("wifi.json","w") as f:
        ujson.dump(obj, f)
    log.info("Salvato wifi.json (raw)")

def start_web_ap():
    """Portale su 0.0.0.0:80 (fallback 8080). Dopo /save ritorna."""
    # prepara server
    s = socket.socket()
    try:
        try:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        except Exception:
            pass

        # bind con fallback
        bound_port = None
        try:
            s.bind(('0.0.0.0', 80)); bound_port = 80
        except OSError as e:
            log.warn("Port 80 busy (%r), trying 8080" % (e,))
            s.bind(('0.0.0.0', 8080)); bound_port = 8080

        s.listen(2)
        s.settimeout(1)
        print('Web server attivo su http://192.168.4.1%s' % ('' if bound_port==80 else (':%d'%bound_port)))

        while True:
            try:
                cl, remote = s.accept()
            except OSError:
                continue

            try:
                cl.settimeout(10)
                request_line, headers, body = _read_http(cl)
                parts = request_line.split(" ")
                method = parts[0] if len(parts)>0 else "GET"
                path   = parts[1] if len(parts)>1 else "/"
                print("HTTP:", method, path, "da", remote)

                if method == "GET" and path in ("/", "/index.html", "/generate_204", "/hotspot-detect.html"):
                    cl.send(HTTP_200); cl.send(FORM_HTML)

                elif method == "POST" and path == "/save":
                    params = _parse_form(body.decode())
                    ssid = params.get("ssid","").strip()
                    pwd  = params.get("password","")
                    if not ssid:
                        cl.send(HTTP_400)
                    else:
                        _write_wifi_json(ssid, pwd)
                        cl.send(HTTP_TXT + b"OK. Salvato. Mi connetto alla Wi-Fi...")
                        try: cl.close()
                        except: pass
                        return  # esci da start_web_ap() invece di resettare

                elif method == "POST" and path == "/save_json":
                    try:
                        obj = ujson.loads(body.decode())
                        _write_wifi_json_raw(obj)
                        cl.send(HTTP_TXT + b"OK JSON. Salvato. Mi connetto alla Wi-Fi...")
                        try: cl.close()
                        except: pass
                        return
                    except Exception:
                        cl.send(HTTP_400 + b"\nJSON error")

                else:
                    cl.send(HTTP_200); cl.send(FORM_HTML)

            except Exception as e:
                try:
                    log.error("HTTP error: %r" % e)
                    cl.send(HTTP_400)
                except Exception:
                    pass
            finally:
                try: cl.close()
                except Exception: pass

    finally:
        try: s.close()
        except Exception: pass

