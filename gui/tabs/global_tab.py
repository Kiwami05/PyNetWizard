from PySide6.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QGroupBox,
    QFormLayout,
    QSpacerItem,
    QSizePolicy,
    QMessageBox,
)
from PySide6.QtCore import Qt

from devices.device import Device
from gui.localization import get_open_file_name, get_save_file_name, question_yes_no
from operations.operation import Operation

from operations.operation_type import OperationType
from gui.tabs.base_config_tab import BaseConfigTab
from platforms.global_commands import (
    GlobalCommandProfile,
    global_commands_for_device,
)
from services.parsed_config import ParsedConfig


class GlobalTab(BaseConfigTab):
    """
    Zakładka 'GLOBAL' — zintegrowana z ConnectionManager.
    Pozwala synchronizować hostname, zapisywać i eksportować konfiguracje.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.device: Device | None = None
        self.conn_mgr = None  # przypisane z MainWindow
        self._log_message = lambda _text: None
        self._operation_runner = None
        self._profile: GlobalCommandProfile = global_commands_for_device(None)
        self.pending_ops: list[Operation] = []
        self._loading = False
        self._baseline_hostname = ""
        self._last_logged_hostname = ""

        main_layout = QVBoxLayout(self)
        main_layout.setAlignment(Qt.AlignTop)
        main_layout.setContentsMargins(20, 15, 20, 15)
        main_layout.setSpacing(15)

        # Nagłówek
        title = QLabel("<h2>Ustawienia globalne</h2>")
        main_layout.addWidget(title)

        # Hostname
        form = QFormLayout()
        self.hostname = QLineEdit()
        self.hostname.setPlaceholderText("np. Router1")
        self.hostname.editingFinished.connect(self._on_hostname_changed)
        form.addRow(QLabel("Nazwa hosta:"), self.hostname)
        main_layout.addLayout(form)

        # NVRAM
        self.memory_box = self._make_box(
            self._profile.memory_label or "Pamięć konfiguracji",
            [
                ("Wyczyść", self._action_erase),
                ("Zapisz", self._action_save),
            ],
        )
        main_layout.addWidget(self.memory_box)

        # Startup-config
        self.startup_box = self._make_box(
            self._profile.startup_label or "Startup-config",
            [
                ("Wczytaj...", self._action_load_startup),
                ("Eksportuj...", self._action_export_startup),
            ],
        )
        main_layout.addWidget(self.startup_box)

        # Running-config
        self.running_box = self._make_box(
            self._profile.running_label,
            [
                ("Eksportuj...", self._action_export_running),
                ("Scal...", self._action_merge_running),
            ],
        )
        main_layout.addWidget(self.running_box)

        self.extra_box = self._make_box(
            "Dodatkowe informacje",
            [
                (label, self._make_extra_read_action(label, command))
                for label, command in self._profile.extra_read_commands
            ],
        )
        main_layout.addWidget(self.extra_box)

        # Spacer
        spacer = QSpacerItem(10, 10, QSizePolicy.Minimum, QSizePolicy.Expanding)
        main_layout.addItem(spacer)

    def bind_device(self, device: Device, conn_mgr):
        """Podpina aktualne urządzenie i ConnectionManager."""
        self.device = device
        self.conn_mgr = conn_mgr
        self._profile = global_commands_for_device(device)
        self._update_profile_ui()

    def set_logger(self, log_message):
        self._log_message = log_message or (lambda _text: None)

    def set_operation_runner(self, runner):
        self._operation_runner = runner

    def _action_save(self):
        """Zapisuje konfigurację w NVRAM (write memory)."""
        if not self._check_ready():
            return
        command = self._profile.save_command
        if not command:
            self._show_unsupported_action("Zapis konfiguracji")
            return
        device = self.device
        conn_mgr = self.conn_mgr

        def work():
            return conn_mgr.send_command(device, command)

        def on_success(output):
            self._append_log(output)
            QMessageBox.information(self, "Zapisano", "Konfiguracja została zapisana.")

        self._start_operation(
            "Zapis konfiguracji w NVRAM", work, on_success, "Błąd zapisu"
        )

    def _action_erase(self):
        """Kasuje konfigurację (write erase)."""
        if not self._check_ready():
            return
        command = self._profile.erase_command
        if not command:
            self._show_unsupported_action("Kasowanie konfiguracji")
            return
        reply = question_yes_no(
            self,
            "Potwierdzenie",
            f"Czy na pewno chcesz wykonać '{command}'?",
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.No:
            return
        device = self.device
        conn_mgr = self.conn_mgr

        def work():
            return conn_mgr.send_command(device, command)

        def on_success(output):
            self._append_log(output)
            QMessageBox.information(
                self,
                "Wykonano",
                "Urządzenie zresetowano do domyślnej konfiguracji (po reload).",
            )

        self._start_operation("Kasowanie konfiguracji", work, on_success, "Błąd")

    def _action_load_startup(self):
        """Wczytuje startup-config (copy startup-config running-config)."""
        if not self._check_ready():
            return
        command = self._profile.load_startup_command
        if not command:
            self._show_unsupported_action("Wczytywanie startup-config")
            return
        device = self.device
        conn_mgr = self.conn_mgr

        def work():
            return conn_mgr.send_command(device, command)

        def on_success(output):
            self._append_log(output)
            QMessageBox.information(self, "Wczytano", "Startup-config został wczytany.")

        self._start_operation("Wczytywanie startup-config", work, on_success, "Błąd")

    def _action_export_startup(self):
        """Eksportuje startup-config do pliku."""
        if not self._check_ready():
            return
        command = self._profile.startup_config_command
        if not command:
            self._show_unsupported_action("Eksport startup-config")
            return
        device = self.device
        conn_mgr = self.conn_mgr
        filename, _ = get_save_file_name(
            self, "Zapisz startup-config", "startup-config.txt"
        )
        if not filename:
            return

        def work():
            return conn_mgr.send_command(device, command)

        def on_success(output):
            try:
                with open(filename, "w") as f:
                    f.write(output)
            except OSError as e:
                self._append_log(f"[ERROR] {e}")
                QMessageBox.critical(self, "Błąd eksportu", str(e))
                return
            QMessageBox.information(
                self, "Zapisano", f"Startup-config zapisany do {filename}"
            )
            self._append_log("[EXPORT] Zapisano startup-config.")

        self._start_operation(
            "Eksport startup-config", work, on_success, "Błąd eksportu"
        )

    def _action_export_running(self):
        """Eksportuje running-config do pliku."""
        if not self._check_ready():
            return
        command = self._profile.running_config_command
        device = self.device
        conn_mgr = self.conn_mgr
        filename, _ = get_save_file_name(
            self, "Zapisz running-config", "running-config.txt"
        )
        if not filename:
            return

        def work():
            return conn_mgr.send_command(device, command)

        def on_success(output):
            try:
                with open(filename, "w") as f:
                    f.write(output)
            except OSError as e:
                self._append_log(f"[ERROR] {e}")
                QMessageBox.critical(self, "Błąd eksportu", str(e))
                return
            QMessageBox.information(
                self, "Zapisano", f"Running-config zapisany do {filename}"
            )
            self._append_log("[EXPORT] Zapisano running-config.")

        self._start_operation(
            "Eksport running-config", work, on_success, "Błąd eksportu"
        )

    def _action_merge_running(self):
        """Łączy lokalny plik konfiguracyjny z running-config."""
        if not self._check_ready():
            return
        device = self.device
        conn_mgr = self.conn_mgr
        filename, _ = get_open_file_name(
            self, "Wybierz plik konfiguracyjny", "", "Text Files (*.txt)"
        )
        if not filename:
            return
        try:
            with open(filename, "r") as f:
                lines = [line.strip() for line in f.readlines() if line.strip()]
        except OSError as e:
            self._append_log(f"[ERROR] {e}")
            QMessageBox.critical(self, "Błąd merge", str(e))
            return

        def work():
            return conn_mgr.send_config(device, lines)

        def on_success(output):
            self._append_log(output)
            QMessageBox.information(
                self, "Wykonano", f"Plik {filename} został zaaplikowany do urządzenia."
            )

        self._start_operation("Scalanie running-config", work, on_success, "Błąd merge")

    def _make_extra_read_action(self, label: str, command: str):
        def action():
            if not self._check_ready():
                return
            device = self.device
            conn_mgr = self.conn_mgr

            def work():
                return conn_mgr.send_command(device, command)

            def on_success(output):
                filename, _ = get_save_file_name(
                    self, label, self._default_extra_filename(label)
                )
                if not filename:
                    return
                try:
                    with open(filename, "w") as f:
                        f.write(output)
                except OSError as e:
                    self._append_log(f"[ERROR] {e}")
                    QMessageBox.critical(self, "Błąd eksportu", str(e))
                    return
                self._append_log(f"[EXPORT] {label}: zapisano do {filename}")
                QMessageBox.information(self, "Zapisano", f"Zapisano do {filename}")

            self._start_operation(label, work, on_success, label)

        return action

    def _default_extra_filename(self, label: str) -> str:
        if "commit" in label.lower():
            return "commit-history.txt"
        return "configuration.txt"

    def _make_box(self, title: str, buttons: list[tuple[str, callable]]) -> QGroupBox:
        """Pomocniczy konstruktor sekcji (grup z przyciskami)."""
        box = QGroupBox(title)
        layout = QHBoxLayout(box)
        layout.setSpacing(8)
        for text, handler in buttons:
            btn = QPushButton(text)
            btn.setFixedWidth(120)
            btn.clicked.connect(handler)
            layout.addWidget(btn)
        layout.addStretch()
        return box

    def _update_profile_ui(self):
        self.memory_box.setTitle(self._profile.memory_label or "Pamięć konfiguracji")
        self.memory_box.setVisible(self._profile.memory_label is not None)

        self.startup_box.setTitle(self._profile.startup_label or "Startup-config")
        self.startup_box.setVisible(self._profile.startup_label is not None)

        self.running_box.setTitle(self._profile.running_label)

        layout = self.extra_box.layout()
        while layout.count() > 1:
            item = layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        for label, command in self._profile.extra_read_commands:
            btn = QPushButton(label)
            btn.setMinimumWidth(220)
            btn.clicked.connect(self._make_extra_read_action(label, command))
            layout.insertWidget(layout.count() - 1, btn)

        self.extra_box.setVisible(bool(self._profile.extra_read_commands))

    def _show_unsupported_action(self, action: str):
        QMessageBox.information(
            self,
            "Niedostępne",
            f"{action} nie jest dostępne dla tej platformy.",
        )

    def _on_hostname_changed(self):
        if self._loading:
            return

        hostname = self.hostname.text().strip()
        self._replace_hostname_operation(hostname)

        if not hostname:
            return
        if hostname == self._baseline_hostname:
            return
        if hostname == self._last_logged_hostname:
            return

        self._last_logged_hostname = hostname
        self._append_log(f"[OP] Zmieniono hostname na {hostname}")

    def _replace_hostname_operation(self, hostname: str):
        self.pending_ops = [
            op
            for op in self.pending_ops
            if op.operation_type != OperationType.SET_HOSTNAME
        ]
        if hostname and hostname != self._baseline_hostname:
            self.pending_ops.append(
                Operation(OperationType.SET_HOSTNAME, hostname=hostname)
            )

    def _check_ready(self) -> bool:
        if not self.device or not self.conn_mgr:
            QMessageBox.warning(
                self,
                "Brak kontekstu",
                "Brak przypisanego urządzenia lub menedżera połączeń.",
            )
            return False
        return True

    def _append_log(self, text: str):
        self._log_message(text)

    def _start_operation(self, title, work, on_success, error_title):
        def on_error(message):
            self._append_log(f"[ERROR] {message}")
            QMessageBox.critical(self, error_title, message)

        if self._operation_runner:
            self._operation_runner(title, work, on_success, on_error)
            return

        try:
            on_success(work())
        except Exception as e:
            on_error(str(e).strip() or type(e).__name__)

    def export_state(self) -> dict:
        return {
            "hostname": self.hostname.text(),
            "baseline_hostname": self._baseline_hostname,
            "pending_ops": list(self.pending_ops),
        }

    def import_state(self, data: dict):
        self._loading = True
        try:
            self.hostname.setText(data.get("hostname", ""))
            self._baseline_hostname = data.get("baseline_hostname", "")
            self._last_logged_hostname = ""
            self.pending_ops = list(data.get("pending_ops", []))
        finally:
            self._loading = False

    def sync_from_config(self, conf: ParsedConfig):
        # Ustaw hostname
        if conf.hostname:
            self._loading = True
            try:
                self.hostname.setText(conf.hostname)
                self._baseline_hostname = conf.hostname
                self._last_logged_hostname = ""
                self.pending_ops.clear()
            finally:
                self._loading = False
        # Podgląd — kilka pierwszych linii jako log
        if conf.raw_running:
            head_len = 10
            head = "\n".join(conf.raw_running.splitlines()[:head_len])
            self._append_log(
                f"[SYNC] Snapshot running-config (pierwsze {head_len} linijek):\n"
                + head
            )

    def get_pending_operations(self, clear=False) -> list[Operation]:
        self._replace_hostname_operation(self.hostname.text().strip())
        ops = list(self.pending_ops)
        if clear:
            self.pending_ops.clear()
            self._baseline_hostname = self.hostname.text().strip()
            self._last_logged_hostname = ""
        return ops

    def clear_pending_operations(self):
        self.pending_ops.clear()
        self._baseline_hostname = self.hostname.text().strip()
        self._last_logged_hostname = ""
