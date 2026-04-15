# network_scanner.py
from PySide6.QtCore import QObject, Signal
from pathlib import Path
import time
import xml.etree.ElementTree as ET


def get_local_ipv4s():
    """Zwraca set lokalnych IPv4, żeby je potem pominąć."""
    local_ips = set()
    try:
        import psutil

        for addrs in psutil.net_if_addrs().values():
            for a in addrs:
                fam = getattr(a, "family", None)
                if str(fam).lower().endswith("inet") or fam == 2:
                    if getattr(a, "address", None):
                        local_ips.add(a.address)
    except Exception:
        try:
            import socket

            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ips.add(s.getsockname()[0])
            s.close()
        except Exception:
            pass
    local_ips.add("127.0.0.1")
    return local_ips


class NetworkScanner(QObject):
    progress = Signal(int, int)
    finished = Signal(list)
    error = Signal(str)

    def __init__(
        self,
        subnet: str,
        detailed: bool = False,
        exclude_hosts: list[str] | None = None,
    ):
        super().__init__()
        self.subnet = subnet
        self.detailed = detailed
        self._abort = False
        self.exclude_hosts = set(exclude_hosts or [])

    def stop(self):
        self._abort = True
        try:
            if (
                hasattr(self, "process")
                and self.process
                and self.process.poll() is None
            ):
                self.process.terminate()
        except Exception:
            pass

    def run(self):
        try:
            results = []
            args = "-sV -O -Pn" if self.detailed else "-sn"

            # Użyjemy nmap w trybie JSON, żeby łatwo sparsować wynik
            # python-nmap nie obsłuży przerwania, ale subprocess – tak.
            import subprocess
            import tempfile

            with tempfile.NamedTemporaryFile(delete=False) as tmpfile:
                out_path = tmpfile.name

            cmd = ["nmap", "-oX", out_path] + args.split() + [self.subnet]

            # Uruchom nmap jako proces
            proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )
            self.process = proc  # zapamiętujemy dla stop()

            # Polling – sprawdzamy co 100 ms
            while proc.poll() is None:
                if self._abort:
                    proc.terminate()
                    proc.wait()
                    self.finished.emit([])  # nie parsujemy XML
                    return
                time.sleep(0.1)

            # Jeśli proces został zakończony z błędem albo XML nie istnieje → nie parsujemy
            if self._abort:
                # safety — nie powinno tu wejść, ale utrzymujemy
                self.finished.emit([])
                return

            # Jeśli plik jest pusty — nie parsujemy
            if Path(out_path).stat().st_size < 20:
                self.finished.emit([])  # 20 bajtów to minimalny poprawny XML
                return

            # Proces zakończony – parsujemy wynik
            tree = ET.parse(out_path)
            root = tree.getroot()

            hosts = [elem for elem in root.findall("host")]
            total = len(hosts)
            local_ips = get_local_ipv4s()

            for i, h in enumerate(hosts):
                if self._abort:
                    break

                self.progress.emit(i + 1, total)

                addr = h.find("address")
                host_ip = addr.get("addr") if addr is not None else None
                if not host_ip:
                    continue

                if host_ip in local_ips or host_ip in self.exclude_hosts:
                    continue

                mac_elem = h.find('address[@addrtype="mac"]')
                mac = mac_elem.get("addr") if mac_elem is not None else ""

                vendor = ""
                device_type = ""

                # Parser OS (jeśli detailed)
                os_elem = h.find("os")
                osclasses = []
                if os_elem is not None:
                    for oc in os_elem.findall("osclass"):
                        osclasses.append(oc.attrib)

                for oc in osclasses:
                    v = oc.get("vendor", "").lower()
                    if v in ("cisco", "juniper"):
                        vendor = v
                        break

                for oc in osclasses:
                    t = oc.get("type", "").lower()
                    if t in ("router", "switch", "wap"):
                        device_type = t
                        break

                results.append(
                    {
                        "host": host_ip,
                        "mac": mac or "",
                        "vendor": vendor or "",
                        "device_type": device_type or "",
                        "raw_info": {},  # XML i tak już sparsowany
                    }
                )

            self.finished.emit(results)

        except Exception as e:
            self.error.emit(f"{type(e).__name__}: {str(e)}")
