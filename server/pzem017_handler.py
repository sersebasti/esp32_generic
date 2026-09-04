# server/pzem017_handler.py

from core.http_consts import _HTTP_400


_PZEM017_API = None
_PZEM017_IMPORT_ERR = None

_PZEM017_PREFIXES = (
    "/pzem017",
)


def _is_pzem017_path(path):
    path_base = path.split("?", 1)[0]

    for prefix in _PZEM017_PREFIXES:
        if path_base == prefix or path_base.startswith(prefix + "/"):
            return True

    return False


def _get_pzem017_api():
    global _PZEM017_API, _PZEM017_IMPORT_ERR

    if _PZEM017_API is not None:
        return _PZEM017_API

    if _PZEM017_IMPORT_ERR is not None:
        return None

    try:
        import pzem_017.pzem017_api as pzem017_api
        _PZEM017_API = pzem017_api
        return _PZEM017_API

    except Exception as exc:
        _PZEM017_IMPORT_ERR = exc
        print("[PZEM-017-HANDLER] import error:", exc)
        return None


def handle(cl, method, path, req=None, read_post_json=None, body_initial_and_len=None):
    if not _is_pzem017_path(path):
        return False

    pzem017_api = _get_pzem017_api()

    if pzem017_api is None:
        cl.send(_HTTP_400)
        return {
            "code": 400,
            "action": "pzem017_import_error"
        }

    handled = pzem017_api.handle_pzem017(
        cl,
        method,
        path,
        req,
        read_post_json
    )

    if handled:
        return {
            "code": 200,
            "action": "pzem017"
        }

    return False