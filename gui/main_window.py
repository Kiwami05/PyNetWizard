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

from devices.connection_manager import ConnectionManager
from gui.add_device_dialog import AddDeviceDialog
from devices.device_list import DeviceList
from devices.device import Device
from gui.config_history_dialog import ConfigHistoryDialog
from gui.log_viewer_dialog import LogViewerDialog
from gui.queued_changes_dialog import QueuedChangesDialog
from gui.settings_dialog import SettingsDialog
from gui.device_detail_widget import DeviceDetailWidget
from operations.operation_support import UnsupportedOperationsError
from services.config_history import save_snapshot
from services.config_sync import ConfigSyncService


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
        self.setWindowTitle("PyNetWizard — Konfigurator Sieciowy")
        self.resize(900, 550)

        self.device_list = device_list
        self.current_device = None

        # === CENTRALNY WIDGET ===
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)

        # === LEWY PANEL: lista hostów + przyciski ===
        left_panel = QVBoxLayout()

        btn_add = QPushButton("Dodaj urządzenie")
        btn_add.clicked.connect(self.add_device_dialog)
        left_panel.addWidget(btn_add)

        btn_clear = QPushButton("Wyczyść listę urządzeń")
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

        action_save = file_menu.addAction("Zapisz listę urządzeń")
        action_save.triggered.connect(self.save_inventory)

        action_load = file_menu.addAction("Wczytaj listę urządzeń")
        action_load.triggered.connect(self.load_inventory)

        device_menu = menubar.addMenu("Urządzenie")

        action_apply_current = device_menu.addAction(
            "Zatwierdź konfigurację (bieżące urządzenie)"
        )
        action_apply_current.triggered.connect(self.apply_current_device)

        action_apply_all = device_menu.addAction(
            "Zatwierdź konfigurację (wszystkie urządzenia)"
        )
        action_apply_all.triggered.connect(self.apply_all_devices)

        device_menu.addSeparator()

        action_sync = device_menu.addAction("Synchronizuj konfigurację")
        action_sync.triggered.connect(self.sync_current_device)

        device_menu.addSeparator()

        action_queued_changes = device_menu.addAction("Pokaż zakolejkowane zmiany")
        action_queued_changes.triggered.connect(self.open_queued_changes_dialog)

        device_menu.addSeparator()

        action_history = device_menu.addAction("Historia konfiguracji")
        action_history.triggered.connect(self.open_config_history_dialog)

        device_menu.addSeparator()

        action_reset_one = device_menu.addAction("Resetuj zmiany (bieżące urządzenie)")
        action_reset_one.triggered.connect(self.reset_current_device)

        action_reset_all = device_menu.addAction(
            "Resetuj zmiany (wszystkie urządzenia)"
        )
        action_reset_all.triggered.connect(self.reset_all_devices)

        action_log_viewer = menubar.addAction("Logi")
        action_log_viewer.triggered.connect(self.open_log_viewer)

        settings_action = menubar.addAction("Ustawienia")
        settings_action.triggered.connect(self.open_settings_dialog)

        # --- NOWE: status bar ---
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_label = QLabel("Gotowy.")
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

        self.connection_manager = ConnectionManager(
            connection_type=self.connection_type,
            timeout=int(self.settings.value("timeout", 10)),
            verbose=(self.settings.value("verbose", "false") == "true"),
            log_path=self.settings.value("log_path", "./logs"),
        )

        self.config_sync = ConfigSyncService(self.connection_manager)

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
                edit_action = menu.addAction("Edytuj urządzenie ✏️")
                action = menu.exec_(b.mapToGlobal(pos))
                if action == remove_action:
                    self.remove_device(d.host)
                elif action == edit_action:
                    self.edit_device_dialog(d)

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
            self.clear_device_buffer(host)
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
            self.clear_device_buffer()
            self.refresh_device_buttons()
            self.show_device_details(None)

    def show_device_details(self, device: Device):
        """Wyświetla szczegóły urządzenia po lewej."""
        self.current_device = device
        self.detail_box.show_for_device(device)
        self.update_status_bar()

        # 🔸 Po wybraniu urządzenia — powiąż zakładkę GLOBAL z ConnectionManagerem
        if device and "GLOBAL" in self.detail_box.pages:
            try:
                global_tab = self.detail_box.pages["GLOBAL"]
                if hasattr(global_tab, "bind_device"):
                    global_tab.bind_device(device, self.connection_manager)
            except Exception as e:
                print(f"[WARN] Nie udało się podpiąć GlobalTab: {e}")

    def scan_network(self):
        from gui.network_scan_dialog import NetworkScanDialog
        from gui.scan_results_dialog import ScanResultsDialog

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
            self, "Zapisz listę urządzeń", "inventory.json", "Pliki JSON (*.json)"
        )
        if filename:
            self.device_list.save_to_file(filename)
            QMessageBox.information(
                self, "Zapisano", f"Lista urządzeń została zapisana do {filename}"
            )

    def load_inventory(self):
        filename, _ = QFileDialog.getOpenFileName(
            self, "Wczytaj listę urządzeń", "", "Pliki JSON (*.json)"
        )
        if filename:
            self.device_list.load_from_file(filename)
            self.clear_device_buffer()
            self.refresh_device_buttons()
            QMessageBox.information(
                self, "Wczytano", f"Załadowano listę urządzeń z {filename}"
            )
        if self.device_list.devices:
            first_device = self.device_list.devices[0]
            self.detail_box.pages["GLOBAL"].bind_device(
                first_device, self.connection_manager
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

        dev = self.current_device
        alive = self.connection_manager.is_connected(dev)
        color = "#0f0" if alive else "#f00"
        state = "POŁĄCZONO" if alive else "ODŁĄCZONO"
        time_str = QTime.currentTime().toString("HH:mm:ss")

        self.status_label.setText(
            f"<b>{dev.host}</b> — <span style='color:{color}'>{state}</span> | Sprawdzono: {time_str}"
        )

    def closeEvent(self, event):
        for dev in list(self.connection_manager.sessions.keys()):
            d = next((x for x in self.device_list.devices if x.host == dev), None)
            if d:
                self.connection_manager.disconnect(d)
        self.settings.setValue("connection_type", self.connection_type)
        super().closeEvent(event)

    # --- MOCKOWE FUNKCJE KONFIGURACYJNE ---

    def apply_current_device(self):
        if not self.current_device:
            QMessageBox.warning(self, "Brak urządzenia", "Nie wybrano urządzenia.")
            return

        dev = self.current_device
        # musimy mieć snapshot, bo GlobalTab delta porównuje z conf
        buf = self.detail_box.buffers.get(dev.host)
        if not buf or not buf.config:
            QMessageBox.information(
                self, "Brak snapshotu", "Najpierw wykonaj Sync dla tego urządzenia."
            )
            return

        try:
            if not self.connection_manager.connect(dev):
                raise ConnectionError("Nie udało się nawiązać połączenia.")

            # 1) Zbierz pending z aktualnych tabów
            cmds = self.detail_box.collect_pending_commands_current(buf.config)
            cmds = [c.strip() for c in cmds if c.strip()]

            if not cmds:
                QMessageBox.information(self, "Brak zmian", "Nie ma nic do wysłania.")
                return

            # 2) Wyślij
            output = self.connection_manager.send_config(dev, cmds)
            self.detail_box.append_console(output)

            # 3) Po sukcesie wyczyść pendingi w aktywnych tabach
            self.detail_box.clear_pending_commands_current()
            self.detail_box.append_console(
                f"[APPLY] Wysłano {len(cmds)} komend do {dev.host}"
            )

            # 4) (Mocno zalecane) Odśwież snapshot i UI – jedna prawda
            self.sync_current_device()
            QMessageBox.information(
                self, "Zatwierdzono", f"Konfiguracja zapisana na {dev.host}."
            )
        except UnsupportedOperationsError as e:
            QMessageBox.warning(self, "Nieobsługiwana funkcja", _format_exception(e))
        except Exception as e:
            QMessageBox.critical(self, "Błąd", _format_exception(e))

    def apply_all_devices(self):
        if not self.device_list.devices:
            QMessageBox.information(self, "Brak urządzeń", "Lista urządzeń jest pusta.")
            return

        applied = 0
        errors = []

        # Upewnij się, że bieżący stan GUI jest w buforze
        if self.current_device:
            self.detail_box.save_tab_state(self.current_device)

        for dev in self.device_list.devices:
            buf = self.detail_box.buffers.get(dev.host)
            if not buf or not buf.config:
                # brak snapshotu → pomiń, albo (opcjonalnie) zrób sync automatycznie
                continue

            try:
                cmds = self.detail_box.collect_pending_commands_from_buffer(
                    dev.host, dev
                )
                if not cmds:
                    continue

                if not self.connection_manager.connect(dev):
                    raise ConnectionError("Nie udało się nawiązać połączenia.")

                output = self.connection_manager.send_config(dev, cmds)
                self.detail_box.append_console(f"[APPLY ALL:{dev.host}] {output}")

                self.detail_box.clear_pending_commands_in_buffer(dev.host)
                applied += 1

                # (Opcjonalnie) szybki resync każdego urządzenia:
                # Tu można pominąć dla wydajności, a zrobić zbiorczy komunikat,
                # ale najczyściej: po apply — sync, żeby snapshot pasował.
                if dev == self.current_device:
                    self.sync_current_device()  # pokaże od razu aktualizację
                else:
                    # light-weight: pobierz i zaktualizuj tylko snapshot, bez przełączania UI
                    try:
                        conf = self.config_sync.fetch_and_parse(dev)
                        buf.config = conf
                    except Exception:
                        pass

            except Exception as e:
                errors.append(f"{dev.host}: {_format_exception(e)}")

        if applied == 0 and not errors:
            QMessageBox.information(
                self, "Brak zmian", "Nie znaleziono zmian do wysłania."
            )
            return

        msg = f"Zastosowano zmiany na {applied} urządzeniach."
        if errors:
            msg += "\nBłędy:\n- " + "\n- ".join(errors)
        QMessageBox.information(self, "Zakończono", msg)

    def sync_current_device(self):
        if not self.current_device:
            QMessageBox.warning(self, "Brak urządzenia", "Najpierw wybierz urządzenie.")
            return

        dev = self.current_device
        try:
            if not self.connection_manager.connect(dev):
                raise ConnectionError("Nie udało się połączyć.")
            # 🆕 pobranie + parsowanie
            conf = self.config_sync.fetch_and_parse(dev)

            # 🆕 rozesłanie do tabów
            self.detail_box.sync_tabs_from_config(conf)

            # 🆕 zapis snapshotu do historii (raw_running)
            try:
                if conf.raw_running:
                    save_snapshot(dev, conf.raw_running, kind="running")
            except Exception:
                # nie chcemy wywracać całego SYNC-a przez problem z dyskiem
                pass

            # 🧾 konsola globalna + status
            self.detail_box.append_console(
                f"[SYNC] Nazwa hosta: {conf.hostname or '-'}"
            )
            QMessageBox.information(
                self,
                "Pobrano",
                f"Konfiguracja {dev.host} zsynchronizowana z zakładkami.",
            )
        except Exception as e:
            QMessageBox.critical(self, "Błąd", _format_exception(e))

    def reset_current_device(self):
        """Przywraca ostatni snapshot (bez pobierania z urządzenia)."""
        if not self.current_device:
            QMessageBox.warning(self, "Brak urządzenia", "Najpierw wybierz urządzenie.")
            return

        dev = self.current_device
        buf = self.detail_box.buffers.get(dev.host)
        if not buf or not buf.config:
            QMessageBox.information(
                self,
                "Brak danych",
                "Nie można przywrócić — brak zapisanego snapshotu (urządzenie nie było synchronizowane).",
            )
            return

        reply = QMessageBox.question(
            self,
            "Potwierdzenie",
            f"Czy na pewno chcesz odrzucić zmiany dla {dev.host} i przywrócić ostatni snapshot?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.No:
            return

        self.detail_box.current_device = dev
        self.detail_box.restore_from_snapshot()
        QMessageBox.information(
            self, "Przywrócono", f"Przywrócono stan {dev.host} z ostatniego synca."
        )
        self.detail_box.append_console(f"[RESET] Przywrócono snapshot dla {dev.host}")

    def reset_all_devices(self):
        """Przywraca snapshot dla wszystkich urządzeń, które go posiadają."""
        if not self.device_list.devices:
            QMessageBox.information(self, "Brak urządzeń", "Lista urządzeń jest pusta.")
            return

        reply = QMessageBox.question(
            self,
            "Potwierdzenie",
            "Czy na pewno chcesz przywrócić snapshoty dla wszystkich urządzeń?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.No:
            return

        count = 0
        for dev in self.device_list.devices:
            buf = self.detail_box.buffers.get(dev.host)
            if buf and buf.config:
                count += 1
                # Nie musimy otwierać wizualnie każdego — wystarczy zapisać stan bufora
                self.detail_box.current_device = dev
                self.detail_box.restore_from_snapshot()

        QMessageBox.information(
            self,
            "Zakończono",
            f"Przywrócono snapshoty dla {count} urządzeń (jeśli były dostępne).",
        )
        self.detail_box.append_console(f"[RESET ALL] Przywrócono {count} urządzeń.")

    def clear_device_buffer(self, host: str | None = None):
        """Usuwa bufor danego urządzenia lub wszystkie bufory."""
        if not hasattr(self.detail_box, "buffers"):
            return
        if host is None:
            self.detail_box.buffers.clear()
        else:
            self.detail_box.buffers.pop(host, None)

    def edit_device_dialog(self, device):
        from gui.add_device_dialog import AddDeviceDialog

        dlg = AddDeviceDialog(self)

        # wypełnij istniejącymi danymi
        dlg.input_host.setText(device.host)
        dlg.input_username.setText(device.username)
        dlg.input_password.setText(device.password)

        # vendor
        if device.vendor.name == "CISCO":
            dlg.radio_cisco.setChecked(True)
        else:
            dlg.radio_juniper.setChecked(True)

        # typ urządzenia
        dlg.combo_devtype.setCurrentText(device.device_type.name.title())

        if dlg.exec():
            new_device = dlg.get_data()
            # aktualizacja obiektu
            device.host = new_device.host
            device.username = new_device.username
            device.password = new_device.password
            device.vendor = new_device.vendor
            device.device_type = new_device.device_type

            self.device_list.sort_devices()
            self.refresh_device_buttons()
            # odśwież widok jeśli edytowaliśmy aktualnie wybrane urządzenie
            if self.current_device == device:
                self.show_device_details(device)

    def open_config_history_dialog(self):
        """
        Otwiera dialog historii konfiguracji dla bieżącego urządzenia.
        Porównanie odbywa się względem ostatniego snapshotu (buf.config.raw_running),
        jeśli jest dostępny.
        """
        if not self.current_device:
            QMessageBox.information(
                self,
                "Brak urządzenia",
                "Najpierw wybierz urządzenie z listy po lewej.",
            )
            return

        dev = self.current_device
        buf = self.detail_box.buffers.get(dev.host)
        current_raw = ""
        if buf and getattr(buf, "config", None) and buf.config.raw_running:
            current_raw = buf.config.raw_running

        dlg = ConfigHistoryDialog(dev, current_raw, self)
        dlg.exec()

    def open_queued_changes_dialog(self):
        if not self.current_device:
            QMessageBox.information(
                self,
                "Brak urządzenia",
                "Najpierw wybierz urządzenie z listy po lewej.",
            )
            return

        dev = self.current_device
        buf = self.detail_box.buffers.get(dev.host)
        if not buf or not getattr(buf, "config", None):
            QMessageBox.information(
                self,
                "Brak snapshotu",
                "Najpierw wykonaj Sync dla tego urządzenia.",
            )
            return

        try:
            preview = self.detail_box.preview_pending_changes_current(buf.config)
        except UnsupportedOperationsError as e:
            QMessageBox.warning(self, "Nieobsługiwana funkcja", _format_exception(e))
            return

        commands = preview["commands"]

        if not commands:
            QMessageBox.information(
                self,
                "Brak zmian",
                f"Brak zakolejkowanych zmian dla {dev.host}.",
            )
            return

        dlg = QueuedChangesDialog(
            host=dev.host,
            commands=commands,
            operation_count=preview["operation_count"],
            parent=self,
        )
        dlg.exec()

    def open_log_viewer(self):
        dlg = LogViewerDialog(self)
        dlg.exec()


def _format_exception(exc: Exception) -> str:
    message = str(exc).strip()
    if message:
        return message
    return type(exc).__name__
