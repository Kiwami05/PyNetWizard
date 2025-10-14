# network_scanner.py
from PySide6.QtCore import QObject, Signal
import nmap
import time
import json
import os

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

    def __init__(self, subnet: str, detailed: bool = False, exclude_hosts: list[str] | None = None):
        super().__init__()
        self.subnet = subnet
        self.detailed = detailed
        self._abort = False
        self.exclude_hosts = set(exclude_hosts or [])

    def stop(self):
        self._abort = True

    def run(self):
        scanner = nmap.PortScanner()
        results = []
        try:
            args = "-sV -O -Pn" if self.detailed else "-sn"
            scanner.scan(hosts=self.subnet, arguments=args)
            hosts = scanner.all_hosts()
            total = len(hosts)
            local_ips = get_local_ipv4s()

            for i, host in enumerate(hosts):
                if self._abort:
                    break
                self.progress.emit(i + 1, total)

                if host in local_ips or host in self.exclude_hosts:
                    continue

                try:
                    info = scanner[host]
                except Exception:
                    info = {}

                mac = info.get("addresses", {}).get("mac", "") if isinstance(info, dict) else ""
                vendor = ""
                device_type = ""

                # Typ urządzenia i vendor z osmatch/osclass
                osmatch = info.get("osmatch") or []
                osclasses = []
                for om in osmatch:
                    if "osclass" in om and isinstance(om["osclass"], list):
                        osclasses.extend(om["osclass"])

                # vendor: tylko Cisco / Juniper
                for oc in osclasses:
                    v = oc.get("vendor", "").strip()
                    if v.lower() in ("cisco", "juniper"):
                        vendor = v
                        break

                # typ urządzenia: router/switch/WAP
                for oc in osclasses:
                    t = oc.get("type", "").lower()
                    if t in ("router", "switch", "wap"):
                        device_type = t
                        break

                # prepare raw_info
                try:
                    raw_info_jsonable = json.loads(json.dumps(info))
                except Exception:
                    raw_info_jsonable = str(info)

                results.append({
                    "host": host,
                    "mac": mac or "",
                    "vendor": vendor or "",
                    "device_type": device_type or "",
                    "raw_info": raw_info_jsonable,
                })
                time.sleep(0.01)

            self.finished.emit(results)
        except Exception as e:
            self.error.emit(f"{type(e).__name__}: {str(e)}")
