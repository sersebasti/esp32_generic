from core.http_consts import _HTTP_400

_SCOPE_API = None
_SCOPE_IMPORT_ERR = None
_SCOPE_PREFIXES = (
    "/sensors",
    "/adc",
    "/amps",
    "/volts",
    "/power",
    "/calibrate",
    "/compare_baseline",
)


def _is_scope_path(path):
    path_base = path.split("?", 1)[0]
    for prefix in _SCOPE_PREFIXES:
        if path_base == prefix or path_base.startswith(prefix + "/"):
            return True
    return False


def _get_scope_api():
    global _SCOPE_API, _SCOPE_IMPORT_ERR
    if _SCOPE_API is not None:
        return _SCOPE_API
    if _SCOPE_IMPORT_ERR is not None:
        return None
    try:
        import scope.adc_api as scope_api

        _SCOPE_API = scope_api
        return _SCOPE_API
    except Exception as exc:
        _SCOPE_IMPORT_ERR = exc
        return None


def _action_from_path(path):
    path_base = path.split("?", 1)[0]
    if path_base == "/sensors":
        return "scope_sensors"
    if path_base.startswith("/adc/scope_counts"):
        return "scope_counts"
    if path_base.startswith("/compare_baseline"):
        return "scope_compare_baseline"
    if path_base.startswith("/calibrate/delete"):
        return "scope_calibrate_delete"
    if path_base.startswith("/calibrate/reset"):
        return "scope_calibrate_reset"
    if path_base.startswith("/calibrate"):
        return "scope_calibrate"
    if path_base.startswith("/amps"):
        return "scope_amps"
    if path_base.startswith("/volts"):
        return "scope_volts"
    if path_base.startswith("/power"):
        return "scope_power"
    return "scope"


def handle(cl, method, path, req=None, read_post_json=None, body_initial_and_len=None):
    if not _is_scope_path(path):
        return False

    scope_api = _get_scope_api()
    if scope_api is None:
        cl.send(_HTTP_400)
        return {"code": 400, "action": "scope_import_error"}

    handled = scope_api.handle(cl, method, path, req, read_post_json)
    if handled:
        return {"code": 200, "action": _action_from_path(path)}
    return False
