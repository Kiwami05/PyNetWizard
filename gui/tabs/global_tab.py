from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QGroupBox,
    QFormLayout,
    QSpacerItem,
    QSizePolicy,
    QFileDialog,
    QMessageBox,
)
from PySide6.QtCore import Qt

from devices.device import Device
from operations.operation import Operation

from operations.operation_type import OperationType
from services.parsed_config import ParsedConfig


class GlobalTab(QWidget):
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
        form.addRow(QLabel("Nazwa hosta:"), self.hostname)
        main_layout.addLayout(form)

        # NVRAM
        nvram_box = self._make_box(
            "Pamięć NVRAM",
            [
                ("Wyczyść", self._action_erase),
                ("Zapisz", self._action_save),
            ],
        )
        main_layout.addWidget(nvram_box)

        # Startup-config
        startup_box = self._make_box(
            "Startup-config",
            [
                ("Wczytaj...", self._action_load_startup),
                ("Eksportuj...", self._action_export_startup),
            ],
        )
        main_layout.addWidget(startup_box)

        # Running-config
        running_box = self._make_box(
            "Running-config",
            [
                ("Eksportuj...", self._action_export_running),
                ("Scal...", self._action_merge_running),
            ],
        )
        main_layout.addWidget(running_box)

        # Sync Configuration
        self.btn_sync = QPushButton("🔄 Synchronizuj konfigurację")
        self.btn_sync.setToolTip(
            "Pobiera konfigurację z urządzenia i aktualizuje nazwę hosta."
        )
        self.btn_sync.clicked.connect(self._action_sync)
        main_layout.addWidget(self.btn_sync)

        # Spacer
        spacer = QSpacerItem(10, 10, QSizePolicy.Minimum, QSizePolicy.Expanding)
        main_layout.addItem(spacer)

    def bind_device(self, device: Device, conn_mgr):
        """Podpina aktualne urządzenie i ConnectionManager."""
        self.device = device
        self.conn_mgr = conn_mgr

    def set_logger(self, log_message):
        self._log_message = log_message or (lambda _text: None)

    def set_operation_runner(self, runner):
        self._operation_runner = runner

    def _action_sync(self):
        """Pobiera konfigurację i aktualizuje hostname."""
        if not self._check_ready():
            return
        device = self.device
        conn_mgr = self.conn_mgr

        def work():
            return conn_mgr.send_command(
                device, "show running-config | include hostname"
            )

        def on_success(output):
            # przykład: "hostname s1"
            for line in output.splitlines():
                if line.strip().startswith("hostname"):
                    _, name = line.strip().split(maxsplit=1)
                    self.hostname.setText(name)
                    break
            self._append_log(output)
            QMessageBox.information(
                self, "Sukces", "Pobrano konfigurację i zaktualizowano hostname."
            )

        self._start_operation(
            "Synchronizacja hostname",
            work,
            on_success,
            "Błąd synchronizacji",
        )

    def _action_save(self):
        """Zapisuje konfigurację w NVRAM (write memory)."""
        if not self._check_ready():
            return
        device = self.device
        conn_mgr = self.conn_mgr

        def work():
            return conn_mgr.send_command(device, "write memory")

        def on_success(output):
            self._append_log(output)
            QMessageBox.information(self, "Zapisano", "Konfiguracja zapisana w NVRAM.")

        self._start_operation(
            "Zapis konfiguracji w NVRAM", work, on_success, "Błąd zapisu"
        )

    def _action_erase(self):
        """Kasuje konfigurację (write erase)."""
        if not self._check_ready():
            return
        reply = QMessageBox.question(
            self,
            "Potwierdzenie",
            "Czy na pewno chcesz wykonać 'write erase'?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.No:
            return
        device = self.device
        conn_mgr = self.conn_mgr

        def work():
            return conn_mgr.send_command(device, "write erase")

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
        device = self.device
        conn_mgr = self.conn_mgr

        def work():
            return conn_mgr.send_command(device, "copy startup-config running-config")

        def on_success(output):
            self._append_log(output)
            QMessageBox.information(self, "Wczytano", "Startup-config został wczytany.")

        self._start_operation("Wczytywanie startup-config", work, on_success, "Błąd")

    def _action_export_startup(self):
        """Eksportuje startup-config do pliku."""
        if not self._check_ready():
            return
        device = self.device
        conn_mgr = self.conn_mgr
        filename, _ = QFileDialog.getSaveFileName(
            self, "Zapisz startup-config", "startup-config.txt"
        )
        if not filename:
            return

        def work():
            return conn_mgr.send_command(device, "show startup-config")

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
        device = self.device
        conn_mgr = self.conn_mgr
        filename, _ = QFileDialog.getSaveFileName(
            self, "Zapisz running-config", "running-config.txt"
        )
        if not filename:
            return

        def work():
            return conn_mgr.send_command(device, "show running-config")

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
        filename, _ = QFileDialog.getOpenFileName(
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
        }

    def import_state(self, data: dict):
        self.hostname.setText(data.get("hostname", ""))

    def sync_from_config(self, conf: ParsedConfig):
        # Ustaw hostname
        if conf.hostname:
            self.hostname.setText(conf.hostname)
        # Podgląd — kilka pierwszych linii jako log
        if conf.raw_running:
            head_len = 10
            head = "\n".join(conf.raw_running.splitlines()[:head_len])
            self._append_log(
                f"[SYNC] Snapshot running-config (pierwsze {head_len} linijek):\n"
                + head
            )

    def build_pending_from_form(self, conf) -> list[Operation]:
        ops: list[Operation] = []
        ui_host = (self.hostname.text() or "").strip()
        if ui_host and ui_host != (conf.hostname or ""):
            ops.append(Operation(OperationType.SET_HOSTNAME, hostname=ui_host))
        return ops
