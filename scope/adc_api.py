# adc_api.py (scope)
import os
import ujson

from core.http_consts import _HTTP_200_JSON, _HTTP_200_JSON_CORS
from server.busy_lock import is_busy, busy_region
try:
    import ustruct as struct
except Exception:
    import struct

# Inizializza il manager dei sensori on-demand (singleton)
_SENSOR_MANAGER = None


def _get_sensor_manager():
    global _SENSOR_MANAGER
    if _SENSOR_MANAGER is None:
        from .sensor_manager import CurrentSensorManager

        _SENSOR_MANAGER = CurrentSensorManager()
    return _SENSOR_MANAGER


def _get_sensor(sensor_id):
    return _get_sensor_manager().get_sensor(sensor_id)


def _get_generic_sensor_class():
    from .generic_sensor import GenericSensor

    return GenericSensor

_CAL_PATH = "scope/calibrate.json"

_HTTP_200_OCTET_CORS = (
    b"HTTP/1.1 200 OK\r\n"
    b"Content-Type: application/octet-stream\r\n"
    b"Cache-Control: no-store\r\n"
    b"Access-Control-Allow-Origin: *\r\n"
    b"Access-Control-Allow-Methods: GET, POST, PUT, OPTIONS\r\n"
    b"Access-Control-Allow-Headers: Content-Type\r\n"
    b"Connection: close\r\n\r\n"
)

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

    # _fit_k removed; use GenericSensor.fit_k instead


def _to_bool(v):
    return v in ("1", "true", "True", "yes", "on")

