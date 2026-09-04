import _thread
import time

from core.config import feature_enabled


def _format_mem_line(free_mem):
	try:
		return ("MEM:" + str(int(free_mem)) + "B")[:16]
	except Exception:
		return "MEM:N/A"


def _show_connected_on_display(display, ip, free_mem):
	if not display:
		return
	try:
		ip_text = str(ip).strip()
		display.clear()
		# On LCD/OLED 16-colonne un IPv4 completo (max 15 char) entra solo senza prefissi.
		display.write(0, 0, ip_text[:16])
		display.write(1, 0, _format_mem_line(free_mem))
	except Exception:
		pass


def _start_ap_button_monitor(wifi_mgr):
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


def _start_wifi_monitor(wifi_mgr, display=None, check_interval=30):
	def monitor():
		import gc
		import network

		while True:
			gc.collect()
			try:
				sta = network.WLAN(network.STA_IF)
				free_mem = gc.mem_free() if hasattr(gc, "mem_free") else "N/A"
				ip = sta.ifconfig()[0] if sta.isconnected() else "0.0.0.0"
				ssid = None
				rssi = None

				if sta.isconnected():
					try:
						ssid = sta.config("essid")
					except Exception:
						ssid = None
					try:
						rssi = sta.status("rssi")
					except Exception:
						rssi = None

				print(
					"[WIFI-MONITOR] IP: {} | SSID: {} | Segnale: {} dBm | Memoria libera: {} bytes".format(
						ip, ssid, rssi, free_mem
					)
				)

				if sta.isconnected():
					_show_connected_on_display(display, ip, free_mem)

				if not sta.isconnected() and not getattr(wifi_mgr, "_setup_mode", False):
					wifi_mgr.log.info("[WIFI-MONITOR] WiFi disconnesso, tento riconnessione...")
					_start_ap_button_monitor(wifi_mgr)
					connect_wifi(wifi_mgr, display)
			except Exception:
				pass
			time.sleep(check_interval)

	if not hasattr(wifi_mgr, "_wifi_monitor_started"):
		wifi_mgr._wifi_monitor_started = True
		_thread.start_new_thread(monitor, ())


def _create_display_if_available():
	try:
		from display.display_manager import create_lcd

		display = create_lcd()
		display.clear()
		display.write(0, 0, "Starting...")
		return display
	except Exception:
		return None


def _show_ap_mode_on_display(display):
	if not display:
		return

	try:
		import network

		ap_ssid = "ESP-SETUP"
		ap_ip = "192.168.4.1"
		ap = network.WLAN(network.AP_IF)
		if ap.active():
			try:
				ap_ssid = str(ap.config("essid") or ap_ssid)
			except Exception:
				pass
			ap_ip = ap.ifconfig()[0]
		display.clear()
		display.write(0, 0, ("AP:" + str(ap_ssid))[:16])
		display.write(1, 0, ("IP:" + str(ap_ip))[:16])
	except Exception:
		pass


def _bootstrap_wifi(context, display):
	if not feature_enabled("wifi"):
		return None, False

	from wifi.feature import start as start_wifi

	result = start_wifi(context)
	if isinstance(result, dict):
		context.update(result)

	wifi_mgr = context.get("wifi_manager")
	if wifi_mgr is None:
		return None, False

	_start_ap_button_monitor(wifi_mgr)
	connected = connect_wifi(wifi_mgr, display)
	if connected:
		_start_wifi_monitor(wifi_mgr, display=display, check_interval=30)
	return wifi_mgr, connected


def _bootstrap_server(context, wifi_mgr, connected):
	if wifi_mgr is None or not feature_enabled("server"):
		return

	ap_mode = getattr(wifi_mgr, "_setup_mode", False)
	if not connected and not ap_mode:
		return

	from server.feature import start as start_server_feature

	result = start_server_feature(context)
	if isinstance(result, dict):
		context.update(result)


def _bootstrap_mdns(context, wifi_mgr, connected):
	if wifi_mgr is None or not connected or not feature_enabled("mdns"):
		return
	try:
		from core.config import MDNS_HOSTNAME, MDNS_HTTP_PORT
		from core.mdns_manager import MDNSManager

		manager = MDNSManager(MDNS_HOSTNAME, MDNS_HTTP_PORT, wifi_mgr.log)
		if manager.start():
			wifi_mgr.mdns_manager = manager
			context["mdns_manager"] = manager
	except Exception as error:
		wifi_mgr.log.info("mDNS bootstrap fallito: %r" % error)


def start_app():
	context = {}
	display = _create_display_if_available()
	wifi_mgr, connected = _bootstrap_wifi(context, display)
	_bootstrap_mdns(context, wifi_mgr, connected)
	_bootstrap_server(context, wifi_mgr, connected)
	return context


def connect_wifi(wifi_mgr, display=None):
	wifi_mgr.log.info("WiFiManager bootstrap: connessione iniziale")

	# Usa LedStatus per la gestione del LED
	if hasattr(wifi_mgr, 'leds') and wifi_mgr.leds:
		wifi_mgr.leds.show_connecting()

	try:
		while True:
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
			connected = False
			for ssid, pwd in nets:
				if display:
					try:
						display.clear()
						display.write(0, 0, "Connecting...")
						display.write(1, 0, (ssid or "")[:16])
					except Exception:
						pass

				if getattr(wifi_mgr, "ap_requested", False):
					wifi_mgr.log.info("Pulsante AP premuto: attivo Access Point!")
					wifi_mgr._enter_setup_once()
					if hasattr(wifi_mgr, "leds") and wifi_mgr.leds:
						wifi_mgr.leds.show_ap()
					_show_ap_mode_on_display(display)
					return False

				def cancel_cb():
					return getattr(wifi_mgr, "ap_requested", False)

				ok, ip, reason = wifi_mgr._try_connect(ssid, pwd, timeout_s=15, cancel_cb=cancel_cb)
				if not ok:
					wifi_mgr.log.info("Connessione fallita a '%s' (%s)" % (ssid, reason or "fail"))
					continue

				wifi_mgr._ap_disable()
				if hasattr(wifi_mgr, "leds") and wifi_mgr.leds:
					wifi_mgr.leds.show_connected()
				wifi_mgr.log.info("Connesso a '%s' con IP %s" % (ssid, ip))

				if display:
					try:
						import gc
						free_mem = gc.mem_free() if hasattr(gc, "mem_free") else "N/A"
						_show_connected_on_display(display, ip, free_mem)
					except Exception:
						pass

				try:
					wifi_mgr._sync_time_once()
				except Exception:
					pass

				connected = True
				break

			if connected:
				break

			time.sleep(2)
	finally:
		if hasattr(wifi_mgr, "ap_monitor_running"):
			wifi_mgr.ap_monitor_running = False
		if hasattr(wifi_mgr, 'leds') and wifi_mgr.leds:
			if not getattr(wifi_mgr, '_setup_mode', False):
				wifi_mgr.leds.show_connected()

	try:
		import network
		sta = network.WLAN(network.STA_IF)
		if sta and sta.isconnected():
			return True
		else:
			return False
	except Exception:
		return False
