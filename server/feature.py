# server/feature.py


def start(context=None):
    try:
        from core.config import feature_enabled

        from server.server import clear_handlers, register_handler, start_server, get_handlers
        from server.scope_handler import handle as scope_handle
        from server.status_handler import handle as status_handle
        from server.system_handler import handle as system_handle
        from server.fs_handler import handle as fs_handle
        from server.wifi_handler import handle as wifi_handler
        from server.power_sensors_handler import handle as power_sensors_handle
        from server.relay_handler import handle as relay_handle
        from server.pzem017_handler import handle as pzem017_handle

        clear_handlers()

        register_handler("status_handler", status_handle)
        register_handler("system_handler", system_handle)
        register_handler("wifi_handler", wifi_handler)

        if feature_enabled("scope"):
            register_handler("scope_handler", scope_handle)

        if feature_enabled("fs"):
            register_handler("fs_handler", fs_handle)

        if feature_enabled("power_sensors"):
            register_handler("power_sensors_handler", power_sensors_handle)
            print("[DEBUG] power_sensors_handler registered")

        if feature_enabled("relay"):
            register_handler("relay_handler", relay_handle)

        if feature_enabled("pzem_017"):
            register_handler("pzem017_handler", pzem017_handle)
            print("[DEBUG] pzem017_handler registered")

        def _run_server():
            print("[SERVER] start_server()")
            start_server(preferred_port=80, fallback_port=8080, verbose=True)

        print("[DEBUG] HANDLERS:", [name for name, _ in get_handlers()])
        _run_server()

    except Exception as e:
        print("[SERVER] start failed:", e)
