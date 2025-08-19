import network, time
from wifi_connect import connect_from_json
from logger import RollingLogger

log = RollingLogger(path="log.txt", max_bytes=8*1024, backups=1, echo=True)

def ts():
    try:
        y,mo,d,hh,mm,ss,_,_ = time.localtime()
        if y >= 2020:
            return "%02d:%02d:%02d" % (hh, mm, ss)
    except:
        pass
    return "t+%dms" % time.ticks_ms()

def wifi_is_ok():
    sta = network.WLAN(network.STA_IF)
    return sta.active() and sta.isconnected() and sta.ifconfig()[0] not in (None, "", "0.0.0.0")

def try_reconnect():
    # se usi la versione con force_reconnect, passa force_reconnect=True
    ok, ip = connect_from_json("wifi.json", timeout=15)
    return ok, ip

def run_wifi_loop(check_interval=30, heartbeat=True):
    """Controlla la connessione ogni 'check_interval' secondi e riconnette se serve."""
    ok, ip = connect_from_json("wifi.json", timeout=15)
    print("OK:", ok, "IP:", ip)
    prev_ok = ok
    if ok:
        log.info("WiFi up (ip=%s)" % ip)
    else:
        log.warn("WiFi down at start; will retry")

    while True:
        try:
            connected = wifi_is_ok()

            # Heartbeat: stampa SEMPRE ad ogni ciclo
            if heartbeat:
                if connected:
                    sta = network.WLAN(network.STA_IF)
                    ip_now = sta.ifconfig()[0]
                    rssi = None
                    try:
                        rssi = sta.status('rssi')
                    except Exception:
                        pass
                    if rssi is None:
                        print("[%s] HB connected ip=%s" % (ts(), ip_now))
                    else:
                        print("[%s] HB connected ip=%s rssi=%sdBm" % (ts(), ip_now, rssi))
                else:
                    print("[%s] HB not connected" % ts())

            if connected:
                if not prev_ok:
                    sta = network.WLAN(network.STA_IF)
                    log.info("WiFi restored (ip=%s)" % sta.ifconfig()[0])
                    prev_ok = True
            else:
                if prev_ok:
                    log.warn("WiFi lost; trying reconnect")
                ok, ip = try_reconnect()
                prev_ok = ok
                if ok:
                    log.info("Reconnected (ip=%s)" % ip)
                else:
                    log.error("Reconnect failed")

            # dorme per 'check_interval' secondi (a passi da 1s per Ctrl-C/soft reboot)
            for _ in range(int(check_interval)):
                time.sleep(1)

        except KeyboardInterrupt:
            log.info("Loop interrupted by user")
            break
        except Exception as e:
            log.error("Loop exception: %r" % e)
            time.sleep(5)

# Avvio con intervallo parametrico e heartbeat attivo
run_wifi_loop(check_interval=30, heartbeat=True)


# vedere le ultime 100 righe di log
log = RollingLogger(path="log.txt")
print(log.tail(100))