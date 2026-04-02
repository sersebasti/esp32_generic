# server/wifi_handler.py
"""
Handler per endpoint WiFi: /wifi/ui, /wifi/scan, /wifi/list, /wifi/add, /wifi/delete
"""
from wifi.wifi_api import handle as wifi_api_handle

def handle(cl, method, path, req, _read_post_json, _body_initial_and_len=None):
    # Delega la gestione a wifi_api.handle
    return wifi_api_handle(cl, method, path, req, _read_post_json, _body_initial_and_len)
