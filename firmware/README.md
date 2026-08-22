# Firmware MicroPython

Installa il firmware corrispondente alla tua scheda prima di eseguire
`tools/deploy_base.sh`. Il deploy dell'applicazione e comune a entrambe le
schede ed e documentato nel [README principale](../README.md).

## ESP32 Wroom classico

Firmware: `ESP32_GENERIC-20250911-v1.26.1.bin`.

La scheda usa normalmente la porta `/dev/ttyUSB0`.

```bash
esptool --port /dev/ttyUSB0 erase-flash
esptool --chip esp32 --port /dev/ttyUSB0 write-flash -z 0x1000 ESP32_GENERIC-20250911-v1.26.1.bin
```

Verifica l'avvio di MicroPython:

```bash
mpremote connect /dev/ttyUSB0 exec "import sys; print(sys.version)"
```

## Arduino Nano ESP32

Firmware: `ARDUINO_NANO_ESP32-20260406-v1.28.0.bin`.

La Nano ESP32 usa normalmente la porta `/dev/ttyACM0`. Per entrare nel
bootloader, collega temporaneamente `GPIO0` (`D0`/`BOOT1`) a `GND`, premi e
rilascia `RST`, poi rimuovi il collegamento a `GND`.

```bash
esptool --chip esp32s3 --port /dev/ttyACM0 --before no-reset --after no-reset erase-flash
esptool --chip esp32s3 --port /dev/ttyACM0 --before no-reset --after no-reset write-flash -z 0x1000 ARDUINO_NANO_ESP32-20260406-v1.28.0.bin
```

Premi `RST`, poi verifica l'avvio di MicroPython:

```bash
mpremote connect /dev/ttyACM0 exec "import sys; print(sys.version)"
```

Sostituisci la porta nei comandi se la tua scheda appare con un nome diverso.