#!/usr/bin/env bash

set -euo pipefail

PORT="${1:-/dev/ttyACM0}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BASE_DIRS=(core app wifi server fs)

command -v mpremote >/dev/null || {
    echo "Errore: mpremote non e installato o non e nel PATH." >&2
    exit 1
}

[[ -e "$PORT" ]] || {
    echo "Errore: porta seriale non trovata: $PORT" >&2
    exit 1
}

[[ -f "$ROOT_DIR/main.py" ]] || {
    echo "Errore: file richiesto mancante: main.py" >&2
    exit 1
}

for dir in "${BASE_DIRS[@]}"; do
    [[ -d "$ROOT_DIR/$dir" ]] || {
        echo "Errore: cartella richiesta mancante: $dir" >&2
        exit 1
    }
done

echo "Verifico MicroPython su $PORT..."
mpremote connect "$PORT" exec "import sys; print(sys.version)"

cd "$ROOT_DIR"

echo "Rimuovo la precedente applicazione..."
for path in main.py "${BASE_DIRS[@]}"; do
    mpremote connect "$PORT" rm -r ":$path" 2>/dev/null || true
done

echo "Copio main.py..."
mpremote connect "$PORT" cp main.py :main.py

for dir in "${BASE_DIRS[@]}"; do
    echo "Copio $dir/..."
    mpremote connect "$PORT" cp -r "$dir" :
done

echo "Riavvio ESP32..."
mpremote connect "$PORT" exec "import machine; machine.reset()" || true

echo "Distribuzione software completata."