# calib_api.py
import ujson
from http_consts import _HTTP_200_JSON, _HTTP_200_JSON_CORS
from busy_lock import BUSY
import adc_scope

def _cal_load():
    try:
        with open("calibrate.json") as f:
            return ujson.load(f)
    except:
        return {}

def _cal_save(d):
    with open("calibrate.json", "w") as f:
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

def handle(cl, method, path, req, _read_post_json):
    # /calibrate (GET con query amp=?)
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
                        try:
                            amp = float(v)
                        except:
                            amp = None

        cal = _cal_load()

        # Nessun parametro → stato corrente
        if amp is None:
            if "points" not in cal: cal["points"] = []
            resp = {"ok": True, "cal": cal,
                    "hint": "usa /calibrate?amp=0 per baseline, /calibrate?amp=<A> per aggiungere un punto"}
            cl.send(_HTTP_200_JSON + ujson.dumps(resp).encode())
            return True

        # amp == 0 → baseline
        if amp == 0.0:
            if BUSY["v"]:
                cl.send(_HTTP_200_JSON + b'{"ok":false,"err":"busy"}')
                return True
            BUSY["v"] = True
            try:
                arr, sr = adc_scope.sample_counts(n, sr)
                baseline = sum(arr) / len(arr)
                cal["baseline_mean"] = round(baseline, 2)
                cal["n0"] = len(arr); cal["sr0"] = sr
                if "points" not in cal: cal["points"] = []
                _cal_save(cal)
                resp = {"ok": True, "saved": {"baseline_mean": cal["baseline_mean"], "n0": cal["n0"], "sr0": cal["sr0"]}}
                cl.send(_HTTP_200_JSON + ujson.dumps(resp).encode())
            finally:
                BUSY["v"] = False
            return True

        # amp > 0 → aggiungi punto + fit k
        if BUSY["v"]:
            cl.send(_HTTP_200_JSON + b'{"ok":false,"err":"busy"}')
            return True
        BUSY["v"] = True
        try:
            arr, sr = adc_scope.sample_counts(n, sr)
            baseline = float(cal.get("baseline_mean", sum(arr)/len(arr)))
            rms = _rms_with_baseline(arr, baseline)
            pt = {"amps": float(amp), "rms_counts": round(rms, 2)}
            pts = cal.get("points", [])
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
        finally:
            BUSY["v"] = False
        return True

    # /amps (GET)
    if method == "GET" and path.startswith("/amps"):
        if BUSY["v"]:
            cl.send(_HTTP_200_JSON + b'{"ok":false,"err":"busy"}')
            return True
        BUSY["v"] = True
        try:
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
        finally:
            BUSY["v"] = False
        return True

    # /calibrate/delete (POST)
    if method == "POST" and path.startswith("/calibrate/delete"):
        try:
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

    # /calibrate/reset (POST)
    if method == "POST" and path.startswith("/calibrate/reset"):
        try:
            import os
            os.remove("calibrate.json")
        except:
            pass
        cl.send(_HTTP_200_JSON + b'{"ok":true}')
        return True

    return False
