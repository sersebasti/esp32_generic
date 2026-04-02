# server/feature.py


def start(context=None):
    try:
        from server.server import clear_handlers, register_handler, start_server
        from server.status_handler import handle as status_handle
        from server.system_handler import handle as system_handle

        clear_handlers()
        register_handler("status_handler", status_handle)
        register_handler("system_handler", system_handle)

        def _run_server():
            print("[SERVER] start_server()")
            start_server(preferred_port=80, fallback_port=8080, verbose=True)

        try:
            import _thread
            _thread.start_new_thread(_run_server, ())
        except Exception:
            _run_server()
    except Exception as e:
        print("[SERVER] start failed:", e)
