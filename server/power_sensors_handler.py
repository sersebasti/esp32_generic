# server/power_sensors_handler.py
"""
Handler HTTP per i power sensors, integrato nel sistema centralizzato di dispatch.
"""
from core.http_consts import _HTTP_400

_POWER_API = None
_POWER_IMPORT_ERR = None
_POWER_PREFIXES = (
    "/power_sensor",
)

def _is_power_path(path):
    path_base = path.split("?", 1)[0]
    for prefix in _POWER_PREFIXES:
        if path_base == prefix or path_base.startswith(prefix + "/") or path.startswith(prefix):
            return True
    return False

def _get_power_api():
    global _POWER_API, _POWER_IMPORT_ERR
    if _POWER_API is not None:
        return _POWER_API
    if _POWER_IMPORT_ERR is not None:
        return None
    try:
        import power_sensors.power_sensors_api as power_api
        _POWER_API = power_api
        return _POWER_API
    except Exception as exc:
        _POWER_IMPORT_ERR = exc
        return None

def handle(cl, method, path, req=None, read_post_json=None, body_initial_and_len=None):
    if not _is_power_path(path):
        return False
    power_api = _get_power_api()
    if power_api is None:
        cl.send(_HTTP_400)
        return {"code": 400, "action": "power_import_error"}
    handled = power_api.handle_power_sensor(cl, method, path, req, read_post_json)
    if handled:
        return {"code": 200, "action": "power_sensor"}
    return False
