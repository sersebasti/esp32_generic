from core.logger import CircularLogger
from core.wifi_manager import WiFiManager
from core.config import LOG_PATH, LOG_MAX_BYTES, WIFI_JSON

log = CircularLogger(path=LOG_PATH, max_bytes=LOG_MAX_BYTES, echo=True)





if __name__ == "__main__":
    # Per testare il sensore di potenza PZEM-004T
    # import power_sensor.test_pzem004t

    
    #Se vuoi ripristinare la logica originale, commenta la riga sopra e decommenta sotto:
    mgr = WiFiManager(log=log, wifi_json=WIFI_JSON)
    mgr.run()