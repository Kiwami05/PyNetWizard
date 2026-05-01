from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QComboBox,
    QLabel,
    QPushButton,
    QCheckBox,
    QSpinBox,
    QLineEdit,
)
from PySide6.QtCore import QSettings

from gui.localization import get_existing_directory


class SettingsDialog(QDialog):
    def __init__(self, parent=None, current_type="ssh"):
        super().__init__(parent)
        self.setWindowTitle("Ustawienia")
        self.resize(350, 300)

        self.settings = QSettings("WEEiA", "PyNetWizard")

        layout = QVBoxLayout(self)

        # Połączenie
        layout.addWidget(QLabel("<b>Połączenie</b>"))
        self.combo_type = QComboBox()
        self.combo_type.addItems(["ssh", "telnet"])
        self.combo_type.setCurrentText(current_type)
        layout.addWidget(QLabel("Typ połączenia:"))
        layout.addWidget(self.combo_type)

        self.spin_timeout = QSpinBox()
        self.spin_timeout.setRange(1, 120)
        self.spin_timeout.setValue(int(self.settings.value("timeout", 10)))
        layout.addWidget(QLabel("Timeout (sekundy):"))
        layout.addWidget(self.spin_timeout)

        self.chk_autosync = QCheckBox(
            "Automatycznie pobieraj konfigurację po dodaniu urządzenia"
        )
        self.chk_autosync.setChecked(self.settings.value("autosync", "false") == "true")
        layout.addWidget(self.chk_autosync)

        # Netmiko / logi
        layout.addWidget(QLabel("<b>Netmiko / logi</b>"))
        self.chk_verbose = QCheckBox("Tryb debugowania (verbose output)")
        self.chk_verbose.setChecked(self.settings.value("verbose", "false") == "true")
        layout.addWidget(self.chk_verbose)

        self.chk_persist_cisco = QCheckBox(
            "Cisco: zapisuj zmiany także do startup-config"
        )
        self.chk_persist_cisco.setChecked(
            self.settings.value("persist_cisco_config", "true") == "true"
        )
        layout.addWidget(self.chk_persist_cisco)

        log_layout = QHBoxLayout()
        self.edit_log_path = QLineEdit(self.settings.value("log_path", "./logs"))
        btn_browse = QPushButton("📂")
        btn_browse.clicked.connect(self.choose_log_folder)
        log_layout.addWidget(QLabel("Folder logów:"))
        log_layout.addWidget(self.edit_log_path)
        log_layout.addWidget(btn_browse)
        layout.addLayout(log_layout)

        # Przyciski
        btn_row = QHBoxLayout()
        btn_reset = QPushButton("Przywróć domyślne")
        btn_reset.clicked.connect(self.reset_defaults)
        btn_ok = QPushButton("OK")
        btn_ok.clicked.connect(self.save_and_close)
        btn_row.addWidget(btn_reset)
        btn_row.addStretch()
        btn_row.addWidget(btn_ok)
        layout.addLayout(btn_row)

    def choose_log_folder(self):
        folder = get_existing_directory(self, "Wybierz folder logów")
        if folder:
            self.edit_log_path.setText(folder)

    def reset_defaults(self):
        self.settings.clear()
        self.combo_type.setCurrentText("ssh")
        self.spin_timeout.setValue(10)
        self.chk_autosync.setChecked(False)
        self.chk_verbose.setChecked(False)
        self.chk_persist_cisco.setChecked(True)

    def save_and_close(self):
        """Zapisuje ustawienia w QSettings"""
        self.settings.setValue("connection_type", self.combo_type.currentText())
        self.settings.setValue("timeout", self.spin_timeout.value())
        self.settings.setValue(
            "autosync", "true" if self.chk_autosync.isChecked() else "false"
        )
        self.settings.setValue(
            "verbose", "true" if self.chk_verbose.isChecked() else "false"
        )
        self.settings.setValue(
            "persist_cisco_config",
            "true" if self.chk_persist_cisco.isChecked() else "false",
        )
        self.settings.setValue("log_path", self.edit_log_path.text())

        self.accept()

    def get_connection_type(self):
        return self.combo_type.currentText()
