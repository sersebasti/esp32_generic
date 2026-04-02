# Scope - guida rapida endpoints modulo scope

## Endpoint sensori

### `/sensors`
- **Metodo:** GET
- **Descrizione:** Restituisce la lista dei sensori disponibili, con informazioni su tipo, id, stato e calibrazione.
- **Esempio:**
        - `GET http://192.168.1.100/sensors`


Per leggere la configurazione/calibrazione di un sensore di corrente (es. c1):

- `GET http://192.168.1.100/calibrate?sensor_id=c1`

Risposta: JSON con baseline, k, punti di calibrazione, ecc.

## Aggiungere un punto di calibrazione corrente

Per aggiungere un punto di calibrazione (o aggiornare la baseline se amp=0):

- `POST http://192.168.1.100/calibrate` con body JSON:

        {
            "sensor_id": "c1",
            "amp": 8,
            "n": 1024,
            "sr": 4000,
            "fast": 1,
            "phase_shift": 2
        }

Se amp è 0, il software aggiornerà la baseline (corrente nulla).


## Aggiungere un punto di calibrazione tensione

Per aggiungere un punto di calibrazione (o aggiornare la baseline se volt=0):

- `POST http://192.168.1.100/calibrate` con body JSON:

                {
                        "sensor_id": "v1",
                        "volt": 230,
                        "n": 1024,
                        "sr": 4000,
                        "fast": 1,
                        "phase_shift": 2
                }

Se volt è 0, il software aggiornerà la baseline (tensione nulla).


## Eliminare un punto di calibrazione per indice

Per eliminare un punto di calibrazione dal file di calibrazione di un sensore di corrente, specificando l’indice del punto:

- `POST http://192.168.1.100/calibrate/delete` con body JSON:

        {
            "sensor_id": "c1",
            "index": 0
        }

Questo rimuove il primo punto (gli indici partono da 0).



## Acquisizione campioni ADC raw

Per acquisire un blocco di campioni raw dall’ADC di un sensore:

- `GET http://192.168.1.100/adc/scope_counts?sensor_id=c1&n=1024&fast=1&binary=true`

**Parametri:**
        - `sensor_id`: id del sensore (es. c1 per corrente, v1 per tensione)
        - `n`: numero di campioni da acquisire (es. 1024)
        - `fast`: 1 per acquisizione rapida, 0 per acquisizione lenta
        - `binary`: true per risposta binaria (default: false, restituisce JSON)

Se `binary=true`, la risposta è un blocco binario (octet-stream) con i valori ADC.

## Nota su fast e frequenza di campionamento

- Se `fast=1` (True), l'acquisizione avviene alla massima velocità possibile: il parametro `sr` (sample_rate_hz) viene ignorato e i campioni sono raccolti senza attese tra una lettura e l'altra. Il sample rate effettivo dipende solo dalla velocità dell'ESP32 e del codice Python.
- Se `fast=0` (False), il sistema cerca di rispettare il sample rate richiesto (`sr`) inserendo un delay tra i campioni. Tuttavia, per valori alti di `sr` (es. >2-3 kHz), il tempo di esecuzione del ciclo e della lettura ADC può rendere il sample rate effettivo più basso di quello richiesto.
- In generale, usa `fast=1` per acquisire il massimo numero di campioni nel minor tempo possibile (profilo rapido), e `fast=0` quando vuoi una frequenza di campionamento regolare e non troppo elevata.
- Se vuoi conoscere il sample rate effettivo, misura il tempo totale di acquisizione e calcola `n / tempo_totale`.

## Misura di potenza istantanea

Per misurare la potenza attiva, apparente e il fattore di potenza tra due sensori (tensione e corrente):

- `GET http://<ip_esp32>/power?voltage_sensor_id=v1&current_sensor_id=c1&n=1600&sr=4000&fast=1&phase_shift=0`

**Parametri:**
- `voltage_sensor_id`: id del sensore di tensione (es. v1)
- `current_sensor_id`: id del sensore di corrente (es. c1)
- `n`: numero di campioni da acquisire (es. 1600)
- `sr`: frequenza di campionamento richiesta (Hz)
- `fast`: 1 per acquisizione rapida, 0 per acquisizione temporizzata
- `phase_shift`: correzione di fase (in campioni, opzionale)

**Risposta:** JSON con i seguenti campi principali:
- `volts_rms`: valore efficace della tensione
- `amps_rms`: valore efficace della corrente
- `power_w`: potenza attiva (Watt)
- `apparent_power_va`: potenza apparente (VA)
- `power_factor`: fattore di potenza
- `phase_shift_samples`: shift di fase applicato (in campioni)
- `voltage` e `current`: info diagnostiche su baseline, min, max, clipping

**Esempio di risposta:**
```json
{
  "ok": true,
  "mode": "instantaneous_pair",
  "voltage_sensor_id": "v1",
  "current_sensor_id": "c1",
  "n": 1600,
  "sample_rate_hz": 4000,
  "fast": true,
  "volts_rms": 228.5,
  "amps_rms": 0.512,
  "power_w": 98.2,
  "apparent_power_va": 117.0,
  "power_factor": 0.84,
  "phase_shift_samples": 0,
  "clipping": false,
  "voltage": { "baseline_mean": 2047.2, "min": 52, "max": 4040, "clipping": false },
  "current": { "baseline_mean": 2048.1, "min": 60, "max": 4030, "clipping": false }
}
```

**Nota:**
- Per misure accurate, assicurati che i sensori siano calibrati e che il sample rate sia sufficiente a rappresentare la forma d’onda (almeno 20x la frequenza di rete).
- Il parametro `phase_shift` permette di compensare eventuali sfasamenti tra tensione e corrente dovuti a filtri o cablaggi.