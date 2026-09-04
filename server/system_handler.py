# server/system_api.py
from core.http_consts import _HTTP_200_JSON


def handle(cl, method, path, req=None, read_post_json=None, body_initial_and_len=None):
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
        return {"code": 200, "action": "reboot"}
    return False
