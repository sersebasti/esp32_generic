from machine import I2C
import framebuf


class _SH1106:
    def __init__(self, width, height, i2c: I2C, addr=0x3C, col_offset=2):
        self.width = width
        self.height = height
        self.i2c = i2c
        self.addr = addr
        self.col_offset = int(col_offset) & 0x0F
        self.pages = self.height // 8
        self.buffer = bytearray(self.pages * self.width)
        self.fb = framebuf.FrameBuffer(self.buffer, self.width, self.height, framebuf.MONO_VLSB)
        self._init_display()
        self.fill(0)
        self.show()

    def _write_cmd(self, cmd):
        self.i2c.writeto(self.addr, bytes((0x80, cmd)))

    def _write_data(self, buf):
        self.i2c.writeto(self.addr, b"\x40" + buf)

    def _init_display(self):
        self._write_cmd(0xAE)  # display off
        self._write_cmd(0xD5)
        self._write_cmd(0x80)
        self._write_cmd(0xA8)
        self._write_cmd(self.height - 1)
        self._write_cmd(0xD3)
        self._write_cmd(0x00)
        self._write_cmd(0x40)
        self._write_cmd(0xAD)
        self._write_cmd(0x8B)  # DC-DC on
        self._write_cmd(0xA1)
        self._write_cmd(0xC8)
        self._write_cmd(0xDA)
        self._write_cmd(0x12 if self.height == 64 else 0x02)
        self._write_cmd(0x81)
        self._write_cmd(0xCF)
        self._write_cmd(0xD9)
        self._write_cmd(0x22)
        self._write_cmd(0xDB)
        self._write_cmd(0x35)
        self._write_cmd(0xA4)
        self._write_cmd(0xA6)
        self._write_cmd(0xAF)  # display on

    def fill(self, color):
        self.fb.fill(color)

    def text(self, text, x, y, color=1):
        self.fb.text(text, x, y, color)

    def show(self):
        # SH1106 usa addressing per pagina con offset colonne variabile per modulo.
        low = self.col_offset & 0x0F
        high = 0x10 | ((self.col_offset >> 4) & 0x0F)
        for page in range(self.pages):
            self._write_cmd(0xB0 + page)
            self._write_cmd(low)
            self._write_cmd(high)
            start = self.width * page
            end = start + self.width
            self._write_data(self.buffer[start:end])


class SH1106DisplayAdapter:
    # Adapter compatibile con l'interfaccia usata dall'app: clear() e write(row, col, text)
    def __init__(self, i2c: I2C, addr=0x3C, width=128, height=64, col_offset=2):
        self.oled = _SH1106(width=width, height=height, i2c=i2c, addr=addr, col_offset=col_offset)

    def clear(self):
        self.oled.fill(0)
        self.oled.show()

    def write(self, row, col, text):
        x = int(col) * 8
        y = int(row) * 10
        self.oled.text(str(text), x, y, 1)
        self.oled.show()
