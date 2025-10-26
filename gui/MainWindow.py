from PySide6.QtCore import Qt, QSettings
from PySide6.QtWidgets import (
    QMainWindow,
    QHBoxLayout,
    QVBoxLayout,
    QPushButton,
    QWidget,
    QScrollArea,
    QDialog,
    QFileDialog,
    QMessageBox,
)
from gui.AddDeviceDialog import AddDeviceDialog
from devices.DeviceList import DeviceList
from devices.Device import Device
from gui.DeviceDetailWidget import DeviceDetailWidget
from gui.SettingsDialog import SettingsDialog


class MainWindow(QMainWindow):
    def __init__(self, device_list: DeviceList):
        super().__init__()
        self.setWindowTitle("Lista urządzeń")
        self.resize(800, 500)

        self.device_list = device_list

        # === CENTRALNY WIDGET ===
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)

        # === LEWA STRONA: lista hostów + przycisk "+" ===
        left_panel = QVBoxLayout()

        btn_add = QPushButton("➕")
        btn_add.clicked.connect(self.add_device_dialog)
        left_panel.addWidget(btn_add)

        # NOWY PRZYCISK: wyczyść listę
        btn_clear = QPushButton("🗑️")
        btn_clear.clicked.connect(self.clear_device_list)
        left_panel.addWidget(btn_clear)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        content = QWidget()
        self.devices_layout = QVBoxLayout(content)
        self.scroll.setWidget(content)
        left_panel.addWidget(self.scroll)

        main_layout.addLayout(left_panel, 1)

        # === PRAWA STRONA: panel szczegółów ===

        self.detail_box = DeviceDetailWidget()
        main_layout.addWidget(self.detail_box, 2)

        # === MENU BAR ===
        menubar = self.menuBar()

        # Plik
        file_menu = menubar.addMenu("Plik")

        action_scan = file_menu.addAction("Skanuj sieć")
        action_scan.triggered.connect(self.scan_network)

        action_save = file_menu.addAction("Zapisz inventory")
        action_save.triggered.connect(self.save_inventory)

        action_load = file_menu.addAction("Wczytaj inventory")
        action_load.triggered.connect(self.load_inventory)

        # Ustawienia
        settings_action = menubar.addAction("Ustawienia")
        settings_action.triggered.connect(self.open_settings_dialog)

        self.settings = QSettings("WEEiA", "PyNetWizard")
        self.connection_type = self.settings.value("connection_type", "ssh")

        # załaduj początkowe urządzenia
        self.refresh_device_buttons()

    def refresh_device_buttons(self):
        # wyczyść layout
        for i in reversed(range(self.devices_layout.count())):
            widget = self.devices_layout.itemAt(i).widget()
            if widget is not None:
                widget.deleteLater()

        # dodaj przyciski na nowo
        for dev in self.device_list.devices:
            try:
                btn = QPushButton(dev.host)
            except AttributeError:
                print(f"Skipping {dev!r}")
            btn.setStyleSheet("padding: 8px; font-size: 13px;")
            btn.setContextMenuPolicy(Qt.CustomContextMenu)

            # Lewy klik
            btn.clicked.connect(lambda _, d=dev: self.show_device_details(d))

            # Prawy klik
            def open_context_menu(pos, d=dev, b=btn):
                from PySide6.QtWidgets import QMenu

                menu = QMenu()
                remove_action = menu.addAction("Usuń urządzenie 🗑️")
                action = menu.exec_(b.mapToGlobal(pos))
                if action == remove_action:
                    self.remove_device(d.host)

            btn.customContextMenuRequested.connect(open_context_menu)
            self.devices_layout.addWidget(btn)

        self.devices_layout.setAlignment(Qt.AlignTop)

    def add_device_dialog(self):
        dialog = AddDeviceDialog(self)
        if dialog.exec() == QDialog.Accepted:
            new_dev = dialog.get_data()
            if new_dev.host:  # minimalna walidacja
                self.device_list.add_device(new_dev)
                self.refresh_device_buttons()

    def remove_device(self, host: str):
        reply = QMessageBox.question(
            self,
            "Potwierdzenie",
            f"Czy na pewno chcesz usunąć urządzenie „{host}”?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self.device_list.remove_device(host)
            self.refresh_device_buttons()
            self.show_device_details(None)

    def clear_device_list(self):
        reply = QMessageBox.question(
            self,
            "Potwierdzenie",
            "Czy na pewno chcesz wyczyścić listę urządzeń?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self.device_list.clear()
            self.refresh_device_buttons()
            self.show_device_details({})

    def show_device_details(self, device: Device):
        self.detail_box.show_for_device(device)

    def scan_network(self):
        from gui.NetworkScanDialog import NetworkScanDialog
        from gui.ScanResultsDialog import ScanResultsDialog

        # zbierz istniejące hosty z device_list, żeby ich nie pokazywać ponownie
        existing_hosts = [d.host for d in self.device_list.devices]

        dlg = NetworkScanDialog(self, exclude_hosts=existing_hosts)
        if dlg.exec() == QDialog.Accepted:
            results = dlg.get_results()
            if not results:
                return
            res_dialog = ScanResultsDialog(results, self)
            if res_dialog.exec() == QDialog.Accepted:
                new_devices = res_dialog.get_selected_devices()
                for dev in new_devices.devices:
                    # upewnij się, że nie dodajemy duplikatu (double-check)
                    if any(d.host == dev.host for d in self.device_list.devices):
                        continue
                    self.device_list.add_device(dev)
                self.refresh_device_buttons()

    def save_inventory(self):
        filename, _ = QFileDialog.getSaveFileName(
            self, "Zapisz inventory", "inventory.json", "JSON Files (*.json)"
        )
        if filename:
            self.device_list.save_to_file(filename)
            QMessageBox.information(
                self, "Zapisano", f"Inventory zapisane do {filename}"
            )

    def load_inventory(self):
        filename, _ = QFileDialog.getOpenFileName(
            self, "Wczytaj inventory", "", "Pliki JSON (*.json)"
        )
        if filename:
            self.device_list.load_from_file(filename)
            self.refresh_device_buttons()
            QMessageBox.information(
                self, "Wczytano", f"Załadowano inventory z {filename}"
            )

    # --- nowa metoda w MainWindow ---
    def open_settings_dialog(self):
        dialog = SettingsDialog(self, self.connection_type)
        if dialog.exec() == QDialog.Accepted:
            self.connection_type = dialog.get_connection_type()

    def closeEvent(self, event):
        self.settings.setValue("connection_type", self.connection_type)
        super().closeEvent(event)
