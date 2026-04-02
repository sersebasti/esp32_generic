# http_consts.py (MicroPython)

_HTTP_200_JSON = (
    b"HTTP/1.1 200 OK\r\n"
    b"Content-Type: application/json\r\n"
    b"Cache-Control: no-store\r\n"
    b"Access-Control-Allow-Origin: *\r\n"
    b"Connection: close\r\n\r\n"
)

_HTTP_200_HTML = (
    b"HTTP/1.1 200 OK\r\n"
    b"Content-Type: text/html; charset=utf-8\r\n"
    b"Cache-Control: no-store\r\n"
    b"Access-Control-Allow-Origin: *\r\n"
    b"Connection: close\r\n\r\n"
)

_HTTP_400 = (
    b"HTTP/1.1 400 Bad Request\r\n"
    b"Content-Type: text/plain\r\n"
    b"Cache-Control: no-store\r\n"
    b"Connection: close\r\n\r\n"
    b"Bad Request"
)

# risposta per preflight CORS
_HTTP_204_CORS = (
    b"HTTP/1.1 204 No Content\r\n"
    b"Access-Control-Allow-Origin: *\r\n"
    b"Access-Control-Allow-Methods: GET, POST, PUT, OPTIONS\r\n"
    b"Access-Control-Allow-Headers: Content-Type\r\n"
    b"Connection: close\r\n\r\n"
)

# JSON + CORS (usala per /fs/*)
_HTTP_200_JSON_CORS = (
    b"HTTP/1.1 200 OK\r\n"
    b"Content-Type: application/json\r\n"
    b"Cache-Control: no-store\r\n"
    b"Access-Control-Allow-Origin: *\r\n"
    b"Access-Control-Allow-Methods: GET, POST, PUT, OPTIONS\r\n"
    b"Access-Control-Allow-Headers: Content-Type\r\n"
    b"Connection: close\r\n\r\n"
)