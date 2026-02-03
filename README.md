## Endpoint ESP32: Misura e Calibrazione

Tutti gli endpoint accettano il parametro sensor_id (es. c1, c2) e supportano fast=1.

### Misura
- **GET /adc/scope_counts**
  - Parametri: sensor_id, n, sr, fast
  - Esempio: `/adc/scope_counts?sensor_id=c1&n=1024&sr=4000&fast=1`

- **GET /amps**
  - Parametri: sensor_id, n, sr, fast
  - Esempio: `/amps?sensor_id=c1&n=1024&sr=4000&fast=1`

### Calibrazione
- **GET /calibrate**
  - Parametri: sensor_id, fast
  - Esempio: `/calibrate?sensor_id=c1&fast=1`

- **GET /calibrate?amp=0** (misura baseline)
  - Parametri: sensor_id, fast
  - Esempio: `/calibrate?amp=0&sensor_id=c1&fast=1`

- **GET /calibrate?amp=...** (aggiungi punto)
  - Parametri: sensor_id, amp, n, sr, fast
  - Esempio: `/calibrate?amp=5.0&sensor_id=c1&n=1600&sr=4000&fast=1`

- **POST /calibrate/delete**
  - Body JSON: `{ "sensor_id": "c1", "index": 0 }`
  - Elimina il punto di calibrazione all’indice indicato

- **POST /calibrate/reset**
  - Parametri: sensor_id, fast
  - Esempio: `/calibrate/reset?sensor_id=c1&fast=1`
  - Cancella tutti i punti e la baseline del sensore

### Baseline
- **GET /compare_baseline**
  - Parametri: sensor_id, n, sr, fast
  - Esempio: `/compare_baseline?sensor_id=c1&n=1600&sr=4000&fast=1`

---
## Modalità campionamento veloce (fast=1)

Tutti gli endpoint di misura e calibrazione supportano il parametro opzionale `fast=1`:

- Se aggiungi `&fast=1` alla richiesta, il campionamento avviene alla massima velocità possibile (senza ritardo tra i campioni).
- Utile per test di velocità o quando non serve un sample rate preciso.

### Esempi di richieste (sostituisci `<IP_ESP32>` con l'indirizzo del tuo dispositivo):

```
http://<IP_ESP32>/adc/scope_counts?sensor_id=c1&n=1024&sr=4000
http://<IP_ESP32>/adc/scope_counts?sensor_id=c1&n=1024&sr=4000&fast=1
http://<IP_ESP32>/amps?sensor_id=c1&n=1024&sr=4000
http://<IP_ESP32>/amps?sensor_id=c1&n=1024&sr=4000&fast=1
http://<IP_ESP32>/calibrate?sensor_id=c1
http://<IP_ESP32>/calibrate?amp=0&sensor_id=c1
http://<IP_ESP32>/calibrate?amp=0&sensor_id=c1&fast=1
http://<IP_ESP32>/calibrate?amp=5.0&sensor_id=c1
http://<IP_ESP32>/calibrate?amp=5.0&sensor_id=c1&fast=1
http://<IP_ESP32>/compare_baseline?sensor_id=c1
http://<IP_ESP32>/compare_baseline?sensor_id=c1&fast=1
```

Se ometti `fast=1`, il sample rate sarà regolato dal parametro `sr` (più lento ma temporizzato).

**Nota:** con `fast=1` il tempo di risposta è molto più breve, ma i campioni non sono equispaziati nel tempo.

## Firmware Installation (Windows)

1) Collega l'ESP32 via USB.


2) Trova la porta seriale (COM):
```powershell
Get-WmiObject Win32_SerialPort | Select-Object DeviceID,Description
```
**Procedura consigliata:**
- Scollega l'ESP32 dal PC e lancia il comando qui sopra.
- Ricollega l'ESP32 e rilancia il comando.
- La porta che appare (o scompare quando scolleghi) è quella giusta per l'ESP32.
- Se non compare nessuna nuova porta, prova a cambiare cavo USB o porta USB del PC.
- Se vedi solo porte "Intel(R) Active Management Technology" o simili, l'ESP32 non è rilevato: verifica i driver o il cavo.

