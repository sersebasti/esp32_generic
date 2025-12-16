# comandi per aggiornare le reti wifi

# password per access point 
premere apposito pulsante per un paio di secondi
la luce blu deve andare accessa fissa
collegarsi alla rete ESP32_MACADDRESS
password = 12345678

# per accedere ad access point
password = 12345678
http://192.168.4.1/wifi/ui
su cellulare disattivare rete dati mobile se attiva

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
curl -X POST --data-binary @status_server.py "http://192.168.1.10/upload?to=/http_consts.py"

# carica una pagina nella sottocartella /www (la crea se non esiste)
curl -X POST --data-binary @osc.html "http://ESP_IP/upload?to=/www/osc.html"


# reboot
curl -X POST "http://ESP_IP/reboot"


# ESP32 File Manager REST API

Questa interfaccia HTTP espone delle API per gestire il filesystem interno dell’ESP32 con MicroPython.  
L’ESP32 espone il server sulla rete locale, esempio: **http://192.168.1.10**

---

# Endpoint disponibili

# 📂 GEstione files /fs/list  

# list
curl http://192.168.1.10/fs/list
{
  "ok": true,
  "files": [
    {"name": "boot.py", "size": 112},
    {"name": "main.py", "size": 854}
  ]
}

# upload
curl -X POST --data-binary @main.py "http://192.168.1.10/fs/upload?to=/main.py"
{
  "ok": true,
  "path": "/main.py",
  "size": 854
}

# download
curl -o tmp.txt.py "http://192.168.1.10/fs/download?path=/tmp.txt"

# delete
curl -X POST -H "Content-Type: application/json" \
     -d '{"path":"/main.py"}' \
     http://192.168.1.10/fs/delete -->
{"ok": true, "deleted": "/main.py"}

# rename
curl -X POST -H "Content-Type: application/json" \
     -d '{"src":"/main.py","dst":"/main_old.py"}' \
     http://192.168.1.10/fs/rename
{"ok": true, "renamed": ["/main.py", "/main_old.py"]}

