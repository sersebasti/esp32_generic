# Logging robusto anche per processi figli Flask
import logging
import os
from flask import Flask, render_template, request
import requests
import threading
import webbrowser


DEFAULT_ESP32_IP = "192.168.1.6"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
app = Flask(__name__, template_folder=TEMPLATES_DIR)
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







@app.route("/", methods=["GET", "POST"])
def index():
        global current_ip
        status = ""
        sensors = None
        status_info = None
        status_raw = None

        # Gestione IP da POST o GET
        ip = current_ip
        if request.method == "POST":
            ip = request.form.get("ip", "").strip() or current_ip
            current_ip = ip

        # Chiamata a /status sempre (sia GET che POST)
        try:
            url_status = f"http://{ip}/status"
            logger.info(f"[REQUEST] GET {url_status}")
            resp = requests.get(url_status, timeout=2)
            logger.info(f"[RESPONSE] {resp.status_code} {resp.text}")
            if resp.ok:
                try:
                    data = resp.json()
                    status_raw = data
                except Exception as e:
                    status_raw = f"Errore parsing JSON: {e}"
                    logger.error(f"[ERROR] Parsing JSON /status: {e}")
                # Verifica che abbia i campi attesi
                if isinstance(status_raw, dict) and status_raw.get("ip") and status_raw.get("ssid"):
                    status_info = status_raw
                    status = f"Connesso a {status_info.get('ssid')} (IP: {status_info.get('ip')})"
                else:
                    status = "Risposta /status non valida."
                    logger.warning(f"[WARNING] Risposta /status non valida: {status_raw}")
            else:
                status = f"Errore HTTP /status: {resp.status_code}"
                status_raw = status
                logger.error(f"[ERROR] HTTP /status: {resp.status_code}")
        except Exception as e:
            status = f"Errore /status: {e}"
            status_raw = status
            logger.error(f"[EXCEPTION] /status: {e}")

        # Prova a recuperare la lista sensori dall'ESP32
        try:
            url_sensors = f"http://{ip}/sensors"
            logger.info(f"[REQUEST] GET {url_sensors}")
            resp = requests.get(url_sensors, timeout=2)
            logger.info(f"[RESPONSE] {resp.status_code} {resp.text}")
            if resp.ok:
                data = resp.json()
                if isinstance(data, dict) and data.get("ok") and isinstance(data.get("sensors"), list):
                    sensors = data["sensors"]
                else:
                    sensors = "Nessun sensore trovato o risposta non valida."
                    logger.warning(f"[WARNING] Risposta /sensors non valida: {data}")
            else:
                sensors = f"Errore HTTP: {resp.status_code}"
                logger.error(f"[ERROR] HTTP /sensors: {resp.status_code}")
        except Exception as e:
            sensors = f"Errore: {e}"
            logger.error(f"[EXCEPTION] /sensors: {e}")
        # Garantisce che sensors sia sempre una lista per il template
        if not isinstance(sensors, list):
            sensors = []
        return render_template("index.html", ip=ip, status=status, sensors=sensors, status_info=status_info, status_raw=status_raw)


if __name__ == "__main__":
    host = "0.0.0.0"
    port = 8000
    # Open the local UI in the default browser after the server starts.
    threading.Timer(0.8, lambda: webbrowser.open(f"http://127.0.0.1:{port}")).start()
    app.run(host=host, port=port, debug=False)
