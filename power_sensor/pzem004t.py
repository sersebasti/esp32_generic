# pzem004t.py
# Classe base per la comunicazione con il modulo PZEM-004T su ESP32 (MicroPython)
# Supporta lettura di tensione, corrente, potenza, energia tramite UART

import time
from machine import UART

class PZEM004T:
    def __init__(self, uart_id=1, tx=17, rx=16, baudrate=9600):
        self.uart = UART(uart_id, baudrate=baudrate, tx=tx, rx=rx, timeout=100)
        time.sleep(1)

    def _send_command(self, cmd):
        self.uart.write(cmd)
        time.sleep(0.1)
        return self.uart.read()

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

    def _build_read_cmd(self, slave_addr=0xF8, reg_addr=0x0000, reg_count=10):
        cmd = bytearray([
            slave_addr,
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

    def read_voltage(self):
        # Comando per leggere la tensione (vedi datasheet PZEM-004T)
        cmd = b'\xB0\xC0\xA8\x01\x01\x00\x1A'  # Esempio, da adattare
        resp = self._send_command(cmd)
        # Decodifica risposta (da implementare secondo protocollo)
        return self._parse_voltage(resp)

    def read_current(self):
        # Comando per leggere la corrente
        cmd = b'\xB1\xC0\xA8\x01\x01\x00\x1B'  # Esempio, da adattare
        resp = self._send_command(cmd)
        return self._parse_current(resp)

    def read_power(self):
        # Comando per leggere la potenza
        cmd = b'\xB2\xC0\xA8\x01\x01\x00\x1C'  # Esempio, da adattare
        resp = self._send_command(cmd)
        return self._parse_power(resp)

    def read_energy(self):
        # Comando per leggere l'energia
        cmd = b'\xB3\xC0\xA8\x01\x01\x00\x1D'  # Esempio, da adattare
        resp = self._send_command(cmd)
        return self._parse_energy(resp)

    def read_all(self):
        cmd = self._build_read_cmd()
        resp = self._send_command(cmd)
        if resp and len(resp) >= 25:
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

    def _parse_voltage(self, resp):
        # Risposta: [0xA0, addr, v_hi, v_lo, ..., crc]
        if resp and len(resp) >= 7:
            v = (resp[2] << 8) | resp[3]
            return v / 10.0  # V
        return None

    def _parse_current(self, resp):
        # Risposta: [0xA1, addr, c_hi, c_lo, ..., crc]
        if resp and len(resp) >= 7:
            c = (resp[2] << 8) | resp[3]
            return c / 100.0  # A
        return None

    def _parse_power(self, resp):
        # Risposta: [0xA2, addr, p_hi, p_lo, ..., crc]
        if resp and len(resp) >= 7:
            p = (resp[2] << 8) | resp[3]
            return p  # W
        return None

    def _parse_energy(self, resp):
        # Risposta: [0xA3, addr, e_hi, e_lo, ..., crc]
        if resp and len(resp) >= 7:
            e = (resp[2] << 8) | resp[3]
            return e  # Wh
        return None
