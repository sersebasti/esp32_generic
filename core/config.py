# core/config.py
import ujson

_DEFAULTS = {
    "wifi_json": "wifi.json",
    "log_path": "log.txt",
    "log_max_bytes": 8 * 1024,
    "btn_pin": 32,
    "features": {
        "scope": True,
        "calibration": True,
        "fs_api": True,
    },
}


def _deep_merge(base, override):
    if not isinstance(base, dict) or not isinstance(override, dict):
        return override if override is not None else base
    out = dict(base)
    for k, v in override.items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def _load_file(path="config.json"):
    try:
        with open(path, "r") as f:
            return ujson.load(f)
    except Exception:
        return {}


def load_config(path="config.json"):
    data = _load_file(path)
    if not isinstance(data, dict):
        data = {}
    return _deep_merge(_DEFAULTS, data)


cfg = load_config()


def feature_enabled(name):
    try:
        feats = cfg.get("features", {})
        return bool(feats.get(name, False))
    except Exception:
        return False
