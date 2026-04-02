from core.http_consts import _HTTP_400

_FS_API = None
_FS_IMPORT_ERR = None
_FS_PREFIXES = (
    "/fs",
)

def _is_fs_path(path):
    path_base = path.split("?", 1)[0]
    for prefix in _FS_PREFIXES:
        if path_base == prefix or path_base.startswith(prefix + "/") or path.startswith(prefix):
            return True
    return False

def _get_fs_api():
    global _FS_API, _FS_IMPORT_ERR
    if _FS_API is not None:
        return _FS_API
    if _FS_IMPORT_ERR is not None:
        return None
    try:
        import fs.api as fs_api
        _FS_API = fs_api
        return _FS_API
    except Exception as exc:
        _FS_IMPORT_ERR = exc
        return None

def _action_from_path(path):
    path_base = path.split("?", 1)[0]
    if path_base.startswith("/fs/list"):
        return "fs_list"
    if path_base.startswith("/fs/download"):
        return "fs_download"
    if path_base.startswith("/fs/upload"):
        return "fs_upload"
    if path_base.startswith("/fs/delete"):
        return "fs_delete"
    if path_base.startswith("/fs/rename"):
        return "fs_rename"
    return "fs"

def handle(cl, method, path, req=None, read_post_json=None, body_initial_and_len=None):
    if not _is_fs_path(path):
        return False
    fs_api = _get_fs_api()
    if fs_api is None:
        cl.send(_HTTP_400)
        return {"code": 400, "action": "fs_import_error"}
    handled = fs_api.handle(cl, method, path, req, read_post_json, body_initial_and_len)
    if handled:
        return {"code": 200, "action": _action_from_path(path)}
    return False
