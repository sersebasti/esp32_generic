# pzem_017/__init__.py

def start(context=None):
    from pzem_017.pzem_rs485 import start_pzem017
    start_pzem017()
    return {}