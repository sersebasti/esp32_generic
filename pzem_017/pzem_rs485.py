from machine import UART, Pin
import time


UART_ID = 2
TX_PIN = 26
RX_PIN = 27
DIR_PIN = 25

uart = UART(
    UART_ID,
    baudrate=9600,
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
    return " ".join("{:02X}".format(b) for b in data)


def rs485_write_read(frame, wait_ms=200):
    # pulisce eventuali byte vecchi
    while uart.any():
        uart.read()

    # trasmissione
    rs485_dir.value(1)
    time.sleep_ms(2)

    uart.write(frame)
    time.sleep_ms(20)

    # ricezione
    rs485_dir.value(0)
    time.sleep_ms(wait_ms)

    if uart.any():
        return uart.read()

    return None


def test_pzem017_raw():
    # Richiesta Modbus:
    # slave 1, function 04, start register 0000, quantity 0008
    frame = bytearray([0x01, 0x04, 0x00, 0x00, 0x00, 0x08])

    crc = modbus_crc(frame)
    frame.append(crc & 0xFF)
    frame.append((crc >> 8) & 0xFF)

    print("[PZEM-017] TX:", to_hex(frame))

    response = rs485_write_read(frame)

    if response:
        print("[PZEM-017] RX:", to_hex(response))
    else:
        print("[PZEM-017] nessuna risposta")


def start_pzem017():
    print("[PZEM-017] avvio test RS485")
    print("[PZEM-017] UART{} TX={} RX={} DIR={}".format(
        UART_ID, TX_PIN, RX_PIN, DIR_PIN
    ))

    test_pzem017_raw()