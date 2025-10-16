from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QTableWidget, QTableWidgetItem,
    QDialogButtonBox, QPushButton, QWidget, QHBoxLayout, QComboBox, QLineEdit, QMessageBox, QHeaderView
)
from gui.RawDataDialog import RawDataDialog

DEBUG = False  # ustaw True, jeśli chcesz zobaczyć raw_data

class ScanResultsDialog(QDialog):
    def __init__(self, results: list[dict], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Wyniki skanowania")
        self.resize(900, 480)
        self.results = results

        layout = QVBoxLayout(self)

        # kolumny: Host, Vendor, Typ, Użytkownik, Hasło, RawData (opcjonalnie)
        cols = ["Host", "Vendor", "Typ", "Użytkownik", "Hasło"]
        if DEBUG:
            cols.append("Surowe dane")
        self.table = QTableWidget(len(results), len(cols))
        self.table.setHorizontalHeaderLabels(cols)

        # --- ustawienia skalowania ---
        header = self.table.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(QHeaderView.Interactive)
        self.table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.setMinimumWidth(600)
        self.table.setMinimumHeight(300)

        for row, dev in enumerate(results):
            host = dev.get("host", "")
            vendor = dev.get("vendor", "")
            dtype = dev.get("device_type", "")
            raw = dev.get("raw_info", {})

            item_host = QTableWidgetItem(host)
            item_host.setFlags(item_host.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(row, 0, item_host)

            combo = QComboBox()
            combo.addItems(["Cisco", "Juniper"])
            if vendor in ("Cisco", "Juniper"):
                combo.setCurrentText(vendor)
            self.table.setCellWidget(row, 1, combo)

            item_type = QTableWidgetItem(dtype or "-")
            item_type.setFlags(item_type.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(row, 2, item_type)

            user_edit = QLineEdit()
            self.table.setCellWidget(row, 3, user_edit)
            pass_edit = QLineEdit()
            pass_edit.setEchoMode(QLineEdit.Password)
            self.table.setCellWidget(row, 4, pass_edit)

            if DEBUG:
                btn = QPushButton("Pokaż")
                btn.raw_info = raw
                btn.clicked.connect(self._make_show_raw_handler(btn))
                container_btn = QWidget()
                box_btn = QHBoxLayout(container_btn)
                box_btn.setContentsMargins(0, 0, 0, 0)
                box_btn.addWidget(btn)
                container_btn.setLayout(box_btn)
                self.table.setCellWidget(row, 5, container_btn)

        layout.addWidget(self.table)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.validate_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _make_show_raw_handler(self, btn):
        @Slot()
        def handler():
            dlg = RawDataDialog(getattr(btn, "raw_info", {}), self)
            dlg.exec()
        return handler

    def validate_and_accept(self):
        for row in range(self.table.rowCount()):
            user_edit = self.table.cellWidget(row, 3)
            pass_edit = self.table.cellWidget(row, 4)
            if not user_edit.text().strip() or not pass_edit.text().strip():
                QMessageBox.warning(
                    self, "Błąd",
                    f"Wszystkie pola użytkownik i hasło muszą być wypełnione (host: {self.table.item(row,0).text()})"
                )
                return
        self.accept()

    def get_selected_devices(self):
        devices = []
        for row in range(self.table.rowCount()):
            host_item = self.table.item(row, 0)
            host = host_item.text() if host_item else ""
            combo_widget = self.table.cellWidget(row, 1)
            vendor_str = ""
            if combo_widget:
                combo = combo_widget
                vendor_str = combo.currentText().strip().lower()
            dtype = "cisco" if "cisco" in vendor_str else "juniper"
            user = self.table.cellWidget(row, 3).text() if self.table.cellWidget(row, 3) else ""
            password = self.table.cellWidget(row, 4).text() if self.table.cellWidget(row, 4) else ""
            devices.append({
                "host": host,
                "username": user,
                "password": password,
                "device_type": dtype,
            })
        return devices
