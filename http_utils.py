# http_utils.py
import json, time

HTTP_STATUSES = {
    200: "OK", 201: "Created", 204: "No Content",
    302: "Found", 400: "Bad Request", 401: "Unauthorized",
    404: "Not Found", 405: "Method Not Allowed",
    409: "Conflict", 500: "Internal Server Error"
}

def _urldecode(s):
    # semplice decodifica %XX e + → spazio
    out = []
    i = 0
    while i < len(s):
        c = s[i]
        if c == '+':
            out.append(' ')
            i += 1
        elif c == '%' and i+2 < len(s):
            try:
                out.append(chr(int(s[i+1:i+3], 16)))
                i += 3
            except:
                out.append('%'); i += 1
        else:
            out.append(c); i += 1
    return ''.join(out)

def parse_qs(q):
    d = {}
    if not q:
        return d
    for pair in q.split('&'):
        if not pair:
            continue
        if '=' in pair:
            k, v = pair.split('=', 1)
            d[_urldecode(k)] = _urldecode(v)
        else:
            d[_urldecode(pair)] = ''
    return d

class Req:
    __slots__ = ("method","path","query","qs","headers","body","ts")
    def __init__(self, method, path, query, headers, body):
        self.method  = method
        self.path    = path
        self.query   = query
        self.qs      = parse_qs(query)
        self.headers = headers
        self.body    = body
        self.ts      = time.ticks_ms()

def read_request(conn, max_body=8*1024, timeout=2.0):
    conn.settimeout(timeout)
    data = b""
    # leggi header
    while b"\r\n\r\n" not in data:
        chunk = conn.recv(512)
        if not chunk: break
        data += chunk
        if len(data) > 16*1024: break
    head, _, rest = data.partition(b"\r\n\r\n")
    if not head:
        return None
    lines = head.split(b"\r\n")
    try:
        method, fullpath, _ = lines[0].decode().split(" ")
    except:
        return None
    if "?" in fullpath:
        path, query = fullpath.split("?", 1)
    else:
        path, query = fullpath, ""
    headers = {}
    for ln in lines[1:]:
        try:
            k, v = ln.decode().split(":", 1)
            headers[k.strip().lower()] = v.strip()
        except:
            pass
    # body (se Content-Length)
    body = rest
    try:
        clen = int(headers.get("content-length","0"))
    except:
        clen = 0
    while len(body) < clen and len(body) < max_body:
        more = conn.recv(min(1024, clen - len(body)))
        if not more: break
        body += more
    return Req(method, path, query, headers, body)

def _send_status(conn, code=200, ctype="text/plain", length=0, extra_hdrs=None):
    msg = HTTP_STATUSES.get(code, "OK")
    hdr = "HTTP/1.0 %d %s\r\n" % (code, msg)
    hdr += "Connection: close\r\n"
    hdr += "Access-Control-Allow-Origin: *\r\n"
    hdr += "Content-Type: %s\r\n" % ctype
    hdr += "Content-Length: %d\r\n" % length
    if extra_hdrs:
        for k, v in extra_hdrs.items():
            hdr += "%s: %s\r\n" % (k, v)
    hdr += "\r\n"
    conn.send(hdr.encode())

def send_json(conn, obj, code=200):
    try:
        body = json.dumps(obj)
    except:
        body = '{"ok":false,"err":"json"}'
        code = 500
    _send_status(conn, code=code, ctype="application/json", length=len(body))
    conn.send(body.encode())

def send_text(conn, text, code=200, ctype="text/plain; charset=utf-8"):
    body = text if isinstance(text, str) else str(text)
    _send_status(conn, code=code, ctype=ctype, length=len(body))
    conn.send(body.encode())

def send_html(conn, html, code=200):
    _send_status(conn, code=code, ctype="text/html; charset=utf-8", length=len(html))
    conn.send(html.encode())

def close_quietly(conn):
    try: conn.close()
    except: pass
