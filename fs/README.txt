# Modulo fs - Endpoint API

Questo modulo espone endpoint HTTP per la gestione remota del filesystem su ESP32/MicroPython.

## Elenco endpoint

### 1. Lista file/cartelle
- **GET /fs/list?path=/cartella**
- Restituisce la lista di file e cartelle nella directory specificata (`/` per la root).
- **Esempio:**
  - `GET /fs/list?path=/`
- **Risposta:** JSON con elenco di file, dimensione e tipo (file/dir).

### 2. Download file
- **GET /fs/download?path=/file.txt**
- Scarica il file specificato come octet-stream.
- **Risposta:** file binario (octet-stream)

### 3. Upload file
- **POST /fs/upload?to=/dest.txt`**
- Carica un file nella destinazione specificata.
- **Body:** dati binari del file
- **Risposta:** JSON con esito e dimensione file scritto.

### 4. Eliminazione file
- **POST /fs/delete**
- Elimina il file specificato.
- **Body JSON:** `{ "path": "/file.txt" }`
- **Risposta:** JSON con esito e nome file eliminato.

### 5. Rinomina file
- **POST /fs/rename**
- Rinomina/sposta un file.
- **Body JSON:** `{ "src": "/file1.txt", "dst": "/file2.txt" }`
- **Risposta:** JSON con esito e nomi coinvolti.

**Nota:** Tutti gli endpoint rispondono con CORS abilitato e JSON per errori/risposte, tranne il download che restituisce direttamente il file richiesto.
