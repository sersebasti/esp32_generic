# app/app_logic.py
# Minimal application bootstrap: connect Wi-Fi first, then start server.

import time
import _thread
import machine

from core.config import feature_enabled


def start_app():
	context = {}
	wifi_mgr = None

	# --- AP button async monitor ---
	def start_ap_button_monitor(wifi_mgr):
		# Monitora il pulsante AP in un thread separato, termina quando ap_monitor_running diventa False
		def monitor():
			while getattr(wifi_mgr, "ap_monitor_running", True):
				try:
					if hasattr(wifi_mgr, "button_pressed") and wifi_mgr.button_pressed():
						wifi_mgr.ap_requested = True
						break
				except Exception:
					pass
				time.sleep_ms(100)
		try:
			wifi_mgr.ap_requested = False
			wifi_mgr.ap_monitor_running = True
			_thread.start_new_thread(monitor, ())
		except Exception:
			pass

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
		start_ap_button_monitor(wifi_mgr)
		connected = connect_wifi(wifi_mgr, lcd)
		ap_mode = getattr(wifi_mgr, '_setup_mode', False)
		# Avvia il server se connesso o se in AP mode
		if connected or ap_mode:
			if feature_enabled("server"):
				from server.feature import start as start_server_feature
				result = start_server_feature(context)
				if isinstance(result, dict):
					context.update(result)
	return context


def connect_wifi(wifi_mgr, lcd=None):
	wifi_mgr.log.info("WiFiManager bootstrap: connessione iniziale")

	# Usa LedStatus per la gestione del LED
	if hasattr(wifi_mgr, 'leds') and wifi_mgr.leds:
		wifi_mgr.leds.show_connecting()

	try:
		while True:
			# ...

			try:
				import network
				sta = network.WLAN(network.STA_IF)
				if sta and sta.isconnected():
					ip = sta.ifconfig()[0]
					wifi_mgr.log.info("Wi-Fi gia connesso con IP %s" % ip)
					break
			except Exception:
				pass

			wifi_mgr._reset_wifi()
			nets = wifi_mgr._load_networks()
			if not nets:
				wifi_mgr.log.info("Nessuna rete configurata in %s" % wifi_mgr.wifi_json)
				break

			nets = wifi_mgr._prioritize_by_scan(nets)
			for ssid, pwd in nets:
				# Mostra stato su LCD
				if lcd:
					try:
						lcd.clear()
						lcd.write(0, 0, "Connecting...")
						lcd.write(1, 0, (ssid or "")[:16])
					except Exception:
						pass
				# Controlla il pulsante anche durante i tentativi
				if getattr(wifi_mgr, "ap_requested", False):
					wifi_mgr.log.info("Pulsante AP premuto: attivo Access Point!")
					wifi_mgr._enter_setup_once()
					# LED: AP mode
					if hasattr(wifi_mgr, 'leds') and wifi_mgr.leds:
						wifi_mgr.leds.show_ap()
					# Mostra su LCD: IP AP e 'AP MODE'
					if lcd:
						try:
							ap_ip = "192.168.4.1"
							try:
								import network
								ap = network.WLAN(network.AP_IF)
								if ap.active():
									ap_ip = ap.ifconfig()[0]
							except Exception:
								pass
							lcd.clear()
							lcd.write(0, 0, ("ip: " + str(ap_ip))[:16])
							lcd.write(1, 0, "AP MODE")
						except Exception:
							pass
					return False
				# Passa una callback che controlla ap_requested per interruzione immediata
				def cancel_cb():
					return getattr(wifi_mgr, "ap_requested", False)
				ok, ip, reason = wifi_mgr._try_connect(ssid, pwd, timeout_s=15, cancel_cb=cancel_cb)
				if ok:
					wifi_mgr._ap_disable()
					# LED: connessione riuscita
					if hasattr(wifi_mgr, 'leds') and wifi_mgr.leds:
						wifi_mgr.leds.show_connected()
					wifi_mgr.log.info("Connesso a '%s' con IP %s" % (ssid, ip))
					# Mostra su LCD: ip e nome rete
					if lcd:
						try:
							lcd.clear()
							lcd.write(0, 0, ("ip: " + str(ip))[:16])
							lcd.write(1, 0, (ssid or "")[:16])
						except Exception:
							pass
					try:
						wifi_mgr._sync_time_once()
					except Exception:
						pass
					break
				wifi_mgr.log.info("Connessione fallita a '%s' (%s)" % (ssid, reason or "fail"))

			# Pausa fissa dopo i tentativi (ora senza controllo su ap_requested)
			time.sleep(2)
	finally:
		# Ferma il thread di monitoraggio pulsante AP
		if hasattr(wifi_mgr, "ap_monitor_running"):
			wifi_mgr.ap_monitor_running = False
		# LED: spegni lampeggio/led se previsto da LedStatus (opzionale)
		if hasattr(wifi_mgr, 'leds') and wifi_mgr.leds:
			wifi_mgr.leds.show_connected()

	# Verifica stato finale
	try:
		import network
		sta = network.WLAN(network.STA_IF)
		if sta and sta.isconnected():
			return True
		else:
			return False
	except Exception:
		return False
