# adc_api.py (scope)
import ujson, os
from core.http_consts import _HTTP_200_JSON, _HTTP_200_JSON_CORS
try:
    from core.busy_lock import is_busy, busy_region
except Exception:
    from busy_lock import is_busy, busy_region
import scope.adc_scope as adc_scope

_CAL_PATH = "scope/calibrate.json"

def _cal_load():
    try:
        with open(_CAL_PATH) as f:
            return ujson.load(f)
    except Exception:
        return {}

def _cal_save(d):
    try:
        os.mkdir("scope")
    except Exception:
        pass
    with open(_CAL_PATH, "w") as f:
        ujson.dump(d, f)

def _rms_with_baseline(arr, baseline):
    s = 0.0
    for v in arr:
        d = v - baseline
        s += d * d
    from math import sqrt
    return sqrt(s / len(arr))

def _fit_k(points):
    sxy = 0.0
    sxx = 0.0
    for p in points:
        a = float(p["amps"])
        r = float(p["rms_counts"])
        sxy += a * r
        sxx += r * r
    return (sxy / sxx) if sxx > 0 else 0.0

def handle(cl, method, path, req=None, _read_post_json=None):
    # /adc/scope_counts
    if method == "GET" and path.startswith("/adc/scope_counts"):
        if not adc_scope:
            cl.send(_HTTP_200_JSON + b'{"ok":false,"err":"adc_scope_module_missing"}')
            return True
        if is_busy():
            cl.send(_HTTP_200_JSON + b'{"ok":false,"err":"busy"}')
            return True
        with busy_region():
            n = 1024; sr = 4000
            if "?" in path:
                q = path.split("?", 1)[1]
                for p in q.split("&"):
                    if "=" in p:
                        k, v = p.split("=", 1)
                        if k == "n": n = int(v)
                        elif k in ("sr","sample_rate_hz"): sr = int(v)
            payload = adc_scope.json_dump_counts(n=n, sample_rate_hz=sr)
            cl.send(_HTTP_200_JSON + payload.encode())
        return True

    # ---- Calibration endpoints ----
    if method == "GET" and path.startswith("/calibrate"):
        n = 1600; sr = 4000; amp = None
        if "?" in path:
            q = path.split("?", 1)[1]
            for p in q.split("&"):
                if "=" in p:
                    k, v = p.split("=", 1)
                    if k == "n": n = int(v)
                    elif k in ("sr","sample_rate_hz"): sr = int(v)
                    elif k == "amp":
                        try: amp = float(v)
                        except: amp = None

        cal = _cal_load()
        if amp is None:
            if "points" not in cal: cal["points"] = []
            resp = {"ok": True, "cal": cal,
                    "hint": "usa /calibrate?amp=0 per baseline, /calibrate?amp=<A> per aggiungere un punto"}
            cl.send(_HTTP_200_JSON + ujson.dumps(resp).encode())
            return True

        if amp == 0.0:
            if is_busy():
                cl.send(_HTTP_200_JSON + b'{"ok":false,"err":"busy"}')
                return True
            with busy_region():
                arr, sr = adc_scope.sample_counts(n, sr)
                baseline = sum(arr) / len(arr)
                cal["baseline_mean"] = round(baseline, 2)
                cal["n0"] = len(arr); cal["sr0"] = sr
                if "points" not in cal: cal["points"] = []
                _cal_save(cal)
                resp = {"ok": True, "saved": {"baseline_mean": cal["baseline_mean"], "n0": cal["n0"], "sr0": cal["sr0"]}}
                cl.send(_HTTP_200_JSON + ujson.dumps(resp).encode())
            return True

        if is_busy():
            cl.send(_HTTP_200_JSON + b'{"ok":false,"err":"busy"}')
            return True
        with busy_region():
            arr, sr = adc_scope.sample_counts(n, sr)
            baseline = float(cal.get("baseline_mean", sum(arr)/len(arr)))
            rms = _rms_with_baseline(arr, baseline)
            pt = {"amps": float(amp), "rms_counts": round(rms, 2)}
            pts = cal.get("points", [])
            pts = pts if isinstance(pts, list) else []
            pts.append(pt)
            cal["points"] = pts
            k = _fit_k(pts)
            cal["k_A_per_count"] = round(k, 9)
            _cal_save(cal)

            mn = min(arr); mx = max(arr)
            clipping = (mn < 50) or (mx > 4040)
            resp = {"ok": True, "added": pt, "k_A_per_count": cal["k_A_per_count"],
                    "num_points": len(pts), "baseline_mean": round(baseline, 2),
                    "min": int(mn), "max": int(mx), "clipping": bool(clipping)}
            cl.send(_HTTP_200_JSON + ujson.dumps(resp).encode())
        return True

    if method == "GET" and path.startswith("/amps"):
        if is_busy():
            cl.send(_HTTP_200_JSON + b'{"ok":false,"err":"busy"}')
            return True
        with busy_region():
            n = 1600; sr = 4000
            if "?" in path:
                q = path.split("?", 1)[1]
                for p in q.split("&"):
                    if "=" in p:
                        k, v = p.split("=", 1)
                        if k == "n": n = int(v)
                        elif k in ("sr","sample_rate_hz"): sr = int(v)

            cal = _cal_load()
            k = float(cal.get("k_A_per_count", 0.0))
            if k <= 0:
                cl.send(_HTTP_200_JSON + b'{"ok":false,"err":"no_model"}')
            else:
                arr, sr = adc_scope.sample_counts(n, sr)
                baseline = float(cal.get("baseline_mean", sum(arr)/len(arr)))
                rms = _rms_with_baseline(arr, baseline)
                amps = k * rms
                mn = min(arr); mx = max(arr)
                clipping = (mn < 50) or (mx > 4040)
                out = {"ok": True, "amps_rms": round(amps, 3), "rms_counts": round(rms, 2),
                       "baseline_mean": round(baseline, 2),
                       "min": int(mn), "max": int(mx), "clipping": bool(clipping)}
                cl.send(_HTTP_200_JSON + ujson.dumps(out).encode())
        return True

    if method == "POST" and path.startswith("/calibrate/delete"):
        try:
            if _read_post_json is None or req is None:
                raise Exception("no_json_parser")
            body = _read_post_json(req, cl)
            idx = body.get("index", None)
            amp = body.get("amps", None)
            rms = body.get("rms_counts", None)

            cal = _cal_load()
            pts = cal.get("points", []) or []

            removed = None
            if isinstance(idx, int) and 0 <= idx < len(pts):
                removed = pts.pop(idx)
            elif (amp is not None) and (rms is not None):
                for i, p in enumerate(pts):
                    try:
                        if float(p.get("amps")) == float(amp) and float(p.get("rms_counts")) == float(rms):
                            removed = pts.pop(i)
                            break
                    except Exception:
                        pass

            if removed is None:
                cl.send(_HTTP_200_JSON_CORS + ujson.dumps({"ok": False, "err": "not_found"}).encode())
            else:
                cal["points"] = pts
                if pts:
                    k = _fit_k(pts)
                    cal["k_A_per_count"] = round(k, 9)
                else:
                    cal["k_A_per_count"] = 0.0
                _cal_save(cal)
                resp = {"ok": True, "removed": removed,
                        "num_points": len(pts),
                        "k_A_per_count": cal.get("k_A_per_count", 0.0)}
                cl.send(_HTTP_200_JSON_CORS + ujson.dumps(resp).encode())
        except Exception:
            try:
                cl.send(_HTTP_200_JSON_CORS + b'{"ok":false,"err":"invalid_request"}')
            except Exception:
                pass
        return True

    if method == "POST" and path.startswith("/calibrate/reset"):
        try:
            try:
                os.remove(_CAL_PATH)
            except Exception:
                pass
        except Exception:
            pass
        cl.send(_HTTP_200_JSON + b'{"ok":true}')
        return True

    return False
