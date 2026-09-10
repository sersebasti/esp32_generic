# pzem_017/pzem017_sensor.py

import ujson

from core.modbus_rtu import ModbusRtuRs485


with open("pzem_017/pzem_017.json") as config_file:
    CONFIG = ujson.load(config_file)


SLAVE_ADDR = CONFIG.get("slave_addr", 1)
REGISTER_COUNT = 8

bus = ModbusRtuRs485(
    uart_id=CONFIG.get("uart_id", 2),
    tx=CONFIG.get("tx", 26),
    rx=CONFIG.get("rx", 27),
    dir_pin=CONFIG.get("dir_pin", 25),
    baudrate=CONFIG.get("baudrate", 9600)
)


def read_pzem017():
    result = bus.read_input_registers(
        slave_addr=SLAVE_ADDR,
        start_register=0,
        count=REGISTER_COUNT,
        timeout_ms=CONFIG.get("timeout_ms", 800),
        retries=CONFIG.get("retries", 3)
    )

    if not result.get("ok"):
        return result

    registers = result["registers"]
    voltage_raw = registers[0]
    result["voltage_raw"] = voltage_raw
    result["voltage_v"] = voltage_raw / 100.0
    return result


def start_pzem017():
    print("[PZEM-017] modulo inizializzato")
    print("[PZEM-017] UART{} TX={} RX={} DIR={}".format(
        CONFIG.get("uart_id", 2),
        CONFIG.get("tx", 26),
        CONFIG.get("rx", 27),
        CONFIG.get("dir_pin", 25)
    ))
    return True
