import os, time

class CircularLogger:
    def __init__(self, path="log.txt", max_bytes=2048,
                 echo=True, echo_levels=("E","W","I")):
        self.path = path
        self.max_bytes = max_bytes
        self.echo = echo
        self.echo_levels = set(echo_levels)
        self._pos = 0

        # Prepara file se non esiste
        try:
            if not self._size(path):
                with open(path, "wb") as f:
                    f.write(b"\0" * max_bytes)  # file pre-allocato
        except OSError:
            pass

    def _size(self, p):
        try: return os.stat(p)[6]
        except OSError: return 0

    def _ts(self):
        try:
            y,mo,d,hh,mm,ss,_,_ = time.gmtime()
            return "%04d-%02d-%02d %02d:%02d:%02d" % (y, mo, d, hh, mm, ss)
        except:
            return "t+%dms" % time.ticks_ms()

    def log(self, msg, level="I"):
        line = "[%s] %s %s\n" % (self._ts(), level, msg)
        data = line.encode()

        if self.echo and level in self.echo_levels:
            try: print(line.strip())
            except: pass

        # Scrivi in modalità circolare
        try:
            with open(self.path, "r+b") as f:
                f.seek(self._pos)
                f.write(data)
                self._pos += len(data)
                if self._pos >= self.max_bytes:
                    self._pos = 0
        except OSError:
            pass

    def info(self, msg): self.log(msg, "I")
    def warn(self, msg): self.log(msg, "W")
    def error(self, msg): self.log(msg, "E")

    def tail(self, max_bytes=1024):
        try:
            with open(self.path, "rb") as f:
                f.seek(0, 2)
                size = f.tell()
                rd = min(size, max_bytes)
                f.seek(-rd, 1)
                data = f.read()
            return data.decode("utf-8", "ignore").splitlines()[-50:]
        except OSError:
            return []

