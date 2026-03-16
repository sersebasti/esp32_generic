# Logging robusto anche per processi figli Flask
import logging
import os
from flask import Flask, render_template, request, session, jsonify, Response
import requests
import threading
import webbrowser
import json


DEFAULT_ESP32_IP = "192.168.1.116"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
app = Flask(__name__, template_folder=TEMPLATES_DIR)
app.secret_key = 'esp32gui-secret-key'
current_ip = DEFAULT_ESP32_IP


LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "log.txt")
logger = logging.getLogger("esp32gui")
logger.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
if not logger.hasHandlers():
    fh = logging.FileHandler(LOG_FILE, encoding='utf-8')
    fh.setFormatter(formatter)
    logger.addHandler(fh)
    sh = logging.StreamHandler()
    sh.setFormatter(formatter)
    logger.addHandler(sh)
logger.info("[SERVER] Flask app avviata")


# Imposta logging su file
LOG_FILE = os.path.join(BASE_DIR, "log.txt")
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
    handlers=[logging.FileHandler(LOG_FILE, encoding='utf-8'), logging.StreamHandler()]
)
logging.info("[SERVER] Flask app avviata")


@app.route('/', methods=['GET'])
def index():
    return render_template('index.html', default_ip=current_ip)


@app.route('/api/generic-get', methods=['GET'])
def generic_get():
    ip = (request.args.get("ip") or current_ip or "").strip()
    path = (request.args.get("path") or "/").strip()

    if not ip:
        return jsonify({"ok": False, "error": "missing_ip"}), 400

    if not path.startswith("/"):
        path = "/" + path

    target_url = f"http://{ip}{path}"

    try:
        upstream = requests.get(target_url, timeout=12)
    except requests.RequestException as exc:
        return jsonify({
            "ok": False,
            "error": "upstream_unreachable",
            "detail": str(exc),
            "target": target_url,
        }), 502

    content_type = (upstream.headers.get("Content-Type") or "").lower()

    if "application/json" in content_type:
        try:
            body = upstream.json()
        except ValueError:
            body = {
                "ok": False,
                "error": "invalid_upstream_json",
                "target": target_url,
                "raw": upstream.text,
            }
        return jsonify(body), upstream.status_code

    pass_headers = {}
    for name in ("Content-Type", "Content-Length", "Content-Disposition", "Cache-Control"):
        value = upstream.headers.get(name)
        if value:
            pass_headers[name] = value

    return Response(upstream.content, status=upstream.status_code, headers=pass_headers)


@app.route('/api/generic-post', methods=['POST'])
def generic_post():
    body = request.get_json(silent=True) or {}

    ip = str(body.get("ip") or request.args.get("ip") or current_ip or "").strip()
    path = str(body.get("path") or request.args.get("path") or "/").strip()
    payload = body.get("payload", {})

    if not ip:
        return jsonify({"ok": False, "error": "missing_ip"}), 400

    if not path.startswith("/"):
        path = "/" + path

    target_url = f"http://{ip}{path}"

    try:
        upstream = requests.post(target_url, json=payload, timeout=12)
    except requests.RequestException as exc:
        return jsonify({
            "ok": False,
            "error": "upstream_unreachable",
            "detail": str(exc),
            "target": target_url,
        }), 502

    content_type = (upstream.headers.get("Content-Type") or "").lower()

    if "application/json" in content_type:
        try:
            response_body = upstream.json()
        except ValueError:
            response_body = {
                "ok": False,
                "error": "invalid_upstream_json",
                "target": target_url,
                "raw": upstream.text,
            }
        return jsonify(response_body), upstream.status_code

    pass_headers = {}
    for name in ("Content-Type", "Content-Length", "Content-Disposition", "Cache-Control"):
        value = upstream.headers.get(name)
        if value:
            pass_headers[name] = value

    return Response(upstream.content, status=upstream.status_code, headers=pass_headers)


@app.route('/api/generic-delete', methods=['POST'])
def generic_delete():
    body = request.get_json(silent=True) or {}

    ip = str(body.get("ip") or request.args.get("ip") or current_ip or "").strip()
    path = str(body.get("path") or request.args.get("path") or "/").strip()
    payload = body.get("payload", {})

    if not ip:
        return jsonify({"ok": False, "error": "missing_ip"}), 400

    if not path.startswith("/"):
        path = "/" + path

    target_url = f"http://{ip}{path}"

    try:
        upstream = requests.delete(target_url, json=payload, timeout=12)
    except requests.RequestException as exc:
        return jsonify({
            "ok": False,
            "error": "upstream_unreachable",
            "detail": str(exc),
            "target": target_url,
        }), 502

    content_type = (upstream.headers.get("Content-Type") or "").lower()

    if "application/json" in content_type:
        try:
            response_body = upstream.json()
        except ValueError:
            response_body = {
                "ok": False,
                "error": "invalid_upstream_json",
                "target": target_url,
                "raw": upstream.text,
            }
        return jsonify(response_body), upstream.status_code

    pass_headers = {}
    for name in ("Content-Type", "Content-Length", "Content-Disposition", "Cache-Control"):
        value = upstream.headers.get(name)
        if value:
            pass_headers[name] = value

    return Response(upstream.content, status=upstream.status_code, headers=pass_headers)


# /api/save-phase endpoint removed — the UI now forwards phase_shift to the device via /calibrate


if __name__ == "__main__":
    host = "0.0.0.0"
    port = 8000
    # Open the local UI in the default browser after the server starts.
    threading.Timer(0.8, lambda: webbrowser.open(f"http://127.0.0.1:{port}")).start()
    app.run(host=host, port=port, debug=False)
