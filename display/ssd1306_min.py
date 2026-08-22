from machine import I2C
import framebuf


class _SSD1306:
    def __init__(self, width, height, i2c: I2C, addr=0x3C):
        self.width = width
        self.height = height
        self.i2c = i2c
        self.addr = addr
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
        # Sequenza di init robusta per SSD1306 (supporta 128x32 e 128x64).
        self._write_cmd(0xAE)  # display off
        self._write_cmd(0x20)
        self._write_cmd(0x00)  # horizontal addressing mode
        self._write_cmd(0x40)  # start line
        self._write_cmd(0xA1)  # segment remap
        self._write_cmd(0xA8)
        self._write_cmd(self.height - 1)  # multiplex ratio
        self._write_cmd(0xC8)  # COM scan direction remapped
        self._write_cmd(0xD3)
        self._write_cmd(0x00)  # display offset
        self._write_cmd(0xDA)
        self._write_cmd(0x02 if self.height == 32 else 0x12)  # COM pins config
        self._write_cmd(0xD5)
        self._write_cmd(0x80)  # display clock divide ratio/osc freq
        self._write_cmd(0xD9)
        self._write_cmd(0xF1)  # pre-charge period
        self._write_cmd(0xDB)
        self._write_cmd(0x30)  # VCOMH deselect level
        self._write_cmd(0x81)
        self._write_cmd(0xCF)  # contrast
        self._write_cmd(0xA4)  # entire display ON follows RAM
        self._write_cmd(0xA6)  # normal display (not inverted)
        self._write_cmd(0x8D)
        self._write_cmd(0x14)  # charge pump enable
        self._write_cmd(0xAF)  # display on

    def fill(self, color):
        self.fb.fill(color)

    def text(self, text, x, y, color=1):
        self.fb.text(text, x, y, color)

    def show(self):
        self._write_cmd(0x21)
        self._write_cmd(0)
        self._write_cmd(self.width - 1)
        self._write_cmd(0x22)
        self._write_cmd(0)
        self._write_cmd(self.pages - 1)
        self._write_data(self.buffer)


class SSD1306DisplayAdapter:
    # Adapter compatibile con l'interfaccia usata dall'app: clear() e write(row, col, text)
    def __init__(self, i2c: I2C, addr=0x3C, width=128, height=64):
        self.oled = _SSD1306(width=width, height=height, i2c=i2c, addr=addr)

    def clear(self):
        self.oled.fill(0)
        self.oled.show()

    def write(self, row, col, text):
        x = int(col) * 8
        y = int(row) * 10
        self.oled.text(str(text), x, y, 1)
        self.oled.show()
