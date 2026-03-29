# webrepl_api.py
# Gestione WebREPL: avvio solo se feature abilitata

from core.config import feature_enabled
import os

webrepl = None

# Funzione per avviare WebREPL solo se abilitato

def start_webrepl():
    global webrepl
    from core.config import feature_enabled
    if not feature_enabled("webrepl"):
        return False
    ensure_webrepl_config()  # Garantisce la presenza del file di configurazione
    try:
        import webrepl as _webrepl
        _webrepl.start()
        webrepl = _webrepl
        return True
    except Exception as e:
        try:
            print("[WEBREPL][ERROR]", repr(e))
        except Exception:
            pass
        webrepl = None
        return False

# Funzione per fermare WebREPL (se supportato)
def stop_webrepl():
    global webrepl
    if webrepl and hasattr(webrepl, "stop"):
        try:
            webrepl.stop()
            webrepl = None
            return True
        except Exception:
            pass
    return False

# (Opzionale) Funzione di stato

def webrepl_status():
    return bool(webrepl)

# (Opzionale) Qui puoi aggiungere un handle HTTP per esporre stato/controllo
def handle_webrepl(cl, method, path, req=None, _read_post_json=None):
    import ujson
    if path == "/webrepl/status" and method == "GET":
        cl.send(b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n\r\n" + ujson.dumps({"ok": True, "enabled": feature_enabled("webrepl"), "running": webrepl_status()}).encode())
        return True
    if path == "/webrepl/start" and method == "POST":
        ok = start_webrepl()
        cl.send(b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n\r\n" + ujson.dumps({"ok": ok, "running": webrepl_status()}).encode())
        return True
    if path == "/webrepl/stop" and method == "POST":
        ok = stop_webrepl()
        cl.send(b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n\r\n" + ujson.dumps({"ok": ok, "running": webrepl_status()}).encode())
        return True
    return False

def ensure_webrepl_config(password=b'1234'):
    from core.config import feature_enabled
    if not feature_enabled("webrepl"):
        return False
    files = os.listdir()
    if "webrepl_cfg.py" not in files:
        with open("webrepl_cfg.py", "w") as f:
            f.write("PASS = %r\nENABLED = True\n" % password)
    return True
