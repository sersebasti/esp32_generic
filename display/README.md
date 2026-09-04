# Display LCD1602 (ESP32)

Questo modulo gestisce un display LCD1602 con backpack I2C (tipicamente PCF8574) su ESP32 con MicroPython.

## File del modulo

- `display/lcd1602.py`: driver base LCD1602
- `display/display_manager.py`: factory e caricamento configurazione
- `display/display.json`: configurazione pin I2C e indirizzo del display

## Configurazione

Il file di configurazione e`:

```json
{
  "i2c_id": 0,
  "scl": 22,
  "sda": 21,
  "addr": 39
}
```

Note:
- `addr: 39` corrisponde a `0x27`
- se il tuo backpack usa un altro indirizzo, ad esempio `0x3F`, imposta `addr` a `63`

## Collegamenti ESP32

- `VCC` display -> `5V` oppure `3.3V` in base al modulo
- `GND` display -> `GND`
- `SCL` display -> `GPIO 22`
- `SDA` display -> `GPIO 21`

## Uso nel progetto

Attualmente il display viene inizializzato in `core/status_api.py` tramite:

```python
from display import create_lcd

lcd = create_lcd()
```

Questo approccio evita di lasciare i pin hardcoded dentro `status_api.py`.

## Uso da altri moduli

Se vuoi usare il display in un altro punto del codice, puoi fare cosi`:

```python
from display import create_lcd

lcd = create_lcd()
lcd.clear()
lcd.write(0, 0, "Hello")
lcd.write(1, 0, "ESP32")
```

Oppure, se ti serve solo leggere la configurazione:

```python
from display import load_display_config

cfg = load_display_config()
print(cfg)
```

## Deploy su ESP32

Per copiare il modulo sul device:

```bash
mpremote connect /dev/ttyUSB0 cp -r display/ :
```

Se hai modificato anche il codice che lo usa, ricopia anche `core/` e riavvia:

```bash
mpremote connect /dev/ttyUSB0 cp -r core/ :
mpremote connect /dev/ttyUSB0 exec "import machine; machine.reset()"
```

## Note pratiche

- il display viene creato solo se la feature `lcd_display` e` abilitata in `core/config.py`
- se non funziona, controlla prima indirizzo I2C, cablaggio e alimentazione
- se il modulo si accende ma non mostra testo, il problema spesso e` l'indirizzo `0x27` vs `0x3F`