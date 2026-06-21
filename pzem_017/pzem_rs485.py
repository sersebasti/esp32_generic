# pzem_017/pzem_rs485.py

from machine import UART, Pin
import time


UART_ID = 2
TX_PIN = 26
RX_PIN = 27
DIR_PIN = 25
BAUDRATE = 9600
SLAVE_ADDR = 0x01


uart = UART(
    UART_ID,
    baudrate=BAUDRATE,
    bits=8,
    parity=None,
    stop=1,
    tx=TX_PIN,
    rx=RX_PIN
)

rs485_dir = Pin(DIR_PIN, Pin.OUT)
rs485_dir.value(0)  # ricezione


def modbus_crc(data):
    crc = 0xFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return crc


def to_hex(data):
    if not data:
        return ""
    return " ".join("{:02X}".format(b) for b in data)


def check_crc(resp):
    if not resp or len(resp) < 5:
        return False

    data = resp[:-2]
    crc_received = resp[-2] | (resp[-1] << 8)
    crc_calculated = modbus_crc(data)

    return crc_received == crc_calculated


def build_read_frame(addr=SLAVE_ADDR):
    # slave, function 04, start register 0000, quantity 0008
    frame = bytearray([
        addr,
        0x04,
        0x00,
        0x00,
        0x00,
        0x08
    ])

    crc = modbus_crc(frame)
    frame.append(crc & 0xFF)
    frame.append((crc >> 8) & 0xFF)

    return frame


def rs485_write_read(frame, wait_ms=300):
    # svuota buffer vecchio
    try:
        while uart.any():
            uart.read()
    except Exception:
        pass

    # TX
    rs485_dir.value(1)
    time.sleep_ms(2)

    uart.write(frame)
    time.sleep_ms(20)

    # RX
    rs485_dir.value(0)
    time.sleep_ms(wait_ms)

    if uart.any():
        return uart.read()

    return None


def _registers_from_response(resp):
    regs = []

    # risposta attesa:
    # addr, function, byte_count, 16 byte dati, crc_lo, crc_hi
    byte_count = resp[2]
    data_start = 3
    data_end = data_start + byte_count

    data = resp[data_start:data_end]

    for i in range(0, len(data), 2):
        if i + 1 < len(data):
            regs.append((data[i] << 8) | data[i + 1])

    return regs


def parse_pzem017_response(resp):
    if not resp:
        return {
            "ok": False,
            "err": "no_response"
        }

    raw_hex = to_hex(resp)

    if len(resp) < 5:
        return {
            "ok": False,
            "err": "short_response",
            "raw": raw_hex
        }

    if not check_crc(resp):
        return {
            "ok": False,
            "err": "crc_error",
            "raw": raw_hex
        }

    if resp[0] != SLAVE_ADDR:
        return {
            "ok": False,
            "err": "wrong_slave",
            "slave": resp[0],
            "raw": raw_hex
        }

    if resp[1] != 0x04:
        return {
            "ok": False,
            "err": "wrong_function",
            "function": resp[1],
            "raw": raw_hex
        }

    if len(resp) < 21:
        return {
            "ok": False,
            "err": "incomplete_response",
            "len": len(resp),
            "raw": raw_hex
        }

    regs = _registers_from_response(resp)

    voltage_raw = regs[0] if len(regs) > 0 else None

    # Dal tuo RX 04 83 = 1155, quindi 1155 / 100 = 11.55 V
    voltage_v = None
    if voltage_raw is not None:
        voltage_v = voltage_raw / 100.0

    return {
        "ok": True,
        "slave": resp[0],
        "function": resp[1],
        "byte_count": resp[2],
        "voltage_v": voltage_v,
        "voltage_raw": voltage_raw,
        "registers": regs,
        "raw": raw_hex
    }


def read_pzem017():
    frame = build_read_frame()

    print("[PZEM-017] TX:", to_hex(frame))

    resp = rs485_write_read(frame, wait_ms=300)

    if resp:
        print("[PZEM-017] RX:", to_hex(resp))
    else:
        print("[PZEM-017] nessuna risposta")

    return parse_pzem017_response(resp)


def start_pzem017():
    print("[PZEM-017] modulo inizializzato")
    print("[PZEM-017] UART{} TX={} RX={} DIR={}".format(
        UART_ID,
        TX_PIN,
        RX_PIN,
        DIR_PIN
    ))
    return True