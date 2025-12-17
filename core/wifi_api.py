# wifi_api.py (core)
import ujson
from core.http_consts import _HTTP_200_JSON, _HTTP_200_HTML
from core import wifi_config as wcfg
from core import wifi_ui

def handle(cl, method, path, req, _read_post_json):
    # /wifi/ui
    if method == "GET" and path.startswith("/wifi/ui"):
        cl.send(_HTTP_200_HTML + wifi_ui.page())
        return True

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
            ok, msg = wcfg.add_network(body.get("ssid"), body.get("password", ""))
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
