from PySide6.QtCore import Qt, QSettings, QTimer, QTime
from PySide6.QtWidgets import (
    QMainWindow,
    QHBoxLayout,
    QVBoxLayout,
    QPushButton,
    QWidget,
    QScrollArea,
    QLabel,
    QDialog,
    QFileDialog,
    QMessageBox,
    QStatusBar,
)
from gui.AddDeviceDialog import AddDeviceDialog
from devices.DeviceList import DeviceList
from devices.Device import Device
from gui.SettingsDialog import SettingsDialog
from gui.DeviceDetailWidget import DeviceDetailWidget


# --- MOCK ConnectionManager ---
class MockConnectionManager:
    """Tymczasowa atrapa menedżera połączeń (bez Netmiko)."""

    def __init__(self):
        self.status = {}  # {host: "connected"/"disconnected"/"error"}

    def toggle_status(self, host):
        """Losowo przełącza status połączenia (do testów GUI)."""
        current = self.status.get(host, "disconnected")
        new = "connected" if current != "connected" else "disconnected"
        self.status[host] = new

    def is_alive(self, device):
        return self.status.get(device.host, "disconnected") == "connected"

    def get_status(self, device):
        return self.status.get(device.host, "disconnected")


class MainWindow(QMainWindow):
    def __init__(self, device_list: DeviceList):
        super().__init__()
        self.setWindowTitle("PyNetWizard — Network Configurator")
        self.resize(900, 550)

        self.device_list = device_list
        self.current_device = None

        # --- NOWE: mock ConnectionManager ---
        self.connection_manager = MockConnectionManager()

        # === CENTRALNY WIDGET ===
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)

        # === LEWY PANEL: lista hostów + przyciski ===
        left_panel = QVBoxLayout()

        btn_add = QPushButton("➕")
        btn_add.clicked.connect(self.add_device_dialog)
        left_panel.addWidget(btn_add)

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

        # === PRAWY PANEL: detail box (taby) ===
        self.detail_box = DeviceDetailWidget()
        main_layout.addWidget(self.detail_box, 2)

        # === MENU BAR ===
        menubar = self.menuBar()
        file_menu = menubar.addMenu("Plik")

        action_scan = file_menu.addAction("Skanuj sieć")
        action_scan.triggered.connect(self.scan_network)

        action_save = file_menu.addAction("Zapisz inventory")
        action_save.triggered.connect(self.save_inventory)

        action_load = file_menu.addAction("Wczytaj inventory")
        action_load.triggered.connect(self.load_inventory)

        device_menu = menubar.addMenu("Urządzenie")

        action_apply_current = device_menu.addAction("Zatwierdź konfigurację (bieżące urządzenie)")
        action_apply_current.triggered.connect(self.apply_current_device)

        action_apply_all = device_menu.addAction("Zatwierdź konfigurację (wszystkie urządzenia)")
        action_apply_all.triggered.connect(self.apply_all_devices)

        device_menu.addSeparator()

        action_sync = device_menu.addAction("Odśwież konfigurację (Sync)")
        action_sync.triggered.connect(self.sync_current_device)

        action_reset = device_menu.addAction("Resetuj zmiany (mock)")
        action_reset.triggered.connect(self.reset_current_device)

        settings_action = menubar.addAction("Ustawienia")
        settings_action.triggered.connect(self.open_settings_dialog)

        # --- NOWE: status bar ---
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_label = QLabel("Ready.")
        self.status_label.setStyleSheet("font-family: monospace;")
        self.status_bar.addPermanentWidget(self.status_label)

        # --- NOWE: zegar i timer odświeżania ---
        self.last_check_time = QTime.currentTime()
        self.status_timer = QTimer(self)
        self.status_timer.timeout.connect(self.update_status_bar)
        self.status_timer.start(4000)  # co 4 sekundy

        # --- ustawienia ---
        self.settings = QSettings("WEEiA", "PyNetWizard")
        self.connection_type = self.settings.value("connection_type", "ssh")

        # --- inicjalne urządzenia ---
        self.refresh_device_buttons()

    # === METODY GUI ===

    def refresh_device_buttons(self):
        """Odświeża listę przycisków urządzeń w panelu po lewej."""
        for i in reversed(range(self.devices_layout.count())):
            widget = self.devices_layout.itemAt(i).widget()
            if widget is not None:
                widget.deleteLater()

        for dev in self.device_list.devices:
            btn = QPushButton(dev.host)
            btn.setStyleSheet("padding: 8px; font-size: 13px; text-align: left;")
            btn.setContextMenuPolicy(Qt.CustomContextMenu)
            btn.clicked.connect(lambda _, d=dev: self.show_device_details(d))

            # klik PPM — usuń urządzenie
            def open_context_menu(pos, d=dev, b=btn):
                from PySide6.QtWidgets import QMenu

                menu = QMenu()
                remove_action = menu.addAction("Usuń urządzenie 🗑️")
                toggle_action = menu.addAction("Przełącz połączenie (mock) 🔄")
                action = menu.exec_(b.mapToGlobal(pos))
                if action == remove_action:
                    self.remove_device(d.host)
                elif action == toggle_action:
                    self.connection_manager.toggle_status(d.host)
                    self.update_status_bar()

            btn.customContextMenuRequested.connect(open_context_menu)
            self.devices_layout.addWidget(btn)

        self.devices_layout.setAlignment(Qt.AlignTop)

    def add_device_dialog(self):
        dialog = AddDeviceDialog(self)
        if dialog.exec() == QDialog.Accepted:
            new_dev = dialog.get_data()
            if new_dev.host:
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
            self.show_device_details(None)

    def show_device_details(self, device: Device):
        """Wyświetla szczegóły urządzenia po lewej."""
        self.current_device = device
        self.detail_box.show_for_device(device)
        self.update_status_bar()

    def scan_network(self):
        from gui.NetworkScanDialog import NetworkScanDialog
        from gui.ScanResultsDialog import ScanResultsDialog

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

    def open_settings_dialog(self):
        dialog = SettingsDialog(self, self.connection_type)
        if dialog.exec() == QDialog.Accepted:
            self.connection_type = dialog.get_connection_type()

    # --- NOWE: aktualizacja statusu ---
    def update_status_bar(self):
        """Odświeża pasek statusu (co 4 sekundy)."""
        if not self.current_device:
            self.status_label.setText("Brak aktywnego urządzenia.")
            return

        host = self.current_device.host
        state = self.connection_manager.get_status(self.current_device)
        color = {
            "connected": "#0f0",
            "disconnected": "#f00",
            "error": "#ff9800",
        }.get(state, "#ccc")

        time_str = QTime.currentTime().toString("HH:mm:ss")
        self.status_label.setText(
            f"<b>{host}</b> — <span style='color:{color}'>{state.upper()}</span> | Last check: {time_str}"
        )

    def closeEvent(self, event):
        self.settings.setValue("connection_type", self.connection_type)
        super().closeEvent(event)

    # --- MOCKOWE FUNKCJE KONFIGURACYJNE ---

    def apply_current_device(self):
        """Zatwierdza konfigurację dla bieżącego urządzenia (mock)."""
        if not self.current_device:
            QMessageBox.information(self, "Brak urządzenia", "Nie wybrano żadnego urządzenia.")
            return
        host = self.current_device.host
        QMessageBox.information(self, "Zatwierdzono", f"Zatwierdzono konfigurację dla {host}.")
        self.detail_box.append_console(f"[MOCK] Applied configuration for {host}")

    def apply_all_devices(self):
        """Zatwierdza konfigurację dla wszystkich urządzeń (mock)."""
        if not self.device_list.devices:
            QMessageBox.information(self, "Brak urządzeń", "Lista urządzeń jest pusta.")
            return
        hosts = [d.host for d in self.device_list.devices]
        QMessageBox.information(self, "Zatwierdzono", "Zatwierdzono konfigurację dla wszystkich urządzeń.")
        for h in hosts:
            self.detail_box.append_console(f"[MOCK] Applied configuration for {h}")

    def sync_current_device(self):
        """Odświeża konfigurację bieżącego urządzenia (mock)."""
        if not self.current_device:
            QMessageBox.warning(self, "Brak urządzenia", "Najpierw wybierz urządzenie.")
            return
        host = self.current_device.host
        QMessageBox.information(self, "Synchronizacja", f"Synchronizacja konfiguracji z {host} (mock).")
        self.detail_box.append_console(f"[MOCK] Synced configuration for {host}")

    def reset_current_device(self):
        """Resetuje zmiany dla bieżącego urządzenia (mock)."""
        if not self.current_device:
            QMessageBox.warning(self, "Brak urządzenia", "Najpierw wybierz urządzenie.")
            return
        host = self.current_device.host
        QMessageBox.information(self, "Reset", f"Zmiany dla {host} zostały odrzucone (mock).")
        self.detail_box.append_console(f"[MOCK] Discarded local changes for {host}")

