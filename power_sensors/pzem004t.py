# pzem004t.py
# Classe base per la comunicazione con il modulo PZEM-004T su ESP32 (MicroPython)
# Supporta lettura di tensione, corrente, potenza, energia tramite UART (protocollo Modbus-RTU)

import time
from machine import UART

class PZEM004T:
    def __init__(self, uart_id=1, tx=17, rx=16, baudrate=9600, slave_addr=0xF8, uart=None):
        if not 1 <= slave_addr <= 0xF8:
            raise ValueError("slave_addr must be between 1 and 248")
        self.slave_addr = slave_addr
        self.uart = uart if uart is not None else UART(
            uart_id, baudrate=baudrate, tx=tx, rx=rx, timeout=100
        )
        if uart is None:
            time.sleep(1)

    def _crc16(self, data):
        crc = 0xFFFF
        for b in data:
            crc ^= b
            for _ in range(8):
                if crc & 0x0001:
                    crc >>= 1
                    crc ^= 0xA001
                else:
                    crc >>= 1
        return crc

    def _build_read_cmd(self, reg_addr=0x0000, reg_count=10):
        cmd = bytearray([
            self.slave_addr,
            0x04,  # Function code: Read Input Register
            (reg_addr >> 8) & 0xFF,
            reg_addr & 0xFF,
            (reg_count >> 8) & 0xFF,
            reg_count & 0xFF
        ])
        crc = self._crc16(cmd)
        cmd.append(crc & 0xFF)      # CRC low byte
        cmd.append((crc >> 8) & 0xFF)  # CRC high byte
        return cmd

    def _send_command(self, cmd):
        while self.uart.any():
            self.uart.read()
        self.uart.write(cmd)
        time.sleep(0.1)
        return self.uart.read()

    def set_slave_addr(self, new_addr):
        if not 1 <= new_addr <= 0xF7:
            raise ValueError("new_addr must be between 1 and 247")
        cmd = bytearray([
            self.slave_addr,
            0x06,
            0x00,
            0x02,
            0x00,
            new_addr,
        ])
        crc = self._crc16(cmd)
        cmd.append(crc & 0xFF)
        cmd.append((crc >> 8) & 0xFF)
        resp = self._send_command(cmd)
        if (resp and len(resp) >= 8 and resp[:6] == cmd[:6]
                and self._crc16(resp[:-2]) == (resp[-2] | resp[-1] << 8)):
            self.slave_addr = new_addr
            return True
        return False

    def read_all(self):
        cmd = self._build_read_cmd()
        resp = self._send_command(cmd)
        if (resp and len(resp) >= 25 and resp[0] == self.slave_addr
            and resp[1] == 0x04 and resp[2] >= 20
            and self._crc16(resp[:-2]) == (resp[-2] | resp[-1] << 8)):
            # Parsing secondo datasheet
            voltage = (resp[3] << 8 | resp[4]) / 10.0
            current = (resp[5] << 8 | resp[6] | resp[7] << 24 | resp[8] << 16) / 1000.0  # 4 byte
            power = (resp[9] << 8 | resp[10] | resp[11] << 24 | resp[12] << 16) / 10.0   # 4 byte
            energy = (resp[13] << 24 | resp[14] << 16 | resp[15] << 8 | resp[16])        # 4 byte
            freq = (resp[17] << 8 | resp[18]) / 10.0
            pf = (resp[19] << 8 | resp[20]) / 100.0
            alarm = (resp[21] << 8 | resp[22])
            return {
                'voltage': voltage,
                'current': current,
                'power': power,
                'energy': energy,
                'frequency': freq,
                'power_factor': pf,
                'alarm': alarm
            }
        return None
