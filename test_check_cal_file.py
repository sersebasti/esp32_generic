import os

# Verifica se il file di calibrazione esiste (MicroPython)
cal_file = 'scope/calibrate_34.json'  # Usa il pin ADC corretto per c1
try:
    os.stat(cal_file)
    print("Il file {} ESISTE ancora.".format(cal_file))
except OSError:
    print("Il file {} NON esiste (cancellato correttamente).".format(cal_file))
