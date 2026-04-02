# app/app_logic.py
# Minimal application bootstrap: connect Wi-Fi first, then start server.

import time
import _thread
import machine

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


def connect_wifi(wifi_mgr):
	wifi_mgr.log.info("WiFiManager bootstrap: connessione iniziale")
def connect_wifi(wifi_mgr, lcd=None):
	wifi_mgr.log.info("WiFiManager bootstrap: connessione iniziale")

	# Setup LED blu (D2 = GPIO2)
	led = machine.Pin(2, machine.Pin.OUT)
	led.off()
	led_blinking = True

	def blink_led():
		while led_blinking:
			led.on()
			time.sleep_ms(500)
			led.off()
			time.sleep_ms(500)

	_thread.start_new_thread(blink_led, ())

	try:
		while True:
			# Se il pulsante AP è premuto a lungo, attiva AP e termina
			if hasattr(wifi_mgr, "button_pressed") and wifi_mgr.button_pressed():
				wifi_mgr.log.info("Pulsante AP premuto: attivo Access Point!")
				wifi_mgr._enter_setup_once()
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
				if hasattr(wifi_mgr, "button_pressed") and wifi_mgr.button_pressed():
					wifi_mgr.log.info("Pulsante AP premuto: attivo Access Point!")
					wifi_mgr._enter_setup_once()
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
				ok, ip, reason = wifi_mgr._try_connect(ssid, pwd, timeout_s=15)
				if ok:
					wifi_mgr._ap_disable()
					try:
						wifi_mgr.leds.show_connected()
					except Exception:
						pass
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
				time.sleep_ms(500)

			time.sleep(2)
	finally:
		# Ferma il lampeggio e spegne il LED
		led_blinking = False
		led.off()

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
