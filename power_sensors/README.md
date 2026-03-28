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

## Integrazione

- Il server HTTP deve importare e chiamare `power_sensors_api.handle_power_sensor` nel ciclo di dispatch, dopo gli altri endpoint.
- Il percorso del file JSON deve essere esattamente `power_sensors/power_sensors.json`.

## Note
- Funziona in parallelo agli endpoint di scope/adc_api.py, senza modificare la logica esistente.
- Puoi aggiungere nuovi sensori modificando il file JSON e riavviando il server.

---

Per domande o problemi, consulta il codice o chiedi supporto!
