# network_scanner.py
from PySide6.QtCore import QObject, Signal
from pathlib import Path
import time
import xml.etree.ElementTree as ET

from platforms.device_type import DeviceType
from platforms.vendor import Vendor


def get_local_ipv4s():
    """Zwraca zbiór lokalnych IPv4, żeby je potem pominąć."""
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
        os_detection: bool = False,
        exclude_hosts: list[str] | None = None,
    ):
        super().__init__()
        self.subnet = subnet
        self.detailed = detailed
        self.os_detection = os_detection
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
            args = ["-sV", "-Pn"] if self.detailed else ["-sn"]
            if self.detailed and self.os_detection:
                args.append("-O")

            import subprocess
            import tempfile

            with tempfile.NamedTemporaryFile(delete=False) as tmpfile:
                out_path = tmpfile.name

            cmd = ["nmap", "-oX", out_path] + args + [self.subnet]

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
                mac_vendor = mac_elem.get("vendor", "") if mac_elem is not None else ""

                vendor = ""
                device_type = ""

                # Parser OS (jeśli detailed)
                os_elem = h.find("os")
                osclasses = []
                if os_elem is not None:
                    for oc in os_elem.findall(".//osclass"):
                        osclasses.append(oc.attrib)

                for oc in osclasses:
                    vendor = _normalize_vendor(oc.get("vendor", ""))
                    if vendor:
                        break

                for oc in osclasses:
                    device_type = _normalize_device_type(oc.get("type", ""))
                    if device_type:
                        break

                for service in h.findall(".//service"):
                    text = " ".join(
                        service.get(attr, "")
                        for attr in ("name", "product", "version", "extrainfo")
                    )
                    if not vendor:
                        vendor = _normalize_vendor(text)
                    if not device_type:
                        device_type = _normalize_device_type(text)
                    if vendor and device_type:
                        break

                if not vendor:
                    vendor = _normalize_vendor(mac_vendor)

                results.append(
                    {
                        "host": host_ip,
                        "mac": mac or "",
                        "vendor": vendor or "",
                        "device_type": device_type or "",
                        "raw_info": {
                            "mac_vendor": mac_vendor,
                            "osclasses": osclasses,
                            "services": [
                                service.attrib for service in h.findall(".//service")
                            ],
                        },
                    }
                )

            self.finished.emit(results)

        except Exception as e:
            self.error.emit(f"{type(e).__name__}: {str(e)}")


def _normalize_vendor(value: str) -> str:
    text = (value or "").lower()
    if "cisco" in text:
        return Vendor.CISCO.name.lower()
    if "juniper" in text:
        return Vendor.JUNIPER.name.lower()
    return ""


def _normalize_device_type(value: str) -> str:
    text = (value or "").lower()
    if "firewall" in text or "adaptive security appliance" in text or " asa" in text:
        return DeviceType.FIREWALL.name.lower()
    if "switch" in text or "ethernet switch" in text or "wap" in text:
        return DeviceType.SWITCH.name.lower()
    if "router" in text or "ios router" in text or "junos router" in text:
        return DeviceType.ROUTER.name.lower()
    return ""
