"""Wi-Fi API endpoints.

Serves a static UI page and exposes simple JSON endpoints for
scan/list/add/delete operations using `core.wifi_store`.
"""

import ujson
from core.http_consts import _HTTP_200_JSON, _HTTP_200_HTML
from wifi import wifi_store as wcfg


def _send_all(cl, data):
    mv = memoryview(data)
    sent = 0
    total = len(mv)
    while sent < total:
        n = cl.send(mv[sent:])
        if not n:
            raise OSError("send_failed")
        sent += n


def _send_file_chunked(cl, path, chunk_size=1024):
    _send_all(cl, _HTTP_200_HTML)
    with open(path, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            _send_all(cl, chunk)


def _send_json(cl, payload):
    _send_all(cl, _HTTP_200_JSON + ujson.dumps(payload).encode())


def _send_static_ui(cl):
    """Send the Wi-Fi UI from the filesystem, with a minimal fallback page."""
    paths = (
        "wifi/wifi_ui.html",
        "/wifi/wifi_ui.html",
        "core/wifi_ui.html",
        "/core/wifi_ui.html",
    )
    for p in paths:
        try:
            _send_file_chunked(cl, p)
            return True
        except Exception:
            pass
    fallback = b"".join(
        [
            b"<!doctype html><html><head><meta charset='utf-8'>",
            b"<title>WiFi UI</title></head><body>",
            b"<h1>Interfaccia Wi-Fi non installata</h1>",
            b"<p>Manca il file wifi/wifi_ui.html sul dispositivo.</p>",
            b"</body></html>",
        ]
    )
    _send_all(cl, _HTTP_200_HTML + fallback)
    return True


def handle(cl, method, path, req, _read_post_json, _body_initial_and_len=None):
    if method == "GET" and path.startswith("/wifi/ui"):
        return _send_static_ui(cl)

    if method == "GET" and path.startswith("/wifi/scan"):
        _send_json(cl, wcfg.scan())
        return True

    if method == "GET" and path.startswith("/wifi/list"):
        _send_json(cl, {"configured_networks": wcfg.configured_networks_no_password()})
        return True

    if method == "POST" and path.startswith("/wifi/add"):
        try:
            body = _read_post_json(req, cl)
            ok, msg = wcfg.add_network(body.get("ssid"), body.get("password", ""), body.get("priority"))
            _send_json(cl, {"ok": ok, "message": msg})
        except Exception:
            _send_json(cl, {"ok": False, "message": "invalid_request"})
        return True

    if method == "POST" and path.startswith("/wifi/delete"):
        try:
            body = _read_post_json(req, cl)
            ok, msg = wcfg.delete_network(body.get("ssid"))
            _send_json(cl, {"ok": ok, "message": msg})
        except Exception:
            _send_json(cl, {"ok": False, "message": "invalid_request"})
        return True

    return False