3) (Opzionale) Installa Python e ampy/mpremote:
Scarica Python da https://www.python.org/downloads/ e assicurati che sia nel PATH.
Poi:
```powershell
pip install adafruit-ampy mpremote
```

4) Connettiti alla REPL MicroPython:
```powershell
mpremote connect COMx repl
```
Sostituisci COMx con la porta trovata (es: COM3).

5) Carica file o esegui comandi:
```powershell
ampy --port COMx put main.py
mpremote connect COMx cp main.py :main.py
 
# Per cancellare TUTTI i file dal dispositivo (attenzione, elimina tutto!):
mpremote connect COMx rm -rv :
```

---

## Aggiornamento completo del software (wipe & reinstall)

1. **Cancella tutti i file dal dispositivo** (ATTENZIONE: elimina tutto!)
  ```powershell
  mpremote connect COMx rm -rv :
  ```
2. **Carica i file principali nella root**:
  ```powershell
  mpremote connect COMx cp boot.py :boot.py
  mpremote connect COMx cp main.py :main.py
  ```
3. **Crea le cartelle necessarie** (core, fs, scope):
  ```powershell
  mpremote connect COMx mkdir :core
  mpremote connect COMx mkdir :fs
  mpremote connect COMx mkdir :scope
  ```
4. **Copia tutti i file nelle rispettive cartelle**:
  ```powershell

 mpremote connect COMx cp -r core :
  mpremote connect COMx cp -r fs :
  mpremote connect COMx cp -r scope :
  ```
  Se ricevi errori di permesso, assicurati che le cartelle siano state create prima e ripeti il comando.

5. **Riavvia il dispositivo** (opzionale ma consigliato):
  ```powershell
  mpremote connect COMx exec "import machine; machine.reset()"
  ```

**Nota:**
- Dopo il wipe, è fondamentale caricare subito almeno boot.py e main.py nella root, altrimenti il dispositivo potrebbe non avviarsi correttamente.
- Se usi moduli opzionali (scope, fs), ricordati di copiare anche queste cartelle e i relativi file.

6) Puoi anche usare programmi come PuTTY/Tera Term per la console seriale (baud 115200).

---

## Firmware Installation (Linux)

1) Connect the ESP32 via USB.

2) Find the serial port:
```bash
ls /dev/ttyUSB* /dev/ttyACM*
```

3) Install esptool (via pipx is recommended):
```bash
sudo apt install -y pipx
pipx ensurepath
pipx install esptool
esptool version
```

4) (Optional) Erase existing firmware:
```bash
esptool --port /dev/ttyUSB0 erase-flash
```

If needed, enter bootloader mode: hold BOOT, press and release RST/EN, then release BOOT.

5) Flash the firmware (replace the .bin filename with yours):
```bash
esptool --chip esp32 --port /dev/ttyUSB0 write-flash -z 0x1000 ESP32_GENERIC-20250911-v1.26.1.bin
```

6) Install mpremote and verify:
```bash
pipx install mpremote
mpremote --help
```

7) Inspect files and (optional) wipe the filesystem:
```bash
mpremote connect /dev/ttyUSB0 ls
mpremote connect /dev/ttyUSB0 rm -rv :
```

8) Upload project files to the device (skip binaries, text, git):
```bash
find . -type f \
  ! -name "*.bin" \
  ! -name "*.txt" \
  ! -path "./.git/*" \
  -exec mpremote connect /dev/ttyUSB0 cp {} :{} \;
```

Required uploads:
- Root files: `main.py`, `boot.py` (located in repository root)
- Full `core/` folder with all its contents (APIs, server, UI, helpers)

Optional modules (upload the folder and enable related features in `core/config.py`):
- `scope/` → set `features.scope = True`
- `fs/` → set `features.fs_api = True`

