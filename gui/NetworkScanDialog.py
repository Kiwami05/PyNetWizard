# gui/NetworkScanDialog.py
from PySide6.QtCore import Qt, QThread
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLineEdit,
    QLabel, QPushButton, QProgressBar, QMessageBox, QCheckBox
)
import os
from network_scanner import NetworkScanner

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
        self.resize(480, 170)
        self.results = []
        self.exclude_hosts = set(exclude_hosts or [])

        layout = QVBoxLayout(self)

        row = QHBoxLayout()
        row.addWidget(QLabel("Podsieć (np. 10.0.0.0/24):"))
        self.input_subnet = QLineEdit()
        self.input_subnet.setPlaceholderText("10.0.0.0/24")
        row.addWidget(self.input_subnet)
        layout.addLayout(row)

        self.checkbox_detailed = QCheckBox("Szczegółowy skan (dłużej, wymaga uprawnień)")
        privileged = is_privileged_user()
        self.checkbox_detailed.setEnabled(privileged)
        if not privileged:
            self.checkbox_detailed.setToolTip("Szczegółowy skan wymaga uprawnień administratora/root.")
        layout.addWidget(self.checkbox_detailed)

        # spinner zamiast progress bar procentowego
        self.progress = QProgressBar()
        self.progress.setAlignment(Qt.AlignCenter)
        self.progress.setTextVisible(False)
        layout.addWidget(self.progress)

        btn_row = QHBoxLayout()
        self.btn_scan = QPushButton("Skanuj")
        self.btn_cancel = QPushButton("Anuluj")
        self.btn_cancel.setEnabled(False)
        self.btn_close = QPushButton("Zamknij")
        self.btn_close.setEnabled(False)

        self.btn_scan.clicked.connect(self.start_scan)
        self.btn_cancel.clicked.connect(self.cancel_scan)
        self.btn_close.clicked.connect(self.close)

        btn_row.addWidget(self.btn_scan)
        btn_row.addWidget(self.btn_cancel)
        btn_row.addWidget(self.btn_close)
        layout.addLayout(btn_row)

        self.thread: QThread | None = None
        self.worker: NetworkScanner | None = None

    def start_scan(self):
        subnet = self.input_subnet.text().strip()
        if not subnet:
            QMessageBox.warning(self, "Błąd", "Podaj podsieć, np. 10.0.0.0/24")
            return

        self.btn_scan.setEnabled(False)
        self.btn_cancel.setEnabled(True)
        self.btn_close.setEnabled(False)
        self.progress.setRange(0, 0)  # spinner

        self.thread = QThread()
        self.worker = NetworkScanner(subnet=subnet, detailed=self.checkbox_detailed.isChecked(),
                                     exclude_hosts=list(self.exclude_hosts))
        self.worker.moveToThread(self.thread)

        self.thread.started.connect(self.worker.run)
        self.worker.progress.connect(lambda c, t: None)  # spinner nie wymaga progress
        self.worker.finished.connect(self.on_finished)
        self.worker.error.connect(self.on_error)
        self.worker.finished.connect(self.thread.quit)
        self.worker.error.connect(self.thread.quit)
        self.thread.finished.connect(self.thread.deleteLater)

        self.thread.start()

    def cancel_scan(self):
        if self.worker:
            self.worker.stop()
        self.btn_cancel.setEnabled(False)
        self.btn_close.setEnabled(True)

    def on_finished(self, results):
        self.results = results
        self.btn_cancel.setEnabled(False)
        self.btn_close.setEnabled(True)
        QMessageBox.information(self, "Skanowanie zakończone", f"Znaleziono {len(results)} nowych hostów (z pominięciem lokalnych i duplikatów).")
        self.accept()

    def on_error(self, message):
        QMessageBox.critical(self, "Błąd skanowania", message)
        self.reject()

    def get_results(self) -> list[dict]:
        return self.results
