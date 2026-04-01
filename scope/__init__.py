# scope package


def start(context=None):
	try:
		import scope.adc_api  # preload for server thread
	except Exception:
		pass
	return {}