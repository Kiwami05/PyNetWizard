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
    QPlainTextEdit,
)
from PySide6.QtCore import Qt

from devices.Device import Device


class GlobalTab(QWidget):
    """
    Zakładka 'GLOBAL' — zintegrowana z ConnectionManager.
    Pozwala synchronizować hostname, zapisywać i eksportować konfiguracje.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.device: Device | None = None
        self.conn_mgr = None  # przypisane z MainWindow

        main_layout = QVBoxLayout(self)
        main_layout.setAlignment(Qt.AlignTop)
        main_layout.setContentsMargins(20, 15, 20, 15)
        main_layout.setSpacing(15)

        # === Nagłówek ===
        title = QLabel("<h2>Global Settings</h2>")
        main_layout.addWidget(title)

        # === Hostname ===
        form = QFormLayout()
        self.hostname = QLineEdit()
        self.hostname.setPlaceholderText("np. Router1")
        form.addRow(QLabel("Hostname:"), self.hostname)
        main_layout.addLayout(form)

        # === NVRAM ===
        nvram_box = self._make_box(
            "NVRAM",
            [
                ("Erase", self._action_erase),
                ("Save", self._action_save),
            ],
        )
        main_layout.addWidget(nvram_box)

        # === Startup-config ===
        startup_box = self._make_box(
            "Startup Config",
            [
                ("Load...", self._action_load_startup),
                ("Export...", self._action_export_startup),
            ],
        )
        main_layout.addWidget(startup_box)

        # === Running-config ===
        running_box = self._make_box(
            "Running Config",
            [
                ("Export...", self._action_export_running),
                ("Merge...", self._action_merge_running),
            ],
        )
        main_layout.addWidget(running_box)

        # === Sync Configuration ===
        self.btn_sync = QPushButton("🔄 Sync Configuration")
        self.btn_sync.setToolTip(
            "Pobiera konfigurację z urządzenia i aktualizuje hostname."
        )
        self.btn_sync.clicked.connect(self._action_sync)
        main_layout.addWidget(self.btn_sync)

        # === Dolna konsola (log) ===
        self.console = QPlainTextEdit()
        self.console.setReadOnly(True)
        self.console.setPlaceholderText("Global operations log...")
        self.console.setStyleSheet("""
            QPlainTextEdit {
                background-color: #111;
                color: #0f0;
                font-family: monospace;
                font-size: 12px;
            }
        """)
        main_layout.addWidget(self.console, 2)

        # === Wypełniacz ===
        spacer = QSpacerItem(10, 10, QSizePolicy.Minimum, QSizePolicy.Expanding)
        main_layout.addItem(spacer)

    # ==============================================================
    #                    PUBLIC API
    # ==============================================================

    def bind_device(self, device: Device, conn_mgr):
        """Podpina aktualne urządzenie i ConnectionManager."""
        self.device = device
        self.conn_mgr = conn_mgr
        self._append_log(f"[INFO] Binded to {device.host}")

    # ==============================================================
    #                    PRZYCISKI (AKCJE)
    # ==============================================================

    def _action_sync(self):
        """Pobiera konfigurację i aktualizuje hostname."""
        if not self._check_ready():
            return
        try:
            output = self.conn_mgr.send_command(
                self.device, "show running-config | include hostname"
            )
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
        except Exception as e:
            self._append_log(f"[ERROR] {e}")
            QMessageBox.critical(self, "Błąd synchronizacji", str(e))

    def _action_save(self):
        """Zapisuje konfigurację w NVRAM (write memory)."""
        if not self._check_ready():
            return
        try:
            output = self.conn_mgr.send_command(self.device, "write memory")
            self._append_log(output)
            QMessageBox.information(self, "Zapisano", "Konfiguracja zapisana w NVRAM.")
        except Exception as e:
            self._append_log(f"[ERROR] {e}")
            QMessageBox.critical(self, "Błąd zapisu", str(e))

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
        try:
            output = self.conn_mgr.send_command(self.device, "write erase")
            self._append_log(output)
            QMessageBox.information(
                self,
                "Wykonano",
                "Urządzenie zresetowano do domyślnej konfiguracji (po reload).",
            )
        except Exception as e:
            self._append_log(f"[ERROR] {e}")
            QMessageBox.critical(self, "Błąd", str(e))

    def _action_load_startup(self):
        """Wczytuje startup-config (copy startup-config running-config)."""
        if not self._check_ready():
            return
        try:
            output = self.conn_mgr.send_command(
                self.device, "copy startup-config running-config"
            )
            self._append_log(output)
            QMessageBox.information(self, "Wczytano", "Startup-config został wczytany.")
        except Exception as e:
            self._append_log(f"[ERROR] {e}")
            QMessageBox.critical(self, "Błąd", str(e))

    def _action_export_startup(self):
        """Eksportuje startup-config do pliku."""
        if not self._check_ready():
            return
        try:
            output = self.conn_mgr.send_command(self.device, "show startup-config")
            filename, _ = QFileDialog.getSaveFileName(
                self, "Zapisz startup-config", "startup-config.txt"
            )
            if filename:
                with open(filename, "w") as f:
                    f.write(output)
                QMessageBox.information(
                    self, "Zapisano", f"Startup-config zapisany do {filename}"
                )
            self._append_log("[EXPORT] Startup config saved.")
        except Exception as e:
            self._append_log(f"[ERROR] {e}")
            QMessageBox.critical(self, "Błąd eksportu", str(e))

    def _action_export_running(self):
        """Eksportuje running-config do pliku."""
        if not self._check_ready():
            return
        try:
            output = self.conn_mgr.send_command(self.device, "show running-config")
            filename, _ = QFileDialog.getSaveFileName(
                self, "Zapisz running-config", "running-config.txt"
            )
            if filename:
                with open(filename, "w") as f:
                    f.write(output)
                QMessageBox.information(
                    self, "Zapisano", f"Running-config zapisany do {filename}"
                )
            self._append_log("[EXPORT] Running config saved.")
        except Exception as e:
            self._append_log(f"[ERROR] {e}")
            QMessageBox.critical(self, "Błąd eksportu", str(e))

    def _action_merge_running(self):
        """Łączy lokalny plik konfiguracyjny z running-config."""
        if not self._check_ready():
            return
        filename, _ = QFileDialog.getOpenFileName(
            self, "Wybierz plik konfiguracyjny", "", "Text Files (*.txt)"
        )
        if not filename:
            return
        try:
            with open(filename, "r") as f:
                lines = [line.strip() for line in f.readlines() if line.strip()]
            output = self.conn_mgr.send_config(self.device, lines)
            self._append_log(output)
            QMessageBox.information(
                self, "Wykonano", f"Plik {filename} został zaaplikowany do urządzenia."
            )
        except Exception as e:
            self._append_log(f"[ERROR] {e}")
            QMessageBox.critical(self, "Błąd merge", str(e))

    # ==============================================================
    #                    POMOCNICZE
    # ==============================================================

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
        self.console.appendPlainText(text.strip())

    # ==============================================================
    #                  API: export/import stanu
    # ==============================================================

    def export_state(self) -> dict:
        return {
            "hostname": self.hostname.text(),
            "console": self.console.toPlainText(),
        }

    def import_state(self, data: dict):
        self.hostname.setText(data.get("hostname", ""))
        self.console.setPlainText(data.get("console", ""))