Key core files (normally included when you copy the entire `core/` folder):
- core/wifi_api.py, core/wifi_store.py, core/wifi_ui.html, core/server.py, core/status_api.py, core/system_api.py, core/http_consts.py, core/busy_lock.py, core/wifi_led_status.py

9) Open the REPL console (for logs/diagnostics):
```bash
mpremote connect /dev/ttyUSB0 repl
```

10) Start FTP manually (optional):
```bash
mpremote connect /dev/ttyUSB0 exec "import core.uftpd as uftpd; uftpd.restart(port=21, verbose=0)"
```

---

## Configuration

Configuration lives in `core/config.py` as in-code defaults. To adjust, edit the default dictionary in that file.

- Main parameters:
  - WIFI_JSON: path to the Wi‑Fi networks file (default: core/wifi.json)
  - LOG_PATH: log file path (default: log.txt)
  - LOG_MAX_BYTES: max log size (default: 8192)
  - BTN_PIN: user button pin (default: 32)
  - FTP_AUTOSTART: start FTP automatically (default: False)
  - FTP_PORT: FTP port (default: 21)
  - FTP_USER / FTP_PASS: FTP credentials (default: admin/admin)

Note: some UIs may read the device name/hostname from core/wifi.json.

---

## Access Point mode (Wi‑Fi setup)

- Hold the button ~2 seconds: blue LED solid = AP is active.
- Connect to SSID `ESP32_<MAC>`, password `12345678`.
- Open http://192.168.4.1/wifi/ui to configure networks.
- Tip: on smartphones, temporarily disable mobile data.

Useful curl commands (replace <DEVICE_IP>):
```bash
# List configured networks
curl http://<DEVICE_IP>/wifi/list

# Add network (append)
curl -X POST http://<DEVICE_IP>/wifi/add \
  -H "Content-Type: application/json" \
  -d '{"ssid":"MySSID","password":"secret"}'

# Add to top (priority=1)
curl -X POST http://<DEVICE_IP>/wifi/add \
  -H "Content-Type: application/json" \
  -d '{"ssid":"TopNet","password":"pwd","priority":1}'

# Delete network
curl -X POST http://<DEVICE_IP>/wifi/delete \
  -H "Content-Type: application/json" \
  -d '{"ssid":"MySSID"}'
```

---

## Endpoints

- Status
  - GET /health: simple probe `{ok:true}`
  - GET /status: detailed status (version, ip, ssid, rssi, mac, uptime, heap)

- Wi‑Fi
  - GET /wifi/ui: static UI (serves core/wifi_ui.html if present)
  - GET /wifi/scan: available networks
  - GET /wifi/list: configured networks (no passwords)
  - POST /wifi/add: add network `{ssid, password, priority?}`
  - POST /wifi/delete: remove network `{ssid}`

- File system (REST)
  - GET /fs/list[?dir=/subdir]
  - GET /fs/download?path=/file
  - POST /fs/upload?to=/dest
  - POST /fs/delete body `{path}`
  - POST /fs/rename body `{src,dst}`

- System
  - POST /reboot: reboot device

- Scope/ADC (if module present)
  - GET /adc/scope_counts[?sensor_id=c1&n=1600&sr=4000]: acquisizione raw dal sensore specificato
  - GET /calibrate[?sensor_id=c1]: mostra stato calibrazione per il sensore
  - GET /calibrate?amp=<A>&sensor_id=c1: aggiungi baseline (A=0) o punto di calibrazione per il sensore
  - GET /amps[?sensor_id=c1&n=1600&sr=4000]: misura la corrente RMS dal sensore
  - GET /compare_baseline[?sensor_id=c1&n=1600&sr=4000]: confronta la baseline salvata con la media attuale dei counts per il sensore
  - POST /calibrate/delete: remove a point `{index}` or `{amps,rms_counts}`
  - POST /calibrate/reset: reset calibration

---

## Notes

- The ESP32 serves on the LAN, e.g., http://<DEVICE_IP>
- /fs/* APIs enable CORS for use from external tools (browsers).
- The Wi‑Fi UI is a static file at `core/wifi_ui.html`.