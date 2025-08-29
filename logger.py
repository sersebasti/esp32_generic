import os, time

class RollingLogger:
    def __init__(self, path="log.txt", max_bytes=2*1024, backups=1,
                 echo=True, echo_levels=("E","W","I")):
        self.path = path
        self.max_bytes = max_bytes
        self.backup = path + ".1" if backups >= 1 else None
        self.echo = echo
        self.echo_levels = set(echo_levels)

    def _size(self, p):
        try: return os.stat(p)[6]
        except OSError: return 0

    def _ts(self):
        try:
            y,mo,d,hh,mm,ss,_,_ = time.localtime()
            if y >= 2020:
                return "%04d-%02d-%02d %02d:%02d:%02d" % (y,mo,d,hh,mm,ss)
        except: pass
        return "t+%dms" % time.ticks_ms()

    def _rotate_if_needed(self):
        if self._size(self.path) <= self.max_bytes:
            return
        if self.backup:
            try: os.remove(self.backup)
            except OSError: pass
            try: os.rename(self.path, self.backup)
            except OSError:
                try: open(self.path, "w").close()
                except OSError: pass
        else:
            try:
                with open(self.path, "rb") as f:
                    f.seek(-self.max_bytes//2, 2)
                    tail = f.read()
                with open(self.path, "wb") as f:
                    f.write(tail)
            except OSError:
                try: open(self.path, "w").close()
                except OSError: pass

    def log(self, msg, level="I"):
        line = "[%s] %s %s" % (self._ts(), level, msg)
        # stampa anche a console, se richiesto
        if self.echo and level in self.echo_levels:
            try:
                print(line)
            except Exception:
                pass
        # scrive su file
        try:
            with open(self.path, "a") as f:
                f.write(line + "\n")
        except OSError:
            with open(self.path, "w") as f:
                f.write(line + "\n")
        self._rotate_if_needed()

    # comodi alias
    def info(self, msg): self.log(msg, "I")
    def warn(self, msg): self.log(msg, "W")
    def error(self, msg): self.log(msg, "E")

    def tail(self, lines=50, max_bytes=2048):
        blobs = []
        for p in (self.backup, self.path) if self.backup else (self.path,):
            if not p: continue
            try:
                with open(p, "rb") as f:
                    f.seek(0, 2)
                    size = f.tell()
                    rd = min(size, max_bytes)
                    f.seek(-rd, 1)
                    blobs.append(f.read())
            except OSError:
                pass
        txt = b"".join(blobs).decode("utf-8", "ignore").splitlines()
        return "\n".join(txt[-lines:])
