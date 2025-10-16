from PySide6.QtCore import Qt, QThread
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLineEdit,
    QLabel, QPushButton, QProgressBar, QMessageBox, QCheckBox, QSpinBox
)
from network_scanner import NetworkScanner
import os, ipaddress

def is_privileged_user() -> bool:
    try:
        if os.name == "posix":
            return os.geteuid() == 0
    except Exception:
        pass
    try:
        if os.name == "nt":
            import ctypes
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        pass
    return False

class NetworkScanDialog(QDialog):
    def __init__(self, parent=None, exclude_hosts: list[str] | None = None):
        super().__init__(parent)
        self.setWindowTitle("Skanuj sieć")
        self.resize(480, 180)
        self.results = []
        self.exclude_hosts = set(exclude_hosts or [])
        self.scanning = False

        layout = QVBoxLayout(self)

        # --- sieć i maska ---
        row = QHBoxLayout()
        row.addWidget(QLabel("Sieć:"))
        self.input_network = QLineEdit()
        self.input_network.setPlaceholderText("np. 10.0.0.0")
        row.addWidget(self.input_network)

        row.addWidget(QLabel("Maska:"))
        self.input_mask = QSpinBox()
        self.input_mask.setRange(0, 32)
        self.input_mask.setValue(24)
        row.addWidget(self.input_mask)
        layout.addLayout(row)

        # --- checkbox szczegółowego skanu ---
        self.checkbox_detailed = QCheckBox("Szczegółowy skan (dłużej, wymaga uprawnień)")
        privileged = is_privileged_user()
        self.checkbox_detailed.setEnabled(privileged)
        if not privileged:
            self.checkbox_detailed.setToolTip("Szczegółowy skan wymaga uprawnień administratora/root.")
        layout.addWidget(self.checkbox_detailed)

        # --- spinner ---
        self.progress = QProgressBar()
        self.progress.setAlignment(Qt.AlignCenter)
        self.progress.setTextVisible(False)
        layout.addWidget(self.progress)

        # --- przyciski ---
        btn_row = QHBoxLayout()
        self.btn_scan = QPushButton("Skanuj")
        self.btn_cancel = QPushButton("Anuluj")
        self.btn_cancel.clicked.connect(self.cancel_scan)
        btn_row.addWidget(self.btn_scan)
        btn_row.addWidget(self.btn_cancel)
        layout.addLayout(btn_row)

        self.btn_scan.clicked.connect(self.start_scan)

        self.thread: QThread | None = None
        self.worker: NetworkScanner | None = None

    def start_scan(self):
        network = self.input_network.text().strip()
        mask = self.input_mask.value()
        try:
            ipaddress.IPv4Network(f"{network}/{mask}", strict=False)
        except ValueError:
            QMessageBox.warning(self, "Błąd", "Niepoprawna sieć lub maska")
            return

        subnet = f"{network}/{mask}"

        self.btn_scan.setEnabled(False)
        self.scanning = True
        self.progress.setRange(0, 0)  # spinner

        self.thread = QThread()
        self.worker = NetworkScanner(subnet=subnet, detailed=self.checkbox_detailed.isChecked(),
                                     exclude_hosts=list(self.exclude_hosts))
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.on_finished)
        self.worker.error.connect(self.on_error)
        self.worker.finished.connect(self.thread.quit)
        self.worker.error.connect(self.thread.quit)
        self.thread.finished.connect(self.cleanup_thread)
        self.thread.start()

    def cancel_scan(self):
        if self.scanning and self.worker:
            self.worker.stop()
        else:
            self.close()

    def cleanup_thread(self):
        if self.thread:
            self.thread.wait()
        self.btn_scan.setEnabled(True)
        self.scanning = False

    def on_finished(self, results):
        self.results = results
        self.scanning = False
        QMessageBox.information(self, "Skanowanie zakończone", f"Znaleziono {len(results)} hostów")
        self.accept()

    def on_error(self, message):
        self.scanning = False
        QMessageBox.critical(self, "Błąd skanowania", message)
        self.reject()

    def get_results(self) -> list[dict]:
        return self.results
