import sys

from PySide6.QtWidgets import QApplication

from DeviceList import DeviceList
from gui.MainWindow import MainWindow

if __name__ == "__main__":
    app = QApplication(sys.argv)

    # Na sztywno dodajemy kilka urządzeń
    devices = DeviceList()
    # devices.add_device("192.168.1.1", "admin", "pass123", "cisco")
    # devices.add_device("192.168.1.2", "user", "secret", "juniper")

    window = MainWindow(devices)
    window.show()

    sys.exit(app.exec())
