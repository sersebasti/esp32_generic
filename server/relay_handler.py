# server/relay_handler.py
"""
Handler HTTP per relay, integrato nel sistema centralizzato di dispatch.
"""
from core.http_consts import _HTTP_400

_RELAY_API = None
_RELAY_IMPORT_ERR = None
_RELAY_PREFIXES = (
    "/relay",
)

def _is_relay_path(path):
    path_base = path.split("?", 1)[0]
    for prefix in _RELAY_PREFIXES:
        if path_base == prefix or path_base.startswith(prefix + "/"):
            return True
    return False

def _get_relay_api():
    global _RELAY_API, _RELAY_IMPORT_ERR
    if _RELAY_API is not None:
        return _RELAY_API
    if _RELAY_IMPORT_ERR is not None:
        return None
    try:
        import relays.relay_api as relay_api
        _RELAY_API = relay_api
        return _RELAY_API
    except Exception as exc:
        _RELAY_IMPORT_ERR = exc
        return None

def handle(cl, method, path, req=None, read_post_json=None, body_initial_and_len=None):
    if not _is_relay_path(path):
        return False
    relay_api = _get_relay_api()
    if relay_api is None:
        cl.send(_HTTP_400)
        return {"code": 400, "action": "relay_import_error"}
    handled = relay_api.handle(cl, method, path, req, read_post_json)
    if handled:
        return {"code": 200, "action": "relay"}
    return False
