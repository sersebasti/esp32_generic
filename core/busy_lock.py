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
