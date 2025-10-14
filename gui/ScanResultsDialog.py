# gui/ScanResultsDialog.py
from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QTableWidget, QTableWidgetItem,
    QDialogButtonBox, QPushButton, QWidget, QHBoxLayout, QComboBox
)
from gui.RawDataDialog import RawDataDialog

class ScanResultsDialog(QDialog):
    def __init__(self, results: list[dict], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Wyniki skanowania")
        self.resize(900, 480)

        layout = QVBoxLayout(self)
        cols = ["Host", "MAC", "Vendor", "Typ", "Użytkownik", "Hasło", "Surowe dane"]
        self.table = QTableWidget(len(results), len(cols))
        self.table.setHorizontalHeaderLabels(cols)

        for row, dev in enumerate(results):
            host = dev.get("host", "")
            mac = dev.get("mac", "")
            vendor = dev.get("vendor", "")
            dtype = dev.get("device_type", "")
            raw = dev.get("raw_info", {})

            item_host = QTableWidgetItem(host)
            item_host.setFlags(item_host.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(row, 0, item_host)

            item_mac = QTableWidgetItem(mac or "-")
            item_mac.setFlags(item_mac.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(row, 1, item_mac)

            combo = QComboBox()
            options = ["Cisco", "Juniper"]
            combo.addItems(options)
            combo.setEditable(False)
            if vendor in options:
                combo.setCurrentText(vendor)
            else:
                combo.setCurrentIndex(-1)
            container = QWidget()
            box = QHBoxLayout(container)
            box.setContentsMargins(0, 0, 0, 0)
            box.addWidget(combo)
            container.setLayout(box)
            self.table.setCellWidget(row, 2, container)

            item_type = QTableWidgetItem(dtype or "-")
            item_type.setFlags(item_type.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(row, 3, item_type)

            item_user = QTableWidgetItem("")
            self.table.setItem(row, 4, item_user)
            item_pass = QTableWidgetItem("")
            self.table.setItem(row, 5, item_pass)

            btn = QPushButton("Pokaż")
            btn.raw_info = raw
            btn.clicked.connect(self._make_show_raw_handler(btn))
            container_btn = QWidget()
            box_btn = QHBoxLayout(container_btn)
            box_btn.setContentsMargins(0, 0, 0, 0)
            box_btn.addWidget(btn)
            container_btn.setLayout(box_btn)
            self.table.setCellWidget(row, 6, container_btn)

        self.table.resizeColumnsToContents()
        layout.addWidget(self.table)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _make_show_raw_handler(self, btn):
        @Slot()
        def handler():
            dlg = RawDataDialog(getattr(btn, "raw_info", {}), self)
            dlg.exec()
        return handler

    def get_selected_devices(self):
        devices = []
        for row in range(self.table.rowCount()):
            host_item = self.table.item(row, 0)
            if not host_item:
                continue
            host = host_item.text().strip()
            widget = self.table.cellWidget(row, 2)
            vendor_str = ""
            if widget:
                combo = widget.layout().itemAt(0).widget()
                if combo:
                    vendor_str = combo.currentText().strip().lower()
            if "cisco" in vendor_str:
                dtype = "cisco"
            elif "juniper" in vendor_str:
                dtype = "juniper"
            else:
                continue

            username = self.table.item(row, 4).text() if self.table.item(row, 4) else ""
            password = self.table.item(row, 5).text() if self.table.item(row, 5) else ""
            devices.append({
                "host": host,
                "username": username,
                "password": password,
                "device_type": dtype,
            })
        return devices
