from wifi_connect import connect_from_json, start_ap_mode
from logger import RollingLogger
import time, network

# Se hai il portale di configurazione, lo importiamo; altrimenti gestiamo senza.
try:
    from web_ap import start_web_ap
except Exception:
    start_web_ap = None

log = RollingLogger(path="log.txt", max_bytes=8*1024, backups=1, echo=True)

def ts():
    try:
        t = time.localtime()
        return "%02d:%02d:%02d" % (t[3], t[4], t[5])
    except Exception:
        return "t+%dms" % time.ticks_ms()

def wifi_is_ok():
    sta = network.WLAN(network.STA_IF)
    return sta.active() and sta.isconnected() and sta.ifconfig()[0] not in (None, "", "0.0.0.0")

def try_reconnect():
    ok, ip = connect_from_json("wifi.json", timeout=15)
    return ok, ip

def _start_config_ap_with_fallback():
    """Accende AP di configurazione usando wifi_connect.start_ap_mode, con fallback locale.
       Ritorna l'oggetto AP o None se fallisce tutto."""
    ap = None
    # 1) prova via wifi_connect
    try:
        ap = start_ap_mode(ssid="ESP32_SETUP", password="12345678", channel=6)
    except Exception as e:
        log.error("start_ap_mode() raised: %r" % e)
        ap = None

    # 2) fallback locale se serve
    if not ap:
        try:
            # spegni STA
            try:
                sta = network.WLAN(network.STA_IF)
                sta.active(False)
            except Exception:
                pass

            ap = network.WLAN(network.AP_IF)
            ap.active(False)
            time.sleep_ms(100)
            ap.active(True)
            try:
                ap.config(essid="ESP32_1_SETUP", password="12345678",
                          authmode=network.AUTH_WPA_WPA2_PSK,
                          channel=6, hidden=0, max_clients=5)
            except Exception:
                ap.config(essid="ESP32_1_SETUP", password="12345678",
                          authmode=network.AUTH_WPA2_PSK)
            try:
                ap.ifconfig(("192.168.4.1","255.255.255.0","192.168.4.1","8.8.8.8"))
            except Exception:
                pass
        except Exception as e:
            log.error("Local AP fallback failed: %r" % e)
            ap = None

    return ap

def run_wifi_loop(check_interval=30, heartbeat=True):
    
    # NEW: flag per non avviare più volte il server /status
    status_started = False
    
    prev_ok = False
    while True:
        try:
            connected = wifi_is_ok()

            # Heartbeat
            if heartbeat:
                if connected:
                    sta = network.WLAN(network.STA_IF)
                    ip_now = sta.ifconfig()[0]
                    try:
                        rssi = sta.status('rssi')
                        print("[%s] HB connected ip=%s rssi=%sdBm" % (ts(), ip_now, rssi))
                    except Exception:
                        print("[%s] HB connected ip=%s" % (ts(), ip_now))
                else:
                    print("[%s] HB not connected" % ts())

            if connected:
                if not prev_ok:
                    sta = network.WLAN(network.STA_IF)
                    log.info("WiFi restored (ip=%s)" % sta.ifconfig()[0])
                    prev_ok = True
                    
                    # >>> NEW: avvia server /status in background una sola volta
                    if not status_started:
                        try:
                            import _thread
                            from status_server import start_status_server
                            _thread.start_new_thread(start_status_server, ())  # porta 80 o 8080
                            status_started = True
                            print("Status endpoint attivo: GET /health, GET /status")
                        except Exception as e:
                            print("Status server non avviato:", e)
                    # <<< NEW
            else:
                if prev_ok:
                    log.warn("WiFi lost; trying reconnect")
                ok, ip = try_reconnect()
                prev_ok = ok
                if ok:
                    log.info("Reconnected (ip=%s)" % ip)
                    # >>> AVVIA IL SERVER ANCHE DOPO RECONNECT (hard boot case)
                    if not status_started:
                        try:
                            import _thread
                            from status_server import start_status_server
                            _thread.start_new_thread(start_status_server, ())  # porta 80 o 8080
                            status_started = True
                            print("Status endpoint attivo: GET /health, GET /status")
                        except Exception as e:
                            print("Status server non avviato:", e)
                    # <<<
                    time.sleep_ms(200)
                    continue
                else:
                    log.error("Reconnect failed")
                    # Fallback: AP di configurazione
                    ap = _start_config_ap_with_fallback()

                if ap and ap.active():
                    try:
                        ip_ap = ap.ifconfig()[0]
                    except Exception:
                        ip_ap = "192.168.4.1"
                    print("Access Point attivo per configurazione! IP:", ip_ap)

                    if start_web_ap:
                        # Il portale ora deve TORNARE (no reboot) dopo il salvataggio
                        start_web_ap()

                        # Chiudi l'AP e prova a connetterti SUBITO
                        try:
                            ap.active(False)
                        except Exception:
                            pass

                        ok, ip = try_reconnect()
                        prev_ok = ok
                        if ok:
                            log.info("Connected post-setup (ip=%s)" % ip)

                            # Avvia /health e /status una sola volta
                            if not status_started:
                                try:
                                    import _thread
                                    from status_server import start_status_server
                                    _thread.start_new_thread(start_status_server, ())  # porta 80 o 8080
                                    status_started = True
                                    print("Status endpoint attivo: GET /health, GET /status")
                                except Exception as e:
                                    print("Status server non avviato:", e)

                            # Resta nel loop
                            continue
                        else:
                            log.warn("Post-setup connect failed; lascio AP attivo e riprovo più tardi")
                            # Se vuoi riaprire subito il portale, puoi fare start_web_ap() di nuovo.
                            # Per ora continuiamo il loop con l'AP acceso.
                            continue
                    else:
                        print("Apri http://%s per la configurazione (se web_ap non è presente, resta solo l'AP)." % ip_ap)
                        continue
                else:
                    log.error("Impossibile avviare AP di configurazione")
                    time.sleep(5)
                    continue

            # Sleep a passi da 1s (per Ctrl-C/soft reboot)
            for _ in range(int(check_interval)):
                time.sleep(1)
        except Exception as e:
            log.error("Errore nel ciclo WiFi: %r" % e)
            time.sleep(5)

# Avvio
run_wifi_loop(check_interval=30, heartbeat=True)

# (facoltativo) stampa ultime 100 righe di log quando esci dal loop
try:
    log2 = RollingLogger(path="log.txt")
    print(log2.tail(100))
except Exception:
    pass


