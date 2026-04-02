# app/app_logic.py
# Application-level loop and orchestration.

import time
from core.config import feature_enabled
from core.feature_runner import start_enabled_features


def start_app():
    context = start_enabled_features()
    wifi_mgr = None
    if isinstance(context, dict):
        wifi_mgr = context.get("wifi_manager")
    if wifi_mgr and feature_enabled("wifi"):
        run_wifi_loop(wifi_mgr)
    return context


def run_wifi_loop(wifi_mgr):
    lcd = None
    if feature_enabled("display"):
        try:
            from display import create_lcd
            lcd = create_lcd()
        except Exception:
            lcd = None
    display_state = {"line0": None, "line1": None}

    def _lcd_show(line0, line1=""):
        if not lcd:
            return
        if line0 is None:
            return
        line1 = line1 or ""
        if (line0, line1) == (display_state["line0"], display_state["line1"]):
            return
        display_state["line0"] = line0
        display_state["line1"] = line1
        try:
            lcd.clear()
            lcd.write(0, 0, line0[:16])
            lcd.write(1, 0, line1[:16])
        except Exception:
            pass

    server_enabled = feature_enabled("server")
    server_port = 80
    fallback_port = 8080
    backoff_retry_ms = 500
    backoff_no_net_s = 5
    backoff_all_fail_s = 2
    health_ok_sleep_s = 5

    wifi_mgr.log.info("WiFiManager avviato: modalita 'never auto-AP'")
    last_status_ms = 0
    server_check_warned = False
    while True:
        import gc, machine
        mem_free = gc.mem_free()
        if mem_free < 10000:
            print("[WARNING] Memoria critica! Riavvio per evitare crash.")
            machine.reset()
        if (not wifi_mgr._setup_mode) and wifi_mgr.button_pressed(clear=True, long_ms=800):
            wifi_mgr.log.info("🔘 Pulsante (long-press) → setup mode")
            break

        if server_enabled:
            result = wifi_mgr.check_wifi_and_server(port=server_port)
            if not result.get("server_ok"):
                fallback_res = wifi_mgr.check_wifi_and_server(port=fallback_port)
                if fallback_res.get("server_ok"):
                    result = fallback_res
        else:
            sta = None
            try:
                import network
                sta = network.WLAN(network.STA_IF)
            except Exception:
                sta = None
            wifi_ok = bool(sta.isconnected()) if sta else False
            ip = sta.ifconfig()[0] if (sta and wifi_ok) else None
            result = {"wifi_ok": wifi_ok, "ip": ip, "server_ok": True, "health": None, "error": None}

        wifi_ok = result.get("wifi_ok")
        ip = result.get("ip")
        srv_ok = result.get("server_ok")
        server_state = srv_ok
        if server_enabled and wifi_ok and not srv_ok:
            server_state = True
            srv_ok = True
            if not server_check_warned:
                server_check_warned = True
                wifi_mgr.log.info("Server attivo: uso stato 'enabled' invece del check locale")

        now_ms = time.ticks_ms()
        if time.ticks_diff(now_ms, last_status_ms) >= 5000:
            last_status_ms = now_ms
            ssid = None
            if wifi_ok:
                try:
                    import network
                    sta = network.WLAN(network.STA_IF)
                    if sta and sta.isconnected():
                        ssid = sta.config("essid")
                except Exception:
                    ssid = None
            wifi_mgr.log.info("Status: wifi=%s ip=%s ssid=%s server=%s mem=%s" % (
                wifi_ok, ip or "-", ssid or "-", server_state, mem_free
            ))

        if wifi_ok and ip:
            _lcd_show("IP:" + ip, "")

        if not wifi_ok:
            try:
                wifi_mgr.leds.show_connecting()
            except Exception:
                pass
            wifi_mgr._reset_wifi()
            nets = wifi_mgr._load_networks()
            if not nets:
                wifi_mgr.log.info("Nessuna rete in %s. Riprovo tra %ss." % (wifi_mgr.wifi_json, backoff_no_net_s))
                time.sleep(backoff_no_net_s)
                continue
            nets = wifi_mgr._prioritize_by_scan(nets)
            connected = False
            setup_requested = False
            for ssid, pwd in nets:
                if wifi_mgr.button_pressed(clear=True, long_ms=800):
                    wifi_mgr.log.info("🔘 Pulsante durante tentativi → setup mode")
                    setup_requested = True
                    connected = False
                    break

                _lcd_show("Connecting...", ssid)

                ok, ip_new, reason = wifi_mgr._try_connect(
                    ssid, pwd, timeout_s=15,
                    cancel_cb=lambda: wifi_mgr.button_pressed(clear=False, long_ms=800)
                )
                if ok:
                    wifi_mgr._ap_disable()
                    try:
                        wifi_mgr.leds.show_connected()
                    except Exception:
                        pass
                    wifi_mgr.log.info("Connesso a '%s' con IP %s" % (ssid, ip_new))
                    _lcd_show("IP:" + ip_new, "")
                    try:
                        wifi_mgr._sync_time_once()
                    except Exception:
                        pass
                    connected = True
                    break
                else:
                    wifi_mgr.log.info("Connessione fallita a '%s' (%s)" % (ssid, reason or "fail"))
                    if reason == "cancelled":
                        setup_requested = True
                        break
                    time.sleep_ms(backoff_retry_ms)
            if setup_requested:
                break
            if not connected:
                time.sleep(backoff_all_fail_s)
                continue
        else:
            wifi_mgr._ap_disable()
            if srv_ok:
                try:
                    wifi_mgr.leds.show_connected()
                except Exception:
                    pass
                for _ in range(health_ok_sleep_s):
                    if wifi_mgr.button_pressed(clear=True, long_ms=800):
                        wifi_mgr.log.info("🔘 Pulsante durante idle → setup mode")
                        wifi_ok = False
                        break
                    time.sleep(1)
                else:
                    continue
                break

    wifi_mgr._enter_setup_once()
    ap_last_ms = 0
    while True:
        now_ms = time.ticks_ms()
        if time.ticks_diff(now_ms, ap_last_ms) >= 3000:
            ap_last_ms = now_ms
            ap_ip = "192.168.4.1"
            ap_ssid = None
            try:
                import network
                ap = network.WLAN(network.AP_IF)
                if ap and ap.active():
                    ap_ip = ap.ifconfig()[0] or ap_ip
                    try:
                        ap_ssid = ap.config("essid")
                    except Exception:
                        ap_ssid = None
            except Exception:
                ap_ssid = None
            _lcd_show("AP:" + ap_ip, ap_ssid or "")
        wifi_mgr.log.info("Loop Access Point attivo (setup)")
        time.sleep(1)
