import ujson
from core.http_consts import _HTTP_200_JSON

from relay.relay_manager import RelayManager


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


def handle(cl, method, path, req=None, _read_post_json=None):
    if not path.startswith("/relay"):
        return False

    relay = _manager()

    if method == "GET" and path in ("/relay", "/relay/status"):
        _send_json(cl, relay.status())
        return True

    if method == "POST" and path == "/relay/on":
        _send_json(cl, relay.on())
        return True

    if method == "POST" and path == "/relay/off":
        _send_json(cl, relay.off())
        return True

    if method == "POST" and path == "/relay/toggle":
        _send_json(cl, relay.toggle())
        return True

    if method == "POST" and path == "/relay/set":
        try:
            body = _read_post_json(req, cl) if _read_post_json else {}
        except Exception as e:
            _send_json(cl, {"ok": False, "err": str(e)})
            return True

        if "on" in body:
            enabled = _bool_value(body.get("on"))
        else:
            enabled = str(body.get("state", "off")).lower() == "on"
        _send_json(cl, relay.set_state(enabled))
        return True

    _send_json(cl, {"ok": False, "err": "unknown_relay_endpoint"})
    return True