# server/feature.py


def start(context=None):
    try:
        from server.server import start_server

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
