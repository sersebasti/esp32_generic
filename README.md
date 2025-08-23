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
