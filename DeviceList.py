import json


class DeviceList:
    """
    Klasa do przechowywania inventory naszej sieci
    """

    json_indent = 4

    def __init__(self):
        self.devices: list[dict] = []

    def __repr__(self):
        return json.dumps(self.devices)

    def __str__(self):
        return json.dumps(self.devices, indent=self.json_indent)

    def __len__(self):
        return len(self.devices)

    def add_device(self, host: str, username: str, password: str, device_type: str):
        item = {
            "host": host,
            "username": username,
            "password": password,
            "device_type": device_type,
        }
        self.devices.append(item)
        pass

    def remove_device(self, host: str):
        self.devices = [d for d in self.devices if d["host"] != host]

    def clear(self):
        self.devices: list[dict] = []

    def save_to_file(self, filename: str = "inventory.json"):
        with open(filename, "w") as file:
            json.dump(self.devices, file, ensure_ascii=False, indent=self.json_indent)

    def load_from_file(self, filename: str = "inventory.json"):
        with open(filename, "r") as file:
            self.devices = json.load(file)
