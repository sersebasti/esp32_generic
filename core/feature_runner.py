# core/feature_runner.py
# Avvio generico delle feature abilitate in config.
from core import config


class _NullLog:
    def info(self, *a, **k):
        return None
    warn = info
    error = info


def _import_module(name):
    mod = __import__(name)
    if "." not in name:
        return mod
    cur = mod
    for part in name.split(".")[1:]:
        try:
            cur = getattr(cur, part)
        except Exception:
            return mod
    return cur


def _iter_feature_names():
    feats = config.cfg.get("features", {})
    order = getattr(config, "FEATURE_ORDER", None)
    if order:
        seen = set()
        for name in order:
            if name in feats:
                seen.add(name)
                yield name
        for name in feats:
            if name not in seen:
                yield name
    else:
        for name in feats:
            yield name


def start_enabled_features():
    context = {"log": _NullLog()}
    feats = config.cfg.get("features", {})
    for name in _iter_feature_names():
        if not feats.get(name, False):
            continue
        try:
            mod = _import_module(name)
        except Exception as e:
            print("[FEATURE] import failed:", name, e)
            continue
        try:
            start_fn = getattr(mod, "start", None)
            if not start_fn:
                print("[FEATURE] no start():", name)
                continue
            result = start_fn(context)
            if isinstance(result, dict):
                context.update(result)
        except Exception as e:
            print("[FEATURE] start failed:", name, e)
            continue
    return context
