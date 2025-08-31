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

    # --- Helpers per DST Europe/Rome ---
    def _weekday(self, y, m, d):
        t = [0, 3, 2, 5, 0, 3, 5, 1, 4, 6, 2, 4]  # Sakamoto
        if m < 3: y -= 1
        return (y + y//4 - y//100 + y//400 + t[m-1] + d) % 7

    def _last_sunday(self, y, month):
        for day in range(31, 27, -1):
            try:
                if self._weekday(y, month, day) == 0:
                    return day
            except:
                continue
        return 31

    def _rome_offset_minutes(self, y, mo, d, hh):
        try:
            mar_last = self._last_sunday(y, 3)
            oct_last = self._last_sunday(y, 10)
            # inizio DST = ultima domenica di marzo, 01:00 UTC
            # fine DST   = ultima domenica di ottobre, 01:00 UTC
            if (mo > 3 and mo < 10) or \
               (mo == 3 and (d > mar_last or (d == mar_last and hh >= 1))) or \
               (mo == 10 and (d < oct_last or (d == oct_last and hh < 1))):
                return 120  # CEST
            return 60       # CET
        except:
            return 60

    def _ts(self):
        try:
            y,mo,d,hh,mm,ss,wd,yday = time.gmtime()  # UTC
            if y >= 2020:
                off = self._rome_offset_minutes(y, mo, d, hh)
                # converti in secondi dall'inizio del giorno UTC
                sec = hh*3600 + mm*60 + ss + off*60
                # normalizza (entro 0..86399)
                sec %= 86400
                lhh = sec // 3600
                lmm = (sec % 3600) // 60
                lss = sec % 60
                return "%04d-%02d-%02d %02d:%02d:%02d" % (y, mo, d, lhh, lmm, lss)
        except:
            pass
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
        if self.echo and level in self.echo_levels:
            try: print(line)
            except: pass
        try:
            with open(self.path, "a") as f:
                f.write(line + "\n")
        except OSError:
            with open(self.path, "w") as f:
                f.write(line + "\n")
        self._rotate_if_needed()

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
