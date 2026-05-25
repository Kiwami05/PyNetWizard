from PySide6.QtCore import Qt, QSettings, QThread, QTimer, QTime, Slot
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

from connections.connection_manager import ConnectionManager
from gui.dialogs.add_device_dialog import AddDeviceDialog
from devices.device_buffer import DeviceBuffer
from devices.device_list import DeviceList
from devices.device import Device
from gui.dialogs.config_history_dialog import ConfigHistoryDialog
from gui.dialogs.message_box import ask_yes_no
from gui.device_operation_worker import DeviceOperationWorker
from gui.dialogs.log_viewer_dialog import LogViewerDialog
from gui.dialogs.queued_changes_dialog import QueuedChangesDialog
from gui.dialogs.settings_dialog import SettingsDialog
from gui.device_detail_widget import DeviceDetailWidget
from operations.operation_support import UnsupportedOperationsError
from services.config_history import save_snapshot
from services.config_sync import ConfigSyncService


class MainWindow(QMainWindow):
    def __init__(self, device_list: DeviceList):
        super().__init__()
        self.setWindowTitle("PyNetWizard — Konfigurator Sieciowy")
        self.resize(900, 550)

        self.device_list = device_list
        self.current_device = None

        # Centralny widget
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)

        # Lewy panel: lista hostów + przyciski
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

        # Prawy panel: rozwinięcie tabów
        self.detail_box = DeviceDetailWidget()
        main_layout.addWidget(self.detail_box, 2)

        # Pasek menu
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

        # Pasek stanu (połączenia)
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_label = QLabel("Gotowy.")
        self.status_label.setStyleSheet("font-family: monospace;")
        self.status_bar.addPermanentWidget(self.status_label)

        # Zegar i timer odświeżania
        self.last_check_time = QTime.currentTime()
        self.status_timer = QTimer(self)
        self.status_timer.timeout.connect(self.update_status_bar)
        self.status_timer.start(4000)  # co 4 sekundy

        # Ustawienia
        self.settings = QSettings("WEEiA", "PyNetWizard")
        self.connection_type = self.settings.value("connection_type", "ssh")

        self.connection_manager = ConnectionManager(
            connection_type=self.connection_type,
            timeout=int(self.settings.value("timeout", 10)),
            verbose=(self.settings.value("verbose", "false") == "true"),
            log_path=self.settings.value("log_path", "./logs"),
            persist_cisco_config=(
                self.settings.value("persist_cisco_config", "true") == "true"
            ),
        )

        self.config_sync = ConfigSyncService(self.connection_manager)
        self._operation_busy = False
        self._active_operation = None
        self._running_operations = []

        global_tab = self.detail_box.pages.get("GLOBAL")
        if global_tab and hasattr(global_tab, "set_operation_runner"):
            global_tab.set_operation_runner(self._run_device_operation)

        self.refresh_device_buttons()

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

            # PPM — usuń urządzenie
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
                if self._is_autosync_enabled():
                    self._autosync_devices([new_dev])

    def remove_device(self, host: str):
        reply = ask_yes_no(
            self,
            "Potwierdzenie",
            f"Czy na pewno chcesz usunąć urządzenie „{host}”?",
        )
        if reply == QMessageBox.Yes:
            self.device_list.remove_device(host)
            self.clear_device_buffer(host)
            self.refresh_device_buttons()
            self.show_device_details(None)

    def clear_device_list(self):
        reply = ask_yes_no(
            self,
            "Potwierdzenie",
            "Czy na pewno chcesz wyczyścić listę urządzeń?",
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

        # Po wybraniu urządzenia — powiąż zakładkę GLOBAL z ConnectionManagerem
        if device and "GLOBAL" in self.detail_box.pages:
            try:
                global_tab = self.detail_box.pages["GLOBAL"]
                if hasattr(global_tab, "bind_device"):
                    global_tab.bind_device(device, self.connection_manager)
            except Exception as e:
                print(f"[WARN] Nie udało się podpiąć GlobalTab: {e}")

    def scan_network(self):
        from gui.dialogs.network_scan_dialog import NetworkScanDialog
        from gui.dialogs.scan_results_dialog import ScanResultsDialog

        existing_hosts = [d.host for d in self.device_list.devices]
        dlg = NetworkScanDialog(self, exclude_hosts=existing_hosts)
        if dlg.exec() == QDialog.Accepted:
            results = dlg.get_results()
            if not results:
                return
            res_dialog = ScanResultsDialog(results, self)
            if res_dialog.exec() == QDialog.Accepted:
                new_devices = res_dialog.get_selected_devices()
                added_devices = []
                for dev in new_devices.devices:
                    if any(d.host == dev.host for d in self.device_list.devices):
                        continue
                    self.device_list.add_device(dev)
                    added_devices.append(dev)
                self.refresh_device_buttons()
                if added_devices and self._is_autosync_enabled():
                    self._autosync_devices(added_devices)

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
            self._apply_runtime_settings()

    def _apply_runtime_settings(self):
        self.connection_type = self.settings.value("connection_type", "ssh")
        self.connection_manager.connection_type = self.connection_type
        self.connection_manager.timeout = int(self.settings.value("timeout", 10))
        self.connection_manager.persist_cisco_config = (
            self.settings.value("persist_cisco_config", "true") == "true"
        )

    def _is_autosync_enabled(self) -> bool:
        return self.settings.value("autosync", "false") == "true"

    def _sync_device_work(self, dev: Device):
        if not self.connection_manager.connect(dev):
            raise ConnectionError("Nie udało się połączyć.")
        conf = self.config_sync.fetch_and_parse(dev)
        if conf.raw_running:
            save_snapshot(dev, conf.raw_running, kind="running")
        return conf

    def _autosync_devices(self, devices: list[Device]):
        if not devices:
            return

        if len(devices) == 1:
            dev = devices[0]

            def work():
                return self._sync_device_work(dev)

            def on_success(conf):
                self._store_config_for_device(dev, conf)
                self._append_console_for_device(
                    dev, f"[SYNC] Nazwa hosta: {conf.hostname or '-'}"
                )
                QMessageBox.information(
                    self,
                    "Pobrano",
                    f"Konfiguracja {dev.host} zsynchronizowana po dodaniu urządzenia.",
                )

            self._run_device_operation(
                f"Synchronizacja konfiguracji {dev.host}",
                work,
                on_success,
                lambda message: QMessageBox.critical(self, "Błąd autosync", message),
            )
            return

        def work():
            synced = []
            errors = []
            for dev in devices:
                try:
                    conf = self._sync_device_work(dev)
                    synced.append((dev, conf))
                except Exception as exc:
                    errors.append(f"{dev.host}: {_format_exception(exc)}")
            return {"synced": synced, "errors": errors}

        def on_success(result):
            synced = result["synced"]
            errors = result["errors"]
            for dev, conf in synced:
                self._store_config_for_device(dev, conf)
                self._append_console_for_device(
                    dev, f"[SYNC] Nazwa hosta: {conf.hostname or '-'}"
                )

            synced_count = len(synced)
            if errors:
                msg = (
                    f"Autosync zakończony częściowo. Zsynchronizowano: {synced_count}/{len(devices)}.\n\n"
                    + "\n".join(errors)
                )
                QMessageBox.warning(self, "Autosync", msg)
            elif synced_count:
                QMessageBox.information(
                    self,
                    "Autosync",
                    f"Zsynchronizowano {synced_count} nowych urządzeń.",
                )

        self._run_device_operation(
            "Synchronizacja konfiguracji nowych urządzeń",
            work,
            on_success,
            lambda message: QMessageBox.critical(self, "Błąd autosync", message),
        )

    def update_status_bar(self):
        """Odświeża pasek statusu bez wykonywania I/O w wątku GUI."""
        if not self.current_device:
            self.status_label.setText("Brak aktywnego urządzenia.")
            return

        dev = self.current_device
        alive = self.connection_manager.has_session(dev)
        color = "#0f0" if alive else "#f00"
        state = "SESJA OTWARTA" if alive else "ODŁĄCZONO"
        if self._operation_busy:
            state = "OPERACJA W TOKU"
            color = "#ffaa00"
        time_str = QTime.currentTime().toString("HH:mm:ss")

        self.status_label.setText(
            f"<b>{dev.host}</b> — <span style='color:{color}'>{state}</span> | Aktualizacja: {time_str}"
        )

    def _run_device_operation(
        self,
        title: str,
        work,
        on_success,
        on_error=None,
    ) -> bool:
        if self._operation_busy:
            QMessageBox.information(
                self,
                "Operacja w toku",
                "Poczekaj na zakończenie bieżącej operacji na urządzeniu.",
            )
            return False

        self._operation_busy = True
        self.status_label.setText(f"{title}...")

        thread = QThread(self)
        worker = DeviceOperationWorker(work)
        worker.moveToThread(thread)
        record = {"thread": thread, "worker": worker}
        record["on_success"] = on_success
        record["on_error"] = on_error
        self._running_operations.append(record)
        self._active_operation = record

        def cleanup():
            if record in self._running_operations:
                self._running_operations.remove(record)
            if self._active_operation is record:
                self._active_operation = None
            thread.deleteLater()

        thread.started.connect(worker.run)
        worker.finished.connect(self._handle_device_operation_success)
        worker.finished.connect(worker.deleteLater)
        worker.finished.connect(thread.quit)
        worker.error.connect(self._handle_device_operation_error)
        worker.error.connect(worker.deleteLater)
        worker.error.connect(thread.quit)
        thread.finished.connect(cleanup)
        thread.start()
        return True

    @Slot(object)
    def _handle_device_operation_success(self, result):
        record = self._active_operation
        self._operation_busy = False
        self.update_status_bar()
        if record and record.get("on_success"):
            record["on_success"](result)

    @Slot(str)
    def _handle_device_operation_error(self, message):
        record = self._active_operation
        self._operation_busy = False
        self.update_status_bar()
        if record and record.get("on_error"):
            record["on_error"](message)
        else:
            QMessageBox.critical(self, "Błąd", message)

    def _append_console_for_device(self, device: Device, text: str):
        message = text.strip()
        if not message:
            return
        if device == self.current_device:
            self.detail_box.append_console(message)
            return

        buf = self.detail_box.buffers.setdefault(device.host, DeviceBuffer())
        if buf.logs:
            buf.logs += "\n" + message
        else:
            buf.logs = message

    def _store_config_for_device(self, device: Device, conf):
        if device == self.current_device:
            self.detail_box.sync_tabs_from_config(conf)
            return

        buf = self.detail_box.buffers.setdefault(device.host, DeviceBuffer())
        buf.hostname = conf.hostname or buf.hostname
        buf.tabs.setdefault("GLOBAL", {})
        buf.config = conf

    def closeEvent(self, event):
        if self._operation_busy:
            QMessageBox.information(
                self,
                "Operacja w toku",
                "Poczekaj na zakończenie bieżącej operacji przed zamknięciem programu.",
            )
            event.ignore()
            return
        for dev in list(self.connection_manager.sessions.keys()):
            d = next((x for x in self.device_list.devices if x.host == dev), None)
            if d:
                self.connection_manager.disconnect(d)
        self.settings.setValue("connection_type", self.connection_type)
        super().closeEvent(event)

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
            # Zbierz pending z aktualnych tabów w wątku GUI.
            cmds = self.detail_box.render_pending_operations_current(buf.config)
            cmds = [c.strip() for c in cmds if c.strip()]
        except UnsupportedOperationsError as e:
            QMessageBox.warning(self, "Nieobsługiwana funkcja", _format_exception(e))
            return
        except Exception as e:
            QMessageBox.critical(self, "Błąd", _format_exception(e))
            return

        if not cmds:
            QMessageBox.information(self, "Brak zmian", "Nie ma nic do wysłania.")
            return

        def work():
            output = self.connection_manager.send_config(dev, cmds)
            conf = self.config_sync.fetch_and_parse(dev)
            if conf.raw_running:
                save_snapshot(dev, conf.raw_running, kind="running")
            return {"output": output, "conf": conf}

        def on_success(result):
            output = result["output"]
            conf = result["conf"]
            self._append_console_for_device(dev, output)
            if dev == self.current_device:
                self.detail_box.clear_pending_operations_current()
            else:
                self.detail_box.clear_pending_operations_in_buffer(dev.host)
            self._append_console_for_device(
                dev, f"[APPLY] Wysłano {len(cmds)} komend do {dev.host}"
            )
            self._store_config_for_device(dev, conf)
            QMessageBox.information(
                self, "Zatwierdzono", f"Konfiguracja zapisana na {dev.host}."
            )

        self._run_device_operation(
            f"Zatwierdzanie konfiguracji {dev.host}",
            work,
            on_success,
            lambda message: QMessageBox.critical(self, "Błąd", message),
        )

    def apply_all_devices(self):
        if not self.device_list.devices:
            QMessageBox.information(self, "Brak urządzeń", "Lista urządzeń jest pusta.")
            return

        # Upewnij się, że bieżący stan GUI jest w buforze
        if self.current_device:
            self.detail_box.save_tab_state(self.current_device)

        jobs = []
        for dev in self.device_list.devices:
            buf = self.detail_box.buffers.get(dev.host)
            if not buf or not buf.config:
                # brak snapshotu → pomiń albo (opcjonalnie) zrób sync automatycznie
                continue

            try:
                cmds = self.detail_box.render_pending_operations_from_buffer(
                    dev.host, dev
                )
            except Exception as e:
                QMessageBox.critical(
                    self, "Błąd", f"{dev.host}: {_format_exception(e)}"
                )
                return
            cmds = [c.strip() for c in cmds if c.strip()]
            if cmds:
                jobs.append((dev, cmds))

        if not jobs:
            QMessageBox.information(
                self, "Brak zmian", "Nie znaleziono zmian do wysłania."
            )
            return

        def work():
            applied_results = []
            errors = []
            for job_dev, cmds in jobs:
                try:
                    output = self.connection_manager.send_config(job_dev, cmds)
                    conf = self.config_sync.fetch_and_parse(job_dev)
                    if conf.raw_running:
                        save_snapshot(job_dev, conf.raw_running, kind="running")
                    applied_results.append(
                        {
                            "device": job_dev,
                            "commands": cmds,
                            "output": output,
                            "conf": conf,
                        }
                    )
                except Exception as exc:
                    errors.append(f"{job_dev.host}: {_format_exception(exc)}")
            return {"applied": applied_results, "errors": errors}

        def on_success(result):
            for item in result["applied"]:
                item_dev = item["device"]
                self._append_console_for_device(
                    item_dev, f"[APPLY ALL:{item_dev.host}] {item['output']}"
                )
                self.detail_box.clear_pending_operations_in_buffer(item_dev.host)
                self._store_config_for_device(item_dev, item["conf"])

            msg = f"Zastosowano zmiany na {len(result['applied'])} urządzeniach."
            if result["errors"]:
                msg += "\nBłędy:\n- " + "\n- ".join(result["errors"])
            QMessageBox.information(self, "Zakończono", msg)

        self._run_device_operation(
            "Zatwierdzanie konfiguracji na wszystkich urządzeniach",
            work,
            on_success,
            lambda message: QMessageBox.critical(self, "Błąd", message),
        )

    def sync_current_device(self):
        if not self.current_device:
            QMessageBox.warning(self, "Brak urządzenia", "Najpierw wybierz urządzenie.")
            return

        dev = self.current_device

        def work():
            conf = self.config_sync.fetch_and_parse(dev)
            if conf.raw_running:
                save_snapshot(dev, conf.raw_running, kind="running")
            return conf

        def on_success(conf):
            self._store_config_for_device(dev, conf)
            self._append_console_for_device(
                dev, f"[SYNC] Nazwa hosta: {conf.hostname or '-'}"
            )
            QMessageBox.information(
                self,
                "Pobrano",
                f"Konfiguracja {dev.host} zsynchronizowana z zakładkami.",
            )

        self._run_device_operation(
            f"Synchronizacja konfiguracji {dev.host}",
            work,
            on_success,
            lambda message: QMessageBox.critical(self, "Błąd", message),
        )

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

        reply = ask_yes_no(
            self,
            "Potwierdzenie",
            f"Czy na pewno chcesz odrzucić zmiany dla {dev.host} i przywrócić ostatni snapshot?",
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

        reply = ask_yes_no(
            self,
            "Potwierdzenie",
            "Czy na pewno chcesz przywrócić snapshoty dla wszystkich urządzeń?",
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
        from gui.dialogs.add_device_dialog import AddDeviceDialog

        dlg = AddDeviceDialog(self)

        # Wypełnij istniejącymi danymi
        dlg.input_host.setText(device.host)
        dlg.input_username.setText(device.username)
        dlg.input_password.setText(device.password)

        # Producent
        if device.vendor.name == "CISCO":
            dlg.radio_cisco.setChecked(True)
        else:
            dlg.radio_juniper.setChecked(True)

        # Typ urządzenia
        dlg.combo_devtype.setCurrentText(device.device_type.name.title())

        if dlg.exec():
            new_device = dlg.get_data()
            # Aktualizacja obiektu
            device.host = new_device.host
            device.username = new_device.username
            device.password = new_device.password
            device.vendor = new_device.vendor
            device.device_type = new_device.device_type

            self.device_list.sort_devices()
            self.refresh_device_buttons()
            # Odśwież widok, jeśli edytowaliśmy aktualnie wybrane urządzenie
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
