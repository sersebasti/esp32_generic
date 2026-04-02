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


def _send_static_ui(cl):
    """Try to send the static UI HTML from common locations.

    Preference order:
    - core/wifi_ui.html
    - /core/wifi_ui.html
    - wifi_ui.html
    - /wifi_ui.html
    If not found, respond with a minimal placeholder page.
    """
    paths = (
        "core/wifi_ui.html",
        "/core/wifi_ui.html",
        "wifi_ui.html",
        "/wifi_ui.html",
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
            b"<p>Manca il file core/wifi_ui.html sul dispositivo.</p>",
            b"</body></html>",
        ]
    )
    _send_all(cl, _HTTP_200_HTML + fallback)
    return True


def handle(cl, method, path, req, _read_post_json, _body_initial_and_len=None):
    # /wifi/ui → serve static HTML
    if method == "GET" and path.startswith("/wifi/ui"):
        return _send_static_ui(cl)

    # /wifi/scan
    if method == "GET" and path.startswith("/wifi/scan"):
        payload = wcfg.scan()
        cl.send(_HTTP_200_JSON + ujson.dumps(payload).encode())
        return True

    # /wifi/list
    if method == "GET" and path.startswith("/wifi/list"):
        payload = {"configured_networks": wcfg.configured_networks_no_password()}
        cl.send(_HTTP_200_JSON + ujson.dumps(payload).encode())
        return True

    # /wifi/add (POST JSON)
    if method == "POST" and path.startswith("/wifi/add"):
        try:
            body = _read_post_json(req, cl)
            ok, msg = wcfg.add_network(body.get("ssid"), body.get("password", ""), body.get("priority"))
            cl.send(_HTTP_200_JSON + ujson.dumps({"ok": ok, "message": msg}).encode())
        except Exception:
            cl.send(_HTTP_200_JSON + ujson.dumps({"ok": False, "message": "invalid_request"}).encode())
        return True

    # /wifi/delete (POST JSON)
    if method == "POST" and path.startswith("/wifi/delete"):
        try:
            body = _read_post_json(req, cl)
            ok, msg = wcfg.delete_network(body.get("ssid"))
            cl.send(_HTTP_200_JSON + ujson.dumps({"ok": ok, "message": msg}).encode())
        except Exception:
            cl.send(_HTTP_200_JSON + ujson.dumps({"ok": False, "message": "invalid_request"}).encode())
        return True

    return False
