# system_api.py
from core.http_consts import _HTTP_200_JSON

def handle(cl, method, path):
    # POST /reboot  (stesso comportamento dell'originale)
    if method == "POST" and path.startswith("/reboot"):
        cl.send(_HTTP_200_JSON + b'{"ok":true}')
        try:
            cl.close()
        except:
            pass
        import machine
        machine.reset()
        return True
    return False
