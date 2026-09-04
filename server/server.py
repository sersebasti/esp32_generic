import gc
import socket
import ujson

from server.busy_lock import set_busy
from core.http_consts import (_HTTP_400, _HTTP_204_CORS)

_HANDLERS = []


def clear_handlers():
    del _HANDLERS[:]


def register_handler(name, handler):
    if not name:
        raise ValueError("handler name required")
    if not callable(handler):
        raise TypeError("handler must be callable")
    _HANDLERS.append((name, handler))


def get_handlers():
    return tuple(_HANDLERS)


def _hdr_get(req_bytes, name_lower):
    try:
        head = req_bytes.split(b"\r\n\r\n", 1)[0]
        for line in head.split(b"\r\n")[1:]:
            lower_line = line.lower()
            if lower_line.startswith(name_lower + b":"):
                return line.split(b":", 1)[1].strip()
    except Exception:
        pass
    return None


def _body_initial_and_len(req_bytes):
    try:
        _, body0 = req_bytes.split(b"\r\n\r\n", 1)
    except ValueError:
        return b"", 0

    value = _hdr_get(req_bytes, b"content-length")
    if value is None:
        return body0, None

    try:
        return body0, int(value)
    except Exception:
        return body0, None


def _read_post_json(req, cl, max_len=4096):
    try:
        head, body = req.split(b"\r\n\r\n", 1)
    except ValueError:
        head, body = req, b""

    content_length = 0
    for line in head.split(b"\r\n")[1:]:
        lower_line = line.strip().lower()
        if lower_line.startswith(b"content-length:"):
            try:
                content_length = int(lower_line.split(b":", 1)[1].strip())
            except Exception:
                content_length = 0
            break

    while len(body) < content_length and len(body) < max_len:
        chunk = cl.recv(min(512, content_length - len(body)))
        if not chunk:
            break
        body += chunk

    if content_length and len(body) < content_length:
        raise ValueError("body_incomplete")
    if not body:
        raise ValueError("empty_body")

    return ujson.loads(body.decode())


def _parse_path(line):
    try:
        parts = line.split(" ")
        method = parts[0]
        path = parts[1]

        if path.startswith("http://") or path.startswith("https://"):
            slash = path.find("/", path.find("://") + 3)
            if slash >= 0:
                path = path[slash:]
            else:
                path = "/"

        if not path.startswith("/"):
            path = "/" + path

        return method, path
    except Exception:
        return "GET", "/"


def _client_ip(addr):
    try:
        if isinstance(addr, tuple) and len(addr) > 0:
            return str(addr[0])
    except Exception:
        pass
    return "?"


def _dispatch_request(cl, method, path, req):
    for name, handler in _HANDLERS:
        handled = handler(cl, method, path, req, _read_post_json, _body_initial_and_len)
        if handled:
            if isinstance(handled, dict):
                return handled
            if isinstance(handled, str):
                return handled
            return name
    return None


def _format_result(result):
    if isinstance(result, dict):
        code = result.get("code", "?")
        action = result.get("action", "unknown")
        return "%s %s" % (code, action)
    return str(result)


def _log_http(verbose, message, *args):
    if not verbose:
        return
    try:
        if args:
            print(message % args)
        else:
            print(message)
    except Exception:
        pass


def _configure_server_socket(s, preferred_port, fallback_port):
    try:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    except Exception:
        pass

    try:
        s.bind(("0.0.0.0", preferred_port))
        return preferred_port
    except OSError:
        s.bind(("0.0.0.0", fallback_port))
        return fallback_port


def _accept_client(server_socket):
    try:
        return server_socket.accept()
    except OSError:
        return None, None


def _handle_special_request(cl, method, path, verbose):
    if method == "OPTIONS":
        cl.send(_HTTP_204_CORS)
        _log_http(verbose, "[HTTP] 204 OPTIONS")
        return {"code": 204, "action": "options"}

    if method == "GET" and path.startswith("/favicon.ico"):
        cl.send(_HTTP_204_CORS)
        _log_http(verbose, "[HTTP] 204 favicon")
        return {"code": 204, "action": "favicon"}

    return None


def _read_request(cl):
    cl.settimeout(3.0)
    req = cl.recv(1024)
    if not req:
        return None, None, None

    line = req.split(b"\r\n", 1)[0].decode("utf-8", "ignore")
    method, path = _parse_path(line)
    return req, method, path


def _handle_client(cl, addr, verbose):
    req, method, path = _read_request(cl)
    if not req:
        return None

    _log_http(verbose, "[HTTP] client=%s %s %s", _client_ip(addr), method, path)

    special = _handle_special_request(cl, method, path, verbose)
    if special is not None:
        return special

    result = _dispatch_request(cl, method, path, req)
    if result is None:
        cl.send(_HTTP_400)
        result = {"code": 400, "action": "no_route"}
        _log_http(verbose, "[HTTP] 400 route non trovata: %s %s", method, path)

    _log_http(verbose, "[HTTP] result=%s", _format_result(result))
    return result


def _should_log_exception(exc):
    try:
        if isinstance(exc, OSError) and len(exc.args) > 0:
            return exc.args[0] not in (110, 116)
    except Exception:
        pass
    return True


def _close_client(cl):
    if cl is None:
        return
    try:
        cl.close()
    except Exception:
        pass


def start_server(preferred_port=80, fallback_port=8080, verbose=True):
    try:
        set_busy(False)
    except Exception:
        pass

    s = socket.socket()
    try:
        bound = _configure_server_socket(s, preferred_port, fallback_port)

        s.listen(2)
        s.settimeout(0.5)

        _log_http(verbose, "Status server su http://%s:%d/status", "0.0.0.0", bound)

        while True:
            cl, addr = _accept_client(s)
            if cl is None:
                continue

            try:
                _handle_client(cl, addr, verbose)
            except Exception as e:
                if _should_log_exception(e):
                    _log_http(verbose, "[HTTP] EXC %r", e)

            finally:
                _close_client(cl)
                gc.collect()

    finally:
        try:
            s.close()
        except Exception:
            pass
