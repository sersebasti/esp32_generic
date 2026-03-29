# WebREPL (MicroPython)

Questa directory contiene la gestione della feature WebREPL per ESP32.

## Funzionalità
- Avvio automatico di WebREPL solo se abilitato tramite configurazione centrale (`core/config.py`, flag `"webrepl"`).
- Endpoint HTTP per controllo remoto:
  - `GET  /webrepl/status` — Stato e abilitazione
  - `POST /webrepl/start`  — Avvia WebREPL
  - `POST /webrepl/stop`   — Ferma WebREPL (se supportato)

## Come abilitare WebREPL
1. Imposta `"webrepl": true` in `core/config.py` nella sezione `features`.
2. All'avvio, WebREPL verrà attivato automaticamente.
3. Puoi controllare lo stato o avviare/fermare WebREPL anche via HTTP.

## Note
- WebREPL è incluso nel firmware MicroPython ufficiale per ESP32.
- Per sicurezza, imposta una password tramite `import webrepl_setup` da REPL seriale.
- Per accedere via browser: https://micropython.org/webrepl/

## Esempio di richiesta HTTP
```
GET  http://<esp32-ip>/webrepl/status
POST http://<esp32-ip>/webrepl/start
POST http://<esp32-ip>/webrepl/stop
```

Risposta tipica:
```json
{"ok": true, "enabled": true, "running": true}
```
