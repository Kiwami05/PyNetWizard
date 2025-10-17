from devices.DeviceType import DeviceType
from devices.Vendor import Vendor


class Device:
    def __init__(
        self,
        host: str,
        username: str,
        password: str,
        vendor: Vendor,
        device_type: DeviceType = None,
    ):
        self.host = host
        self.username = username
        self.password = password
        self.vendor = vendor
        self.device_type = device_type

    def __repr__(self):
        return f"Device({self.host}, {self.username}, {self.password}, {self.vendor}), device_type={self.device_type}"

    def __str__(self):
        return f"Host: {self.host}, Username: {self.username}, Password: {self.password}, Vendor: {self.vendor}, Device Type: {self.device_type}"
