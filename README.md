## installazione ambiente

# trova porta seriale linux:
ls /dev/ttyUSB* /dev/ttyACM*


# installa esptool linux
sudo apt install -y pipx
pipx ensurepath
pipx install esptool
esptool version

## installazione firmware linux

# cancellazione firmware
esptool --port /dev/ttyUSB0 erase-flash


# installazione firmware
esptool --chip esp32 --port /dev/ttyUSB0 write-flash -z 0x1000 ESP32_GENERIC-20250911-v1.26.1.bin


## installazione software

# verifica
mpremote connect /dev/ttyUSB0 ls

# verifica windows
mpremote connect COM4 ls

# cancella tutto
mpremote connect XXX rm -r :

# carica singoli files base
mpremote connect XXXX cp boot.py :boot.py
mpremote connect XXXX cp main.py :main.py

# crea cartelle base
mpremote connect XXXX mkdir :core
mpremote connect XXXX mkdir :wifi
mpremote connect XXXX mkdir :server
mpremote connect XXXX mkdir :app


# crea eventuali ulteriori cartelle sulla base della configurazione
mpremote connect XXXX mkdir :fs
mpremote connect XXXX mkdir :display
# ecc...

# copia i files nelle rispettive cartelle**:
mpremote connect XXXX cp -r core :

# oppure cancella tutti i file sul dispositivo e distribuisci la configurazione base:
# boot.py, main.py, core, app, wifi, server e fs
./tools/deploy_base.sh /dev/ttyUSB0


## Notes

- The ESP32 serves on the LAN, e.g., http://<DEVICE_IP>
- /fs/* APIs enable CORS for use from external tools (browsers).
- The Wi‑Fi UI is a static file at `core/wifi_ui.html`.


## comado powershell per vedere ip
- arp -a