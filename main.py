from core.logger import CircularLogger
from core.wifi_manager import WiFiManager
from core.config import LOG_PATH, LOG_MAX_BYTES, WIFI_JSON

log = CircularLogger(path=LOG_PATH, max_bytes=LOG_MAX_BYTES, echo=True)





if __name__ == "__main__":
    # Per testare il sensore di potenza PZEM-004T
    import power_sensor.test_pzem004t
    # from machine import UART
    # import time

    # uart = UART(1, 9600, tx=17, rx=16)

    # while True:
    #     uart.write("ciao\n")
    #     time.sleep(0.2)

    #     if uart.any():
    #         data = uart.read()
    #         print("Ricevuto:", data)

    #     time.sleep(1)
    
    # Se vuoi ripristinare la logica originale, commenta la riga sopra e decommenta sotto:
    # mgr = WiFiManager(log=log, wifi_json=WIFI_JSON)
    # mgr.run()