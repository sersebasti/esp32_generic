# Power Sensors API (ESP32)

Questa API permette di leggere i dati da uno o più sensori di potenza (PZEM-004T) collegati all’ESP32 tramite UART, configurabili via file JSON.

## Configurazione

1. **File di configurazione:**
   - Percorso: `power_sensors/power_sensors.json`
   - Esempio:
     ```json
     [
       {"id": "pz1", "uart_id": 1, "tx": 17, "rx": 16, "baudrate": 9600},
       {"id": "pz2", "uart_id": 2, "tx": 25, "rx": 26, "baudrate": 9600}
     ]
     ```

2. **Endpoint HTTP:**
   - Richiesta singolo sensore:
     ```
     GET /power_sensor?id=pz1
     ```
     Risposta:
     ```json
     {"ok": true, "data": {"voltage": ..., "current": ..., ...}}
     ```

3. **Più sensori sulla stessa UART:**
   Assegna la stessa UART, gli stessi pin e baudrate, ma uno `slave_addr` univoco a ogni sensore:
   ```json
   [
     {"id": "pz1", "uart_id": 1, "tx": 17, "rx": 16, "baudrate": 9600, "slave_addr": 1},
     {"id": "pz2", "uart_id": 1, "tx": 17, "rx": 16, "baudrate": 9600, "slave_addr": 2}
   ]
   ```
   Gli indirizzi validi per il bus condiviso sono 1-247. Il valore predefinito `0xF8` è mantenuto per configurazioni con un solo sensore su ciascuna UART.

  Assegna gli indirizzi prima di collegare insieme i sensori: collega un solo sensore alla UART mentre è ancora all'indirizzo `0xF8`, poi da REPL esegui:
  ```python
  from power_sensors.pzem004t import PZEM004T
  sensor = PZEM004T(uart_id=1, tx=17, rx=16, baudrate=9600)
  sensor.set_slave_addr(1)
  ```
  Ripeti con gli altri sensori, usando ogni volta un indirizzo diverso, quindi aggiorna la configurazione JSON. Non collegare insieme sensori ancora tutti impostati a `0xF8` durante l'assegnazione.

   La condivisione elettrica deve corrispondere all'interfaccia del modulo e alla scheda adattatrice usata. Se l'uscita è TTL e non è progettata per una linea multi-drop, usa un adattatore/multiplexer adatto invece di collegare direttamente più uscite TX.

## Integrazione

- Il server HTTP deve importare e chiamare `power_sensors_api.handle_power_sensor` nel ciclo di dispatch, dopo gli altri endpoint.
- Il percorso del file JSON deve essere esattamente `power_sensors/power_sensors.json`.

## Note
- Funziona in parallelo agli endpoint di scope/adc_api.py, senza modificare la logica esistente.
- Puoi aggiungere nuovi sensori modificando il file JSON e riavviando il server.

---

Per domande o problemi, consulta il codice o chiedi supporto!
