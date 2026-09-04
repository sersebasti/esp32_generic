def _register_core_handlers(register_handler):
    from server.status_handler import handle as status_handle
    from server.system_handler import handle as system_handle
    from server.wifi_handler import handle as wifi_handler

    register_handler("status_handler", status_handle)
    register_handler("system_handler", system_handle)
    register_handler("wifi_handler", wifi_handler)


def _register_optional_handlers(register_handler, feature_enabled):
    handler_specs = (
        ("scope", "scope_handler", "server.scope_handler"),
        ("fs", "fs_handler", "server.fs_handler"),
        ("power_sensors", "power_sensors_handler", "server.power_sensors_handler"),
        ("relay", "relay_handler", "server.relay_handler"),
        ("pzem_017", "pzem017_handler", "server.pzem017_handler"),
    )

    for feature_name, handler_name, module_name in handler_specs:
        if not feature_enabled(feature_name):
            continue

        module = __import__(module_name, None, None, ("handle",))
        register_handler(handler_name, module.handle)


def start(context=None):
    try:
        from core.config import feature_enabled
        from server.server import clear_handlers, get_handlers, register_handler, start_server

        clear_handlers()
        _register_core_handlers(register_handler)
        _register_optional_handlers(register_handler, feature_enabled)

        print("[DEBUG] HANDLERS:", [name for name, _ in get_handlers()])
        print("[SERVER] start_server()")
        start_server(preferred_port=80, fallback_port=8080, verbose=True)

        if isinstance(context, dict):
            context["server_started"] = True
        return {"server_started": True}
    except Exception as e:
        print("[SERVER] start failed:", e)
        if isinstance(context, dict):
            context["server_started"] = False
            context["server_error"] = str(e)
        return {"server_started": False, "server_error": str(e)}
