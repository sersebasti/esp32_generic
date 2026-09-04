# fs/api.py (MicroPython)
import os, gc, ujson
from core.http_consts import _HTTP_200_JSON_CORS, _HTTP_400

def _bad_path(p):
    return (not p) or (".." in p) or p.endswith("/")

def _query_arg(path, key):
    if "?" not in path:
        return None
    try:
        q = path.split("?", 1)[1]
        for p in q.split("&"):
            if "=" in p:
                k, v = p.split("=", 1)
                if k == key:
                    return v
    except:
        pass
    return None

def handle(cl, method, path, req, _read_post_json, _body_initial_and_len):
    """
    Gestisce endpoint /fs/*.
    Ritorna True se gestito, False altrimenti.
    """

    # --- LIST ---
    if method == "GET" and path.startswith("/fs/list"):
        try:
            # directory target da query (?path=/dir). Default: root "/"
            target = _query_arg(path, "path") or _query_arg(path, "dir")
            if not target or target == "/":
                target = "/"
            else:
                # normalizza: assoluto, senza slash finale
                target = target if target.startswith("/") else ("/" + target)
                if target.endswith("/") and target != "/":
                    target = target[:-1]

            # helper compatibili con path assoluti/relativi su MicroPython
            def _listdir_safe(p):
                try:
                    return os.listdir(p)
                except:
                    try:
                        q = p.lstrip("/")
                        return os.listdir(q)
                    except:
                        return None
            def _stat_safe(p):
                try:
                    return os.stat(p)
                except:
                    try:
                        q = p.lstrip("/")
                        return os.stat(q)
                    except:
                        return None

            # elenca contenuti
            names = None
            if target == "/":
                # alcune build richiedono stringa vuota per root
                names = _listdir_safe("/") or _listdir_safe("") or _listdir_safe(".")
            else:
                names = _listdir_safe(target)
            if names is None:
                cl.send(_HTTP_200_JSON_CORS + b'{"ok":false,"err":"bad_dir"}')
                return True

            files = []
            for name in names:
                full = (target + "/" + name) if target != "/" else ("/" + name)
                st = _stat_safe(full)
                if st:
                    size = st[6] if len(st) > 6 else None
                    mode = st[0] if len(st) > 0 else 0
                    is_dir = bool(mode & 0x4000)  # S_IFDIR
                else:
                    size = None
                    is_dir = False
                files.append({"name": name, "size": size, "is_dir": is_dir})
            cl.send(_HTTP_200_JSON_CORS + ujson.dumps({"ok": True, "path": target, "files": files}).encode())
        except:
            cl.send(_HTTP_200_JSON_CORS + b'{"ok":false,"err":"list_failed"}')
        return True

    # --- DELETE ---
    if method == "POST" and path.startswith("/fs/delete"):
        try:
            body = _read_post_json(req, cl)
            fname = (body.get("path") or "").strip()
            if _bad_path(fname):
                cl.send(_HTTP_200_JSON_CORS + b'{"ok":false,"err":"bad_path"}')
            else:
                os.remove(fname)
                cl.send(_HTTP_200_JSON_CORS + ujson.dumps({"ok": True, "deleted": fname}).encode())
        except:
            cl.send(_HTTP_200_JSON_CORS + b'{"ok":false,"err":"delete_failed"}')
        return True

    # --- RENAME ---
    if method == "POST" and path.startswith("/fs/rename"):
        try:
            body = _read_post_json(req, cl)
            src = (body.get("src") or "").strip()
            dst = (body.get("dst") or "").strip()
            if _bad_path(src) or _bad_path(dst):
                cl.send(_HTTP_200_JSON_CORS + b'{"ok":false,"err":"bad_path"}')
            else:
                os.rename(src, dst)
                cl.send(_HTTP_200_JSON_CORS + ujson.dumps({"ok": True, "renamed": [src, dst]}).encode())
        except:
            cl.send(_HTTP_200_JSON_CORS + b'{"ok":false,"err":"rename_failed"}')
        return True

    # --- UPLOAD ---
    if method in ("POST", "PUT") and path.startswith("/fs/upload"):
        try:
            # path di destinazione da query (?to=/file.txt) oppure default
            to_path = _query_arg(path, "to") or _query_arg(path, "path") or _query_arg(path, "filename")
            if to_path:
                to_path = to_path if to_path.startswith("/") else ("/" + to_path)

            if _bad_path(to_path):
                cl.send(_HTTP_200_JSON_CORS + b'{"ok":false,"err":"bad_path"}')
                return True

            body0, total = _body_initial_and_len(req)
            if body0 is None or total is None:
                cl.send(_HTTP_200_JSON_CORS + b'{"ok":false,"err":"no_content_length"}')
                return True
            if total <= 0:
                cl.send(_HTTP_200_JSON_CORS + b'{"ok":false,"err":"empty"}')
                return True
            if total > 512*1024:
                cl.send(_HTTP_200_JSON_CORS + b'{"ok":false,"err":"too_big"}')
                return True

            # crea dir un livello (facoltativo)
            try:
                dname = to_path.rsplit("/", 1)[0]
                if dname and dname not in ("", "/"):
                    try: os.mkdir(dname)
                    except: pass
            except: pass

            written = 0
            with open(to_path, "wb") as f:
                if body0:
                    f.write(body0); written += len(body0)
                while written < total:
                    chunk = cl.recv(min(1024, total - written))
                    if not chunk:
                        break
                    f.write(chunk); written += len(chunk)

            gc.collect()
            ok = (written == total)
            cl.send(_HTTP_200_JSON_CORS + ujson.dumps({"ok": ok, "path": to_path, "size": written}).encode())
        except:
            cl.send(_HTTP_200_JSON_CORS + b'{"ok":false,"err":"upload_failed"}')
        return True

    # --- DOWNLOAD ---
    if method == "GET" and path.startswith("/fs/download"):
        try:
            fname = _query_arg(path, "path")
            if _bad_path(fname):
                cl.send(_HTTP_200_JSON_CORS + b'{"ok":false,"err":"bad_path"}')
            else:
                with open(fname, "rb") as f:
                    data = f.read()
                # risposta binaria (octet-stream) con CORS
                cl.send(b"HTTP/1.1 200 OK\r\n"
                        b"Content-Type: application/octet-stream\r\n"
                        b"Access-Control-Allow-Origin: *\r\n"
                        b"Access-Control-Allow-Methods: GET, POST, PUT, OPTIONS\r\n"
                        b"Access-Control-Allow-Headers: Content-Type\r\n"
                        b"Connection: close\r\n\r\n" + data)
        except:
            cl.send(_HTTP_200_JSON_CORS + b'{"ok":false,"err":"download_failed"}')
        return True

    return False  # non gestito
