import json
import ipaddress

from devices.Device import Device
from devices.DeviceType import DeviceType
from devices.Vendor import Vendor


class DeviceList:
    """
    Klasa do przechowywania inventory naszej sieci
    """

    json_indent = 4

    def __init__(self):
        self.devices: list[Device] = []

    def __repr__(self):
        return json.dumps(self.devices)

    def __str__(self):
        return json.dumps(self.devices, indent=self.json_indent)

    def __len__(self):
        return len(self.devices)

    def sort_devices(self):
        self.devices.sort(key=host_sort_key)

    def add_device(self, device: Device):
        self.devices.append(device)
        self.sort_devices()

    def remove_device(self, host: str):
        self.devices = [d for d in self.devices if d.host != host]
        self.sort_devices()

    def clear(self):
        self.devices: list[Device] = []

    def save_to_file(self, filename: str = "inventory.json"):
        with open(filename, "w") as file:
            json.dump(
                [_device_to_dict(device) for device in self.devices],
                file,
                ensure_ascii=False,
                indent=self.json_indent,
            )

    def load_from_file(self, filename: str = "inventory.json"):
        with open(filename, "r") as file:
            data = json.load(file)
            self.devices = [
                Device(
                    host=d["host"],
                    username=d["username"],
                    password=d["password"],
                    vendor=Vendor[d["vendor"]],
                    device_type=DeviceType[d["device_type"]]
                    if d["device_type"]
                    else None,
                )
                for d in data
            ]


def _device_to_dict(dev: Device) -> dict:
    return {
        "host": dev.host,
        "username": dev.username,
        "password": dev.password,
        "vendor": dev.vendor.name,
        "device_type": dev.device_type.name if dev.device_type else None,
    }


def host_sort_key(device: Device):
    try:
        ip = ipaddress.ip_address(device.host)
        return 1, ip
    except ValueError:
        return 0, device.host.lower()
