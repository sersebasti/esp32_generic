# ESP32 Generic

## Ambiente Linux

Individua la porta seriale della scheda:

```bash
ls /dev/ttyUSB* /dev/ttyACM*
```

Installa gli strumenti necessari:

```bash
sudo apt install -y pipx
pipx ensurepath
pipx install esptool
pipx install mpremote
```

Chiudi e riapri il terminale dopo `pipx ensurepath`, quindi verifica:

```bash
esptool version
mpremote --version
```

## Firmware MicroPython

Le istruzioni per installare il firmware sono in
[firmware/README.md](firmware/README.md):

- ESP32 Wroom classico;
- Arduino Nano ESP32.

Dopo il flash, verifica che MicroPython risponda. Per Wroom la porta e di
solito `/dev/ttyUSB0`; per Nano ESP32 e di solito `/dev/ttyACM0`.

```bash
mpremote connect /dev/ttyUSB0 exec "import sys; print(sys.version)"
```

## Installazione applicazione base

`tools/deploy_base.sh` richiede MicroPython gia installato. Elimina la
precedente applicazione e copia `main.py` con le cartelle `core`, `app`,
`wifi`, `server` e `fs`. Funziona sia su ESP32 Wroom sia su Arduino Nano ESP32.

```bash
chmod +x tools/deploy_base.sh
./tools/deploy_base.sh /dev/ttyUSB0
```

Per Arduino Nano ESP32 usa `/dev/ttyACM0` al posto di `/dev/ttyUSB0`:

```bash
./tools/deploy_base.sh /dev/ttyACM0
```

## Installazione manuale dell'applicazione

Questa procedura esegue manualmente le stesse operazioni di
`tools/deploy_base.sh`. Non installa il firmware MicroPython. Imposta prima la
porta della scheda; usa `/dev/ttyACM0` per Arduino Nano ESP32 oppure
`/dev/ttyUSB0` per ESP32 Wroom.

```bash
PORT=/dev/ttyACM0
```

Verifica che MicroPython risponda:

```bash
mpremote connect "$PORT" exec "import sys; print(sys.version)"
```

Per sostituire completamente l'applicazione base, rimuovi i file e le cartelle
precedenti. Questo elimina anche la configurazione Wi-Fi presente sulla scheda.

```bash
mpremote connect "$PORT" rm -r :main.py
mpremote connect "$PORT" rm -r :core
mpremote connect "$PORT" rm -r :app
mpremote connect "$PORT" rm -r :wifi
mpremote connect "$PORT" rm -r :server
mpremote connect "$PORT" rm -r :fs
```

Carica `main.py`:

```bash
mpremote connect "$PORT" cp main.py :main.py
```

Carica una cartella alla volta. `cp -r` crea automaticamente la cartella sulla
scheda.

```bash
mpremote connect "$PORT" cp -r core :
mpremote connect "$PORT" cp -r app :
mpremote connect "$PORT" cp -r wifi :
mpremote connect "$PORT" cp -r server :
mpremote connect "$PORT" cp -r fs :
```

Riavvia la scheda dopo la copia:

```bash
mpremote connect "$PORT" exec "import machine; machine.reset()"
```

## Note

- L'ESP32 espone il server sulla rete locale, ad esempio `http://<DEVICE_IP>`.