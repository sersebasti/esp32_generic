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

Note: some UIs may read the device name/hostname from `wifi.json`.

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
  - GET /adc/scope_counts[?n=1600&sr=4000]
  - GET /calibrate: show calibration state
  - GET /calibrate?amp=<A>: add baseline (A=0) or a calibration point
  - GET /amps[?n=1600&sr=4000]: measure RMS current using the model
  - POST /calibrate/delete: remove a point `{index}` or `{amps,rms_counts}`
  - POST /calibrate/reset: reset calibration

---

## Notes

- The ESP32 serves on the LAN, e.g., http://<DEVICE_IP>
- /fs/* APIs enable CORS for use from external tools (browsers).
- The Wi‑Fi UI is a static file at `core/wifi_ui.html`.