# core/system_api.py
from core.http_consts import _HTTP_200_JSON


def handle(cl, method, path):
    # POST /reboot
    if method == "POST" and path.startswith("/reboot"):
        cl.send(_HTTP_200_JSON + b'{"ok":true}')
        try:
            cl.close()
        except Exception:
            pass
        try:
            import machine
            machine.reset()
        except Exception:
            pass
        return True
    return False
