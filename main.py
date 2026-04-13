import sys

from PySide6.QtWidgets import QApplication

from devices.device_list import DeviceList
from gui.main_window import MainWindow

if __name__ == "__main__":
    app = QApplication(sys.argv)

    devices = DeviceList()

    window = MainWindow(devices)
    window.show()

    sys.exit(app.exec())
