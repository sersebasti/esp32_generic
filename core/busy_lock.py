# core/busy_lock.py
# Shared mutable lock with tiny helpers

BUSY = {"v": False}

def is_busy():
    try:
        return bool(BUSY.get("v"))
    except Exception:
        return False

def set_busy(flag):
    try:
        BUSY["v"] = bool(flag)
    except Exception:
        BUSY["v"] = False


class _BusyRegion:
    def __enter__(self):
        set_busy(True)
        return True
    def __exit__(self, exc_type, exc, tb):
        set_busy(False)
        # Do not suppress exceptions
        return False


def busy_region():
    """Context manager that sets BUSY on enter and clears it on exit.

    Usage:
        if is_busy():
            ...
        with busy_region():
            ...
    """
    return _BusyRegion()
