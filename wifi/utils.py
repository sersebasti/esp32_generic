# wifi/utils.py


def mac_hex_upper():
    try:
        import ubinascii
        import network
        mac = network.WLAN(network.STA_IF).config("mac")
        return ubinascii.hexlify(mac).decode().upper()
    except Exception:
        return None


def ssid_from_mac(prefix="ESP32_", fallback="ESP-SETUP", max_len=32):
    mac_hex = mac_hex_upper()
    if not mac_hex:
        return fallback
    full = prefix + mac_hex
    if len(full) <= max_len:
        return full
    short = prefix + mac_hex[-6:]
    return short[:max_len]


def device_name_from_mac(prefix="ESP32_", fallback="ESP-SETUP", max_len=32):
    return ssid_from_mac(prefix=prefix, fallback=fallback, max_len=max_len)


def apply_sta_hostname(log, name=None, prefix="ESP32_", fallback="ESP-SETUP", max_len=32):
    try:
        import network
        sta = network.WLAN(network.STA_IF)
    except Exception:
        sta = None
    if not sta:
        return False
    if not name:
        name = device_name_from_mac(prefix=prefix, fallback=fallback, max_len=max_len)
    ok = False
    try:
        sta.active(True)
    except Exception:
        pass
    try:
        sta.config(dhcp_hostname=name)
        ok = True
    except Exception:
        pass
    if not ok:
        try:
            sta.config(hostname=name)
            ok = True
        except Exception:
            pass
    if not ok:
        try:
            network.hostname(name)  # type: ignore
            ok = True
        except Exception:
            pass
    if log:
        if ok:
            try:
                log.info("Hostname STA impostato: %s" % name)
            except Exception:
                pass
        else:
            try:
                log.info("Impostazione hostname STA non supportata su questa build")
            except Exception:
                pass
    return ok
