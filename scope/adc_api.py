# adc_api.py (scope)
import ujson, os
from core.http_consts import _HTTP_200_JSON, _HTTP_200_JSON_CORS
try:
    from core.busy_lock import is_busy, busy_region
except Exception:
    from busy_lock import is_busy, busy_region

# Refactoring: supporto multi-sensore
from .sensor_manager import CurrentSensorManager

# Inizializza il manager dei sensori (singleton)
_SENSOR_MANAGER = CurrentSensorManager()

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
    # /adc/scope_counts?sensor_id=c1
    if method == "GET" and path.startswith("/adc/scope_counts"):
        print("[DEBUG] handle /adc/scope_counts", path)
        if is_busy():
            print("[DEBUG] busy lock active")
            cl.send(_HTTP_200_JSON + b'{"ok":false,"err":"busy"}')
            return True
        with busy_region():
            n = 1024; sr = 4000; sensor_id = "c1"; fast = False
            if "?" in path:
                q = path.split("?", 1)[1]
                for p in q.split("&"):
                    if "=" in p:
                        k, v = p.split("=", 1)
                        if k == "n": n = int(v)
                        elif k in ("sr","sample_rate_hz"): sr = int(v)
                        elif k == "sensor_id": sensor_id = v
                        elif k == "fast": fast = v in ("1","true","True")
            print(f"[DEBUG] Parsed params: n={n}, sr={sr}, sensor_id={sensor_id}, fast={fast}")
            sensor = _SENSOR_MANAGER.get_sensor(sensor_id)
            print(f"[DEBUG] Sensor object: {sensor}")
            if not sensor:
                print("[DEBUG] Sensor not found")
                cl.send(_HTTP_200_JSON + b'{"ok":false,"err":"sensor_not_found"}')
                return True
            arr, sr = sensor.sample_counts(n, sr, fast=fast)
            print(f"[DEBUG] Sampled counts: {arr[:10]}... (total {len(arr)})")
            mean, rms = sensor.stats_counts(arr)
            print(f"[DEBUG] Stats: mean={mean}, rms={rms}")
            payload = ujson.dumps({
                "ok": True,
                "n": len(arr),
                "sample_rate_hz": sr,
                "counts": arr,
                "counts_mean": round(mean, 2),
                "counts_rms": round(rms, 2)
            })
            cl.send(_HTTP_200_JSON + payload.encode())
        return True

    # --- Endpoint per confronto baseline ---
    if method == "GET" and path.startswith("/compare_baseline"):
        n = 1600; sr = 4000; sensor_id = "c1"; fast = False
        if "?" in path:
            q = path.split("?", 1)[1]
            for p in q.split("&"):
                if "=" in p:
                    k, v = p.split("=", 1)
                    if k == "n": n = int(v)
                    elif k in ("sr","sample_rate_hz"): sr = int(v)
                    elif k == "sensor_id": sensor_id = v
                    elif k == "fast": fast = v in ("1","true","True")
        sensor = _SENSOR_MANAGER.get_sensor(sensor_id)
        if not sensor:
            cl.send(_HTTP_200_JSON + b'{"ok":false,"err":"sensor_not_found"}')
            return True
        baseline, mean_now, diff = sensor.compare_baseline(n, sr, fast=fast)
        resp = {"ok": True, "baseline_mean": baseline, "mean_now": round(mean_now, 2)}
        if baseline is not None:
            resp["diff"] = round(diff, 2)
        cl.send(_HTTP_200_JSON + ujson.dumps(resp).encode())
        return True

    # ---- Calibration endpoints (multi-sensore) ----
    if method == "GET" and path.startswith("/calibrate"):
        n = 1600; sr = 4000; amp = None; sensor_id = "c1"; fast = False
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
                    elif k == "sensor_id": sensor_id = v
                    elif k == "fast": fast = v in ("1","true","True")

        sensor = _SENSOR_MANAGER.get_sensor(sensor_id)
        if not sensor:
            cl.send(_HTTP_200_JSON + b'{"ok":false,"err":"sensor_not_found"}')
            return True

        if amp is None:
            cal = sensor._load_calibration()
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
                baseline = sensor.calibrate_baseline(n, sr, fast=fast)
                cal = sensor._load_calibration()
                resp = {"ok": True, "saved": {"baseline_mean": cal["baseline_mean"], "n0": cal["n0"], "sr0": cal["sr0"]}}
                cl.send(_HTTP_200_JSON + ujson.dumps(resp).encode())
            return True

        if is_busy():
            cl.send(_HTTP_200_JSON + b'{"ok":false,"err":"busy"}')
            return True
        with busy_region():
            pt, k = sensor.add_calibration_point(amp, n, sr, fast=fast)
            arr, sr = sensor.sample_counts(n, sr, fast=fast)
            baseline = float(sensor.cal.get("baseline_mean", sum(arr)/len(arr)))
            mn = min(arr); mx = max(arr)
            clipping = (mn < 50) or (mx > 4040)
            resp = {"ok": True, "added": pt, "k_A_per_count": k,
                    "num_points": len(sensor.cal.get("points", [])), "baseline_mean": round(baseline, 2),
                    "min": int(mn), "max": int(mx), "clipping": bool(clipping)}
            cl.send(_HTTP_200_JSON + ujson.dumps(resp).encode())
        return True

    if method == "GET" and path.startswith("/amps"):
        if is_busy():
            cl.send(_HTTP_200_JSON + b'{"ok":false,"err":"busy"}')
            return True
        with busy_region():
            n = 1600; sr = 4000; sensor_id = "c1"; fast = False
            if "?" in path:
                q = path.split("?", 1)[1]
                for p in q.split("&"):
                    if "=" in p:
                        k, v = p.split("=", 1)
                        if k == "n": n = int(v)
                        elif k in ("sr","sample_rate_hz"): sr = int(v)
                        elif k == "sensor_id": sensor_id = v
                        elif k == "fast": fast = v in ("1","true","True")

            sensor = _SENSOR_MANAGER.get_sensor(sensor_id)
            if not sensor:
                cl.send(_HTTP_200_JSON + b'{"ok":false,"err":"sensor_not_found"}')
                return True
            amps, rms, baseline, mn, mx = sensor.measure_amps(n, sr, fast=fast)
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
            sensor_id = body.get("sensor_id", None)
            sensor = _SENSOR_MANAGER.get_sensor(sensor_id or "c1")
            cal = sensor._load_calibration()
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
                sensor._save_calibration()
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
            sensor_id = None
            if "?" in path:
                q = path.split("?", 1)[1]
                for p in q.split("&"):
                    if "=" in p:
                        k, v = p.split("=", 1)
                        if k == "sensor_id": sensor_id = v
            sensor = _SENSOR_MANAGER.get_sensor(sensor_id or "c1")
            if sensor and hasattr(sensor, 'reset_calibration'):
                sensor.reset_calibration()
            else:
                try:
                    os.remove(_CAL_PATH)
                except Exception:
                    pass
        except Exception:
            pass
        cl.send(_HTTP_200_JSON + b'{"ok":true}')
        return True

    return False
