# adc_api.py
import ujson
from http_consts import _HTTP_200_JSON
from busy_lock import BUSY
import adc_scope

def handle(cl, method, path):
    # /adc/scope_counts
    if method == "GET" and path.startswith("/adc/scope_counts"):
        if not adc_scope:
            cl.send(_HTTP_200_JSON + b'{"ok":false,"err":"adc_scope_module_missing"}')
            return True
        if BUSY["v"]:
            cl.send(_HTTP_200_JSON + b'{"ok":false,"err":"busy"}')
            return True
        BUSY["v"] = True
        try:
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
        finally:
            BUSY["v"] = False
        return True
    return False
