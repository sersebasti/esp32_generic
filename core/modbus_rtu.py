from machine import UART, Pin
import time


class ModbusRtuRs485:
    def __init__(self, uart_id, tx, rx, dir_pin, baudrate=9600):
        self.uart = UART(
            uart_id,
            baudrate=baudrate,
            bits=8,
            parity=None,
            stop=1,
            tx=tx,
            rx=rx
        )
        self.rs485_dir = Pin(dir_pin, Pin.OUT)
        self.rs485_dir.value(0)

    @staticmethod
    def crc(data):
        crc = 0xFFFF
        for byte in data:
            crc ^= byte
            for _ in range(8):
                if crc & 1:
                    crc = (crc >> 1) ^ 0xA001
                else:
                    crc >>= 1
        return crc

    @staticmethod
    def to_hex(data):
        if not data:
            return ""
        return " ".join("{:02X}".format(byte) for byte in data)

    def _build_read_frame(self, slave_addr, function, start_register, count):
        frame = bytearray([
            slave_addr,
            function,
            (start_register >> 8) & 0xFF,
            start_register & 0xFF,
            (count >> 8) & 0xFF,
            count & 0xFF
        ])
        crc = self.crc(frame)
        frame.append(crc & 0xFF)
        frame.append((crc >> 8) & 0xFF)
        return frame

    def _write_read(self, frame, expected_length, timeout_ms):
        try:
            while self.uart.any():
                self.uart.read()
        except Exception:
            pass

        self.rs485_dir.value(1)
        time.sleep_ms(5)
        self.uart.write(frame)
        time.sleep_ms(50)
        self.rs485_dir.value(0)

        start = time.ticks_ms()
        response = bytearray()
        while time.ticks_diff(time.ticks_ms(), start) < timeout_ms:
            if self.uart.any():
                chunk = self.uart.read()
                if chunk:
                    response.extend(chunk)
                    if len(response) >= expected_length:
                        break
            time.sleep_ms(10)

        if response:
            return bytes(response)
        return None

    def read_input_registers(self, slave_addr, start_register, count,
                             timeout_ms=800, retries=3):
        function = 0x04
        byte_count = count * 2
        expected_length = 3 + byte_count + 2
        frame = self._build_read_frame(
            slave_addr, function, start_register, count
        )
        last_result = None

        for attempt in range(1, retries + 1):
            print("[MODBUS] tentativo", attempt)
            print("[MODBUS] TX:", self.to_hex(frame))
            response = self._write_read(frame, expected_length, timeout_ms)

            if not response:
                print("[MODBUS] nessuna risposta")
                last_result = {"ok": False, "err": "no_response"}
                time.sleep_ms(200)
                continue

            print("[MODBUS] RX:", self.to_hex(response))
            result = self._parse_read_response(
                response, slave_addr, function, byte_count
            )
            if result.get("ok"):
                return result

            print("[MODBUS] errore:", result)
            last_result = result
            time.sleep_ms(200)

        return {
            "ok": False,
            "err": "no_valid_response_after_retries",
            "last_result": last_result
        }

    def _parse_read_response(self, response, slave_addr, function, byte_count):
        raw_hex = self.to_hex(response)
        if len(response) < 5:
            return {"ok": False, "err": "short_response", "raw": raw_hex}

        crc_received = response[-2] | (response[-1] << 8)
        if crc_received != self.crc(response[:-2]):
            return {"ok": False, "err": "crc_error", "raw": raw_hex}

        if response[0] != slave_addr:
            return {
                "ok": False,
                "err": "wrong_slave",
                "expected": slave_addr,
                "received": response[0],
                "raw": raw_hex
            }

        if response[1] != function:
            return {
                "ok": False,
                "err": "wrong_function",
                "expected": function,
                "received": response[1],
                "raw": raw_hex
            }

        if response[2] != byte_count:
            return {
                "ok": False,
                "err": "wrong_byte_count",
                "expected": byte_count,
                "received": response[2],
                "raw": raw_hex
            }

        expected_length = 3 + byte_count + 2
        if len(response) != expected_length:
            return {
                "ok": False,
                "err": "wrong_response_length",
                "expected": expected_length,
                "received": len(response),
                "raw": raw_hex
            }

        registers = []
        for index in range(3, 3 + byte_count, 2):
            registers.append((response[index] << 8) | response[index + 1])

        return {
            "ok": True,
            "slave": response[0],
            "function": response[1],
            "byte_count": byte_count,
            "registers": registers,
            "raw": raw_hex
        }
