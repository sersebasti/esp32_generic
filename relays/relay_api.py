import ujson
from core.http_consts import _HTTP_200_JSON
from relays.relay_manager import RelayManager

_RELAY = None

def _manager():
    global _RELAY
    if _RELAY is None:
        _RELAY = RelayManager()
    return _RELAY

def _send_json(cl, payload):
    cl.send(_HTTP_200_JSON + ujson.dumps(payload).encode())

def _bool_value(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value != 0
    if isinstance(value, str):
        return value.lower() in ("1", "true", "on", "high")
    return False

def _get_id_from_path_or_body(path, req, _read_post_json):
    # Cerca id in query string o body
    import ure
    m = ure.search(r"[?&]id=([^&]+)", path)
    if m:
        return m.group(1)
    if req and _read_post_json:
        try:
            body = _read_post_json(req, None)
            if isinstance(body, dict) and "id" in body:
                return body["id"]
        except Exception:
            pass
    return None

def handle(cl, method, path, req=None, _read_post_json=None):
    if not path.startswith("/relay"):
        return False

    relay_mgr = _manager()
    relay_id = _get_id_from_path_or_body(path, req, _read_post_json)
    path_base = path.split("?", 1)[0]

    if method == "GET" and path_base in ("/relay", "/relay/status"):
        _send_json(cl, relay_mgr.status(relay_id))
        return True

    if method == "POST" and path_base == "/relay/on":
        _send_json(cl, relay_mgr.on(relay_id))
        return True

    if method == "POST" and path_base == "/relay/off":
        _send_json(cl, relay_mgr.off(relay_id))
        return True

    if method == "POST" and path_base == "/relay/toggle":
        _send_json(cl, relay_mgr.toggle(relay_id))
        return True

    if method == "POST" and path_base == "/relay/set":
        try:
            body = _read_post_json(req, cl) if _read_post_json else {}
        except Exception as e:
            _send_json(cl, {"ok": False, "err": str(e)})
            return True
        enabled = False
        if "on" in body:
            enabled = _bool_value(body.get("on"))
        else:
            enabled = str(body.get("state", "off")).lower() == "on"
        relay_id = body.get("id", relay_id)
        relay = relay_mgr.get(relay_id)
        if relay:
            _send_json(cl, relay.set_state(enabled))
        else:
            _send_json(cl, {"ok": False, "err": "relay_not_found"})
        return True

    _send_json(cl, {"ok": False, "err": "unknown_relay_endpoint"})
    return True
