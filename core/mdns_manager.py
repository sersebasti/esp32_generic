import _thread
import socket
import struct
import time


_MDNS_ADDR = "224.0.0.251"
_MDNS_PORT = 5353
_TYPE_A = 1
_TYPE_PTR = 12
_TYPE_TXT = 16
_TYPE_SRV = 33


def _dns_name(name):
    encoded = bytearray()
    for label in name.rstrip(".").split("."):
        label_bytes = label.encode()
        if not 0 < len(label_bytes) < 64:
            raise ValueError("invalid DNS label")
        encoded.append(len(label_bytes))
        encoded.extend(label_bytes)
    encoded.append(0)
    return bytes(encoded)


def _normalise_hostname(hostname):
    allowed = "abcdefghijklmnopqrstuvwxyz0123456789"
    value = "".join(char.lower() if char.lower() in allowed else "-" for char in str(hostname))
    value = value.strip("-")[:63]
    if not value:
        raise ValueError("mDNS hostname is empty")
    return value


def _read_name(packet, offset):
    labels = []
    while offset < len(packet):
        length = packet[offset]
        offset += 1
        if length == 0:
            return ".".join(labels).lower(), offset
        if length & 0xc0:
            return None, offset + 1
        if offset + length > len(packet):
            return None, offset
        labels.append(packet[offset:offset + length].decode("utf-8", "ignore"))
        offset += length
    return None, offset


class MDNSManager:
    def __init__(self, hostname, http_port=80, log=None):
        self.hostname = _normalise_hostname(hostname)
        self.http_port = int(http_port)
        self.log = log
        self.socket = None
        self.running = False

    @property
    def host_name(self):
        return self.hostname + ".local"

    @property
    def service_name(self):
        return "_http._tcp.local"

    @property
    def instance_name(self):
        return self.hostname + "._http._tcp.local"

    def _log(self, message, *args):
        try:
            if self.log:
                self.log.info(message, *args)
            else:
                print(message % args if args else message)
        except Exception:
            pass

    def _ip_address(self):
        try:
            import network
            sta = network.WLAN(network.STA_IF)
            if sta.isconnected():
                return sta.ifconfig()[0]
        except Exception:
            pass
        return None

    def _records(self):
        ip = self._ip_address()
        if not ip:
            return []
        host = _dns_name(self.host_name)
        service = _dns_name(self.service_name)
        instance = _dns_name(self.instance_name)
        ttl = struct.pack("!I", 120)
        return [
            (host, _TYPE_A, struct.pack("!H", _TYPE_A) + struct.pack("!H", 0x8001) + ttl + struct.pack("!H", 4) + socket.inet_aton(ip)),
            (service, _TYPE_PTR, struct.pack("!H", _TYPE_PTR) + struct.pack("!H", 0x8001) + ttl + struct.pack("!H", len(instance)) + instance),
            (instance, _TYPE_SRV, struct.pack("!H", _TYPE_SRV) + struct.pack("!H", 0x8001) + ttl + struct.pack("!H", 6 + len(host)) + struct.pack("!HHH", 0, 0, self.http_port) + host),
            (instance, _TYPE_TXT, struct.pack("!H", _TYPE_TXT) + struct.pack("!H", 0x8001) + ttl + struct.pack("!H", 1) + b"\x00"),
        ]

    def _response(self, records):
        body = b"".join(name + record for name, _, record in records)
        return struct.pack("!HHHHHH", 0, 0x8400, 0, len(records), 0, 0) + body

    def announce(self):
        records = self._records()
        if records and self.socket:
            self.socket.sendto(self._response(records), (_MDNS_ADDR, _MDNS_PORT))

    def _answer_query(self, packet):
        if len(packet) < 12:
            return None
        _, flags, question_count, _, _, _ = struct.unpack("!HHHHHH", packet[:12])
        if flags & 0x8000:
            return None
        wanted = set()
        offset = 12
        for _ in range(question_count):
            name, offset = _read_name(packet, offset)
            if name is None or offset + 4 > len(packet):
                return None
            question_type, _ = struct.unpack("!HH", packet[offset:offset + 4])
            offset += 4
            wanted.add((name, question_type))
        selected = []
        for name, record_type, record in self._records():
            plain_name, _ = _read_name(name, 0)
            if (plain_name, record_type) in wanted or (plain_name, 255) in wanted:
                selected.append((name, record_type, record))
        return self._response(selected) if selected else None

    def _run(self):
        while self.running:
            try:
                packet, _ = self.socket.recvfrom(512)
                response = self._answer_query(packet)
                if response:
                    self.socket.sendto(response, (_MDNS_ADDR, _MDNS_PORT))
            except OSError:
                pass
            except Exception as error:
                self._log("mDNS error: %r", error)

    def start(self):
        if self.running:
            return True
        ip = self._ip_address()
        if not ip:
            self._log("mDNS non avviato: Wi-Fi non connesso")
            return False
        self.running = True
        self._log("mDNS attivo: http://%s" % self.host_name)
        return True

    def stop(self):
        self.running = False
        if self.socket:
            try:
                self.socket.close()
            except Exception:
                pass
        self.socket = None