import sys

from PySide6.QtWidgets import QApplication

from devices.DeviceList import DeviceList
from gui.MainWindow import MainWindow

if __name__ == "__main__":
    app = QApplication(sys.argv)

    devices = DeviceList()

    window = MainWindow(devices)
    window.show()

    sys.exit(app.exec())
