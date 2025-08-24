# comandi per aggiornare le reti wifi

# lista reti configurate
curl http://<IP-ESP>/wifi/list

# aggiungi (append)
curl -X POST http://<IP-ESP>/wifi/add \
  -H "Content-Type: application/json" \
  -d '{"ssid":"NuovaRete","password":"segretissima"}'

# aggiungi in testa (priority=1)
curl -X POST http://<IP-ESP>/wifi/add \
  -H "Content-Type: application/json" \
  -d '{"ssid":"RetePrioritaria","password":"pwd","priority":1}'

# cancella
curl -X POST http://<IP-ESP>/wifi/delete \
  -H "Content-Type: application/json" \
  -d '{"ssid":"NuovaRete"}'
'''

# calibrazione
# 1) Baseline a 0 A
curl "http://ESP_IP/calibrate?amp=0"

# 2) Aggiungi punti con correnti note (ripeti con 2–3 valori, es. 0.5 A, 1.2 A, 3 A…)
curl "http://ESP_IP/calibrate?amp=1.20"
curl "http://ESP_IP/calibrate?amp=3.00"

# 3) Vedi stato/modello
curl "http://ESP_IP/calibrate"

# 4) Lettura in Ampere (usa il modello lineare stimato)
curl "http://ESP_IP/amps?n=1600&sr=4000"

# 5) reset calibrate - elimina tutti i dati di calibrazione
curl -X POST "http://192.168.1.24/calibrate/reset"




# carica un file nella root del device
curl -X POST --data-binary @status_server.py "http://ESP_IP/upload?to=/status_server.py"

# carica una pagina nella sottocartella /www (la crea se non esiste)
curl -X POST --data-binary @osc.html "http://ESP_IP/upload?to=/www/osc.html"

# carica main.py e poi riavvia manualmente (pulsante EN o power-cycle)
curl -X POST --data-binary @main.py "http://ESP_IP/upload?to=/main.py"



curl -X POST "http://ESP_IP/reboot"