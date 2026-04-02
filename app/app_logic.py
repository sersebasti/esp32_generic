# app/app_logic.py
# Minimal application bootstrap: connect Wi-Fi first, then start server.

import time

from core.config import feature_enabled


def start_app():
	context = {}
	wifi_mgr = None

	# --- Display: messaggio di avvio ---
	lcd = None
	try:
		from display.display_manager import create_lcd
		lcd = create_lcd()
		lcd.clear()
		lcd.write(0, 0, "Starting...")
	except Exception:
		lcd = None

	if feature_enabled("wifi"):
		from wifi.feature import start as start_wifi

		# start_wifi popola context con wifi_manager e lo restituisce anche nel result.
		result = start_wifi(context)
		if isinstance(result, dict):
			context.update(result)
		wifi_mgr = context.get("wifi_manager")

	if wifi_mgr is not None:
		connected = connect_wifi(wifi_mgr)
		if not connected:
			return context

	if feature_enabled("server"):
		from server.feature import start as start_server_feature

		result = start_server_feature(context)
		if isinstance(result, dict):
			context.update(result)

	return context


def connect_wifi(wifi_mgr):
	wifi_mgr.log.info("WiFiManager bootstrap: connessione iniziale")

	# Tenta la connessione iniziale: se il Wi-Fi e gia attivo esce subito, altrimenti prova le reti configurate.
	while True:
		try:
			import network

			sta = network.WLAN(network.STA_IF)
			if sta and sta.isconnected():
				ip = sta.ifconfig()[0]
				wifi_mgr.log.info("Wi-Fi gia connesso con IP %s" % ip)
				return True
		except Exception:
			pass

		wifi_mgr._reset_wifi()
		nets = wifi_mgr._load_networks()
		if not nets:
			wifi_mgr.log.info("Nessuna rete configurata in %s" % wifi_mgr.wifi_json)
			return False

		nets = wifi_mgr._prioritize_by_scan(nets)
		for ssid, pwd in nets:
			ok, ip, reason = wifi_mgr._try_connect(ssid, pwd, timeout_s=15)
			if ok:
				wifi_mgr._ap_disable()
				try:
					wifi_mgr.leds.show_connected()
				except Exception:
					pass
				wifi_mgr.log.info("Connesso a '%s' con IP %s" % (ssid, ip))
				try:
					wifi_mgr._sync_time_once()
				except Exception:
					pass
				return True

			wifi_mgr.log.info("Connessione fallita a '%s' (%s)" % (ssid, reason or "fail"))
			time.sleep_ms(500)

		time.sleep(2)

	if wifi_mgr is not None and lcd:
		try:
			import network
			sta = network.WLAN(network.STA_IF)
			if sta and sta.isconnected():
				ip = sta.ifconfig()[0]
				ssid = wifi_mgr._current_ssid if hasattr(wifi_mgr, '_current_ssid') else ""
				lcd.clear()
				lcd.write(0, 0, "IP=" + ip)
				lcd.write(1, 0, ssid)
		except Exception:
			pass
