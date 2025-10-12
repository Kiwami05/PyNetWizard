# --- zmodyfikowana klasa SettingsDialog ---
from PySide6.QtWidgets import QDialog, QVBoxLayout, QComboBox, QLabel, QPushButton


class SettingsDialog(QDialog):
    def __init__(self, parent=None, current_type="ssh"):
        super().__init__(parent)
        self.setWindowTitle("Ustawienia")
        self.resize(250, 120)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Typ połączenia:"))

        self.combo = QComboBox()
        self.combo.addItems(["ssh", "telnet"])
        self.combo.setCurrentText(current_type)
        layout.addWidget(self.combo)

        btn_ok = QPushButton("OK")
        btn_ok.clicked.connect(self.accept)
        layout.addWidget(btn_ok)

    def get_connection_type(self):
        return self.combo.currentText()
