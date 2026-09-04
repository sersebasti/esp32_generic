# pzem_017/pzem017_api.py

import ujson
from core.http_consts import _HTTP_200_JSON

from pzem_017.pzem_rs485 import read_pzem017


def get_pzem017():
    return read_pzem017()


def handle_pzem017(cl, method, path, req=None, read_post_json=None):
    try:
        path_base = path.split("?", 1)[0]

        if method == "GET" and path_base == "/pzem017":
            data = get_pzem017()
            cl.send(_HTTP_200_JSON + ujson.dumps(data).encode())
            return True

        return False

    except Exception as e:
        cl.send(
            _HTTP_200_JSON +
            ujson.dumps({
                "ok": False,
                "err": "server_exception",
                "msg": str(e)
            }).encode()
        )
        return True