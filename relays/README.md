# Relay API (ESP32/MicroPython)

## Descrizione

Questa API permette di gestire uno o più relay collegati a ESP32 tramite HTTP REST, con configurazione dinamica e supporto multi-relay.

## Configurazione

Il file `relays.json` deve avere questa struttura:

```json
{
  "relays": [
    {
      "id": "relay1",
      "pin": 13,
      "active_low": true,
      "initial_state": "off"
    }
    // ... altri relay ...
  ]
}
```

## Lazy Load

I relay vengono istanziati solo al primo utilizzo (lazy load), ottimizzando memoria e prestazioni.

## Endpoint disponibili

### Stato relay
- **Tutti i relay:**
  ```bash
  curl "http://<IP>/relay"
  ```
- **Singolo relay:**
  ```bash
  curl "http://<IP>/relay?id=relay1"
  # oppure
  curl "http://<IP>/relay/status?id=relay1"
  ```

### Accensione/spegnimento/toggle
- **Accendi:**
  ```bash
  curl -X POST "http://<IP>/relay/on?id=relay1"
  ```
- **Spegni:**
  ```bash
  curl -X POST "http://<IP>/relay/off?id=relay1"
  ```
- **Toggle:**
  ```bash
  curl -X POST "http://<IP>/relay/toggle?id=relay1"
  ```

### Imposta stato direttamente
- **Via body JSON:**
  ```bash
  curl -X POST -H "Content-Type: application/json" -d '{"id":"relay1", "on": true}' http://<IP>/relay/set
  curl -X POST -H "Content-Type: application/json" -d '{"id":"relay1", "on": false}' http://<IP>/relay/set
  ```

## Note
- Se non specifichi `id`, lo stato di tutti i relay viene restituito (solo per GET).
- Tutti i parametri possono essere passati sia in query string che nel body JSON.
- Gli endpoint sono robusti e restituiscono errori chiari in caso di id non valido.

## Esempio risposta
```json
{"id": "relay1", "is_on": false, "pin": 13}
```