def handle(cl, method, path, req=None, _read_post_json=None):
    path_base = path.split("?", 1)[0]
    
    # --- Endpoint per misura tensione RMS (solo sensori voltage) ---
    if method == "GET" and path.startswith("/volts"):
            if is_busy():
                cl.send(_HTTP_200_JSON + b'{"ok":false,"err":"busy"}')
                return True
            with busy_region():
                n = 1600; sr = 4000; sensor_id = "v1"; fast = False
                if "?" in path:
                    q = path.split("?", 1)[1]
                    for p in q.split("&"):
                        if "=" in p:
                            k, v = p.split("=", 1)
                            if k == "n": n = int(v)
                            elif k in ("sr","sample_rate_hz"): sr = int(v)
                            elif k == "sensor_id": sensor_id = v
                            elif k == "fast": fast = v in ("1","true","True")
                sensor = _get_sensor(sensor_id)
                if not sensor:
                    cl.send(_HTTP_200_JSON + b'{"ok":false,"err":"sensor_not_found"}')
                    return True
                # Verifica tipo sensore
                if not hasattr(sensor, 'type') or getattr(sensor, 'type', None) != 'voltage':
                    cl.send(_HTTP_200_JSON + b'{"ok":false,"err":"not_voltage_sensor"}')
                    return True
                volts, rms, baseline, mn, mx = sensor.measure_volts(n, sr, fast=fast)
                clipping = (mn < 50) or (mx > 4040)
                out = {"ok": True, "volts_rms": round(volts, 3), "rms_counts": round(rms, 2),
                       "baseline_mean": round(baseline, 2),
                       "min": int(mn), "max": int(mx), "clipping": bool(clipping)}
                cl.send(_HTTP_200_JSON + ujson.dumps(out).encode())
            return True
    # Endpoint: /sensors - restituisce la lista dei sensori da sensors.json
    if method == "GET" and path_base == "/sensors":
            try:
                with open("scope/sensors.json") as f:
                    sensors_cfg = ujson.load(f)
                sensors = sensors_cfg.get("sensors", [])
                cl.send(_HTTP_200_JSON + ujson.dumps({"ok": True, "sensors": sensors}).encode())
            except Exception as e:
                cl.send(_HTTP_200_JSON + ujson.dumps({"ok": False, "err": str(e)}).encode())
            return True
    # /adc/scope_counts?sensor_id=c1
    if method == "GET" and path.startswith("/adc/scope_counts"):
        if is_busy():
            cl.send(_HTTP_200_JSON + b'{"ok":false,"err":"busy"}')
            return True
        with busy_region():
            n = 1024; sr = 4000; sensor_id = "c1"; fast = False
            binary = path.startswith("/adc/scope_counts_bin")
            if "?" in path:
                q = path.split("?", 1)[1]
                for p in q.split("&"):
                    if "=" in p:
                        k, v = p.split("=", 1)
                        if k == "n": n = int(v)
                        elif k in ("sr","sample_rate_hz"): sr = int(v)
                        elif k == "sensor_id": sensor_id = v
                        elif k == "fast": fast = v in ("1","true","True")
                        elif k == "binary": binary = _to_bool(v)
            sensor = _get_sensor(sensor_id)
            if not sensor:
                cl.send(_HTTP_200_JSON + b'{"ok":false,"err":"sensor_not_found"}')
                return True
            arr, sr = sensor.sample_counts(n, sr, fast=fast)
            mean, rms = sensor.stats_counts(arr)
            if binary:
                cl.send(_HTTP_200_OCTET_CORS)
                cl.send(struct.pack("<4sHII", b"SCB1", 1, len(arr), int(sr)))
                i = 0
                chunk_samples = 96
                while i < len(arr):
                    chunk = arr[i:i + chunk_samples]
                    buf = bytearray(len(chunk) * 2)
                    j = 0
                    for v in chunk:
                        cv = int(v)
                        if cv < 0:
                            cv = 0
                        elif cv > 65535:
                            cv = 65535
                        buf[j] = cv & 0xFF
                        buf[j + 1] = (cv >> 8) & 0xFF
                        j += 2
                    cl.send(buf)
                    i += chunk_samples
                del arr
                return True
            payload = ujson.dumps({
                "ok": True,
                "n": len(arr),
                "sample_rate_hz": sr,
                "counts": arr,
                "counts_mean": round(mean, 2),
                "counts_rms": round(rms, 2)
            })
            cl.send(_HTTP_200_JSON + payload.encode())
            del arr
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
        sensor = _get_sensor(sensor_id)
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
        n = 1600; sr = 4000; value = None; sensor_id = "c1"; fast = False
        value_key = "amps"; k_key = "k_A_per_count"; hint = "usa /calibrate?amp=0 per baseline, /calibrate?amp=<A> per aggiungere un punto"
        if "?" in path:
            q = path.split("?", 1)[1]
            for p in q.split("&"):
                if "=" in p:
                    k, v = p.split("=", 1)
                    if k == "n": n = int(v)
                    elif k in ("sr","sample_rate_hz"): sr = int(v)
                    elif k == "amp":
                        try: value = float(v)
                        except: value = None
                        value_key = "amps"; k_key = "k_A_per_count"
                    elif k == "volt":
                        try: value = float(v)
                        except: value = None
                        value_key = "volts"; k_key = "k_V_per_count"
                    elif k == "sensor_id": sensor_id = v
                    elif k == "fast": fast = v in ("1","true","True")

        sensor = _get_sensor(sensor_id)
        if not sensor:
            cl.send(_HTTP_200_JSON + b'{"ok":false,"err":"sensor_not_found"}')
            return True

        # Se il sensore è di tipo voltage, cambia i parametri di default
        if hasattr(sensor, 'type') and getattr(sensor, 'type', None) == 'voltage':
            value_key = "volts"; k_key = "k_V_per_count"
            hint = "usa /calibrate?volt=0 per baseline, /calibrate?volt=<V> per aggiungere un punto"

        if value is None:
            cal = sensor._load_calibration()
            if "points" not in cal: cal["points"] = []
            resp = {"ok": True, "cal": cal, "hint": hint}
            cl.send(_HTTP_200_JSON + ujson.dumps(resp).encode())
            return True

        if value == 0.0:
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
            pt, k = sensor.add_calibration_point(value, n, sr, fast=fast, value_key=value_key, rms_key="rms_counts", k_key=k_key)
            arr, sr = sensor.sample_counts(n, sr, fast=fast)
            baseline = float(sensor.cal.get("baseline_mean", sum(arr)/len(arr)))
            mn = min(arr); mx = max(arr)
            clipping = (mn < 50) or (mx > 4040)
            resp = {"ok": True, "added": pt, k_key: k,
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

            sensor = _get_sensor(sensor_id)
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

    # --- Endpoint per misura potenza RMS (solo /power) ---
    if method == "GET" and (path.split("?", 1)[0] == "/power"):
        if is_busy():
            cl.send(_HTTP_200_JSON + b'{"ok":false,"err":"busy"}')
            return True
        with busy_region():
            n = 1600; sr = 4000; fast = False
            voltage_sensor_id = "v1"
            current_sensor_id = "c1"
            phase_shift = None
            if "?" in path:
                q = path.split("?", 1)[1]
                for p in q.split("&"):
                    if "=" in p:
                        k, v = p.split("=", 1)
                        if k == "n": n = int(v)
                        elif k in ("sr", "sample_rate_hz"): sr = int(v)
                        elif k == "fast": fast = v in ("1","true","True")
                        elif k in ("voltage_sensor_id", "voltage_id", "v_sensor_id"):
                            voltage_sensor_id = v
                        elif k in ("current_sensor_id", "current_id", "i_sensor_id"):
                            current_sensor_id = v
                        elif k in ("phase_shift", "phase-shift", "v_phase_shift"):
                            try:
                                phase_shift = int(v)
                            except Exception:
                                phase_shift = None

            # Future improvement: if phase_shift is not provided in the query,
            # load it from the saved calibration of the voltage/current sensor.

            voltage_sensor = _get_sensor(voltage_sensor_id)
            current_sensor = _get_sensor(current_sensor_id)

            if not voltage_sensor:
                cl.send(_HTTP_200_JSON + ujson.dumps({"ok": False, "err": "sensor_not_found", "sensor_id": voltage_sensor_id}).encode())
                return True
            if not current_sensor:
                cl.send(_HTTP_200_JSON + ujson.dumps({"ok": False, "err": "sensor_not_found", "sensor_id": current_sensor_id}).encode())
                return True

            voltage_type = getattr(voltage_sensor, 'type', None)
            current_type = getattr(current_sensor, 'type', 'current')

            if voltage_type != 'voltage':
                cl.send(_HTTP_200_JSON + ujson.dumps({"ok": False, "err": "not_voltage_sensor", "sensor_id": voltage_sensor_id}).encode())
                return True
            if current_type != 'current':
                cl.send(_HTTP_200_JSON + ujson.dumps({"ok": False, "err": "not_current_sensor", "sensor_id": current_sensor_id}).encode())
                return True

            # Pass optional phase_shift to measurement
            generic_sensor = _get_generic_sensor_class()
            p = generic_sensor.measure_instant_power_pair(
                voltage_sensor,
                current_sensor,
                n=n,
                sample_rate_hz=sr,
                fast=fast,
                phase_shift=phase_shift,
            )

            out = {
                "ok": True,
                "mode": "instantaneous_pair",
                "voltage_sensor_id": voltage_sensor_id,
                "current_sensor_id": current_sensor_id,
                "n": int(p["n"]),
                "sample_rate_hz": int(p["sample_rate_hz"]),
                "fast": bool(fast),
                "volts_rms": round(p["volts_rms"], 3),
                "amps_rms": round(p["amps_rms"], 3),
                "power_w": round(p["power_w"], 3),
                "apparent_power_va": round(p["apparent_power_va"], 3),
                "power_factor": round(p["power_factor"], 4),
                "phase_shift_samples": int(p.get("phase_shift_samples", 0)),
                "clipping": bool(p["voltage"]["clipping"] or p["current"]["clipping"]),
                "voltage": {
                    "baseline_mean": round(p["voltage"]["baseline_mean"], 2),
                    "min": int(p["voltage"]["min"]),
                    "max": int(p["voltage"]["max"]),
                    "clipping": bool(p["voltage"]["clipping"]),
                },
                "current": {
                    "baseline_mean": round(p["current"]["baseline_mean"], 2),
                    "min": int(p["current"]["min"]),
                    "max": int(p["current"]["max"]),
                    "clipping": bool(p["current"]["clipping"]),
                }
            }
            cl.send(_HTTP_200_JSON + ujson.dumps(out).encode())
        return True

    if method in ("POST", "DELETE") and path.startswith("/calibrate/delete"):
        try:
            if _read_post_json is None or req is None:
                raise Exception("no_json_parser")
            body = _read_post_json(req, cl)
            idx = body.get("index", None)
            amp = body.get("amps", None)
            rms = body.get("rms_counts", None)
            sensor_id = body.get("sensor_id", None)
            sensor = _get_sensor(sensor_id or "c1")
            cal = sensor._load_calibration()
            pts = cal.get("points", []) or []

            removed = None
            # Determina le chiavi da usare in base al tipo di sensore
            value_key = "amps"
            k_key = "k_A_per_count"
            if hasattr(sensor, 'type') and getattr(sensor, 'type', None) == 'voltage':
                value_key = "volts"
                k_key = "k_V_per_count"

            if isinstance(idx, int) and 0 <= idx < len(pts):
                removed = pts.pop(idx)
            elif (amp is not None) and (rms is not None):
                for i, p in enumerate(pts):
                    try:
                        if value_key == "amps" and float(p.get("amps")) == float(amp) and float(p.get("rms_counts")) == float(rms):
                            removed = pts.pop(i)
                            break
                        elif value_key == "volts" and float(p.get("volts")) == float(amp) and float(p.get("rms_counts")) == float(rms):
                            removed = pts.pop(i)
                            break
                    except Exception:
                        pass

            if removed is None:
                cl.send(_HTTP_200_JSON_CORS + ujson.dumps({"ok": False, "err": "not_found"}).encode())
            else:
                cal["points"] = pts
                if pts:
                    generic_sensor = _get_generic_sensor_class()
                    k = generic_sensor.fit_k(pts, value_key=value_key, rms_key="rms_counts")
                    cal[k_key] = round(k, 9)
                else:
                    cal[k_key] = 0.0
                sensor.cal = cal  # Aggiorna la variabile in memoria
                sensor._save_calibration()
                resp = {"ok": True, "removed": removed,
                        "num_points": len(pts),
                        k_key: cal.get(k_key, 0.0)}
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
            sensor = _get_sensor(sensor_id or "c1")
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

    # --- Endpoint per calibrazione (POST) ---
    if method == "POST" and path.startswith("/calibrate"):
        try:
            if _read_post_json is None or req is None:
                raise Exception("no_json_parser")
            body = _read_post_json(req, cl) or {}

            # defaults
            n = int(body.get("n", 1600))
            sr = int(body.get("sr", body.get("sample_rate_hz", 4000)))
            sensor_id = body.get("sensor_id", "c1")
            fast = bool(body.get("fast", False))

            value = None
            value_key = "amps"
            k_key = "k_A_per_count"
            hint = "usa /calibrate?amp=0 per baseline, /calibrate?amp=<A> per aggiungere un punto"

            # decide which value is present in payload
            if "amp" in body:
                try:
                    value = float(body.get("amp"))
                except Exception:
                    value = None
                value_key = "amps"
                k_key = "k_A_per_count"
            if "volt" in body:
                try:
                    value = float(body.get("volt"))
                except Exception:
                    value = None
                value_key = "volts"
                k_key = "k_V_per_count"

            sensor = _get_sensor(sensor_id)
            if not sensor:
                cl.send(_HTTP_200_JSON_CORS + ujson.dumps({"ok": False, "err": "sensor_not_found"}).encode())
                return True

            # if sensor is voltage, adjust keys/hint
            if hasattr(sensor, 'type') and getattr(sensor, 'type', None) == 'voltage':
                value_key = "volts"
                k_key = "k_V_per_count"
                hint = "usa /calibrate?volt=0 per baseline, /calibrate?volt=<V> per aggiungere un punto"

            # support saving phase_shift if provided in payload
            try:
                if 'phase_shift' in body:
                    try:
                        ps = int(body.get('phase_shift'))
                        sensor.cal = sensor._load_calibration() if getattr(sensor, 'cal', None) is None else sensor.cal
                        sensor.cal['phase_shift'] = ps
                        sensor._save_calibration()
                    except Exception:
                        # ignore invalid phase_shift value, do not fail the whole request
                        pass
            except Exception:
                pass

            # if no value provided return calibration info
            if value is None:
                cal = sensor._load_calibration()
                if "points" not in cal: cal["points"] = []
                resp = {"ok": True, "cal": cal, "hint": hint}
                cl.send(_HTTP_200_JSON_CORS + ujson.dumps(resp).encode())
                return True

            # baseline acquisition
            if float(value) == 0.0:
                if is_busy():
                    cl.send(_HTTP_200_JSON_CORS + b'{"ok":false,"err":"busy"}')
                    return True
                with busy_region():
                    baseline = sensor.calibrate_baseline(n, sr, fast=fast)
                    # if phase_shift provided, ensure it's stored (again) and persisted
                    try:
                        if 'phase_shift' in body:
                            try:
                                ps = int(body.get('phase_shift'))
                                sensor.cal = sensor._load_calibration() if getattr(sensor, 'cal', None) is None else sensor.cal
                                sensor.cal['phase_shift'] = ps
                                sensor._save_calibration()
                            except Exception:
                                pass
                    except Exception:
                        pass
                    cal = sensor._load_calibration()
                    resp = {"ok": True, "saved": {"baseline_mean": cal.get("baseline_mean"), "n0": cal.get("n0"), "sr0": cal.get("sr0")}}
                    # include phase_shift in response if present
                    if 'phase_shift' in cal:
                        resp['phase_shift'] = cal.get('phase_shift')
                    cl.send(_HTTP_200_JSON_CORS + ujson.dumps(resp).encode())
                return True

            # add calibration point
            if is_busy():
                cl.send(_HTTP_200_JSON_CORS + b'{"ok":false,"err":"busy"}')
                return True
            with busy_region():
                pt, k = sensor.add_calibration_point(value, n, sr, fast=fast, value_key=value_key, rms_key="rms_counts", k_key=k_key)
                arr, sr = sensor.sample_counts(n, sr, fast=fast)
                baseline = float(sensor.cal.get("baseline_mean", sum(arr)/len(arr)))
                mn = min(arr); mx = max(arr)
                clipping = (mn < 50) or (mx > 4040)
                # if phase_shift provided, persist it alongside the added point
                try:
                    if 'phase_shift' in body:
                        try:
                            ps = int(body.get('phase_shift'))
                            sensor.cal = sensor._load_calibration() if getattr(sensor, 'cal', None) is None else sensor.cal
                            sensor.cal['phase_shift'] = ps
                            sensor._save_calibration()
                        except Exception:
                            pass
                except Exception:
                    pass
                resp = {"ok": True, "added": pt, k_key: k,
                        "num_points": len(sensor.cal.get("points", [])), "baseline_mean": round(baseline, 2),
                        "min": int(mn), "max": int(mx), "clipping": bool(clipping)}
                # include phase_shift in response if present
                cal_now = sensor._load_calibration()
                if 'phase_shift' in cal_now:
                    resp['phase_shift'] = cal_now.get('phase_shift')
                cl.send(_HTTP_200_JSON_CORS + ujson.dumps(resp).encode())
            return True
        except Exception:
            try:
                cl.send(_HTTP_200_JSON_CORS + b'{"ok":false,"err":"invalid_request"}')
            except Exception:
                pass
        return True

    return False
