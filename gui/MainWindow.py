from PySide6.QtCore import Qt, QSize, QSettings
from PySide6.QtWidgets import (
    QMainWindow,
    QHBoxLayout,
    QVBoxLayout,
    QPushButton,
    QWidget,
    QScrollArea,
    QFrame,
    QLabel,
    QDialog,
    QFileDialog,
    QMessageBox,
    QStyle,
)
from gui.AddDeviceDialog import AddDeviceDialog
from DeviceList import DeviceList
from gui.SettingsDialog import SettingsDialog


class MainWindow(QMainWindow):
    def __init__(self, device_list: DeviceList):
        super().__init__()
        self.setWindowTitle("Lista urządzeń")
        self.resize(800, 500)

        self.device_list = device_list

        # === CENTRALNY WIDGET ===
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)

        # === LEWA STRONA: lista hostów + przycisk "+" ===
        left_panel = QVBoxLayout()

        btn_add = QPushButton("➕")
        btn_add.clicked.connect(self.add_device_dialog)
        left_panel.addWidget(btn_add)

        # NOWY PRZYCISK: wyczyść listę
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

        # === PRAWA STRONA: panel szczegółów ===
        self.detail_box = QFrame()
        self.detail_box.setFrameShape(QFrame.StyledPanel)
        detail_layout = QVBoxLayout(self.detail_box)

        self.label_host = QLabel("Host: -")
        self.label_username = QLabel("Użytkownik: -")
        self.label_type = QLabel("Typ urządzenia: -")

        for lbl in (self.label_host, self.label_username, self.label_type):
            lbl.setStyleSheet("font-size: 14px; margin: 5px;")
            detail_layout.addWidget(lbl)

        detail_layout.addStretch()
        main_layout.addWidget(self.detail_box, 2)

        # === MENU BAR ===
        menubar = self.menuBar()

        # Plik
        file_menu = menubar.addMenu("Plik")

        action_save = file_menu.addAction("Zapisz inventory")
        action_save.triggered.connect(self.save_inventory)

        action_load = file_menu.addAction("Wczytaj inventory")
        action_load.triggered.connect(self.load_inventory)

        # Ustawienia
        settings_action = menubar.addAction("Ustawienia")
        settings_action.triggered.connect(self.open_settings_dialog)

        self.settings = QSettings("WEEiA", "PyNetWizard")
        self.connection_type = self.settings.value("connection_type", "ssh")

        # załaduj początkowe urządzenia
        self.refresh_device_buttons()

    def refresh_device_buttons(self):
        # wyczyść layout
        for i in reversed(range(self.devices_layout.count())):
            widget = self.devices_layout.itemAt(i).widget()
            if widget is not None:
                widget.deleteLater()

        # dodaj przyciski na nowo
        for dev in self.device_list.devices:
            btn = QPushButton(dev["host"])
            btn.setStyleSheet("padding: 8px; font-size: 13px;")
            btn.setContextMenuPolicy(Qt.CustomContextMenu)

            # Lewy klik
            btn.clicked.connect(lambda _, d=dev: self.show_device_details(d))

            # Prawy klik
            def open_context_menu(pos, d=dev, b=btn):
                from PySide6.QtWidgets import QMenu

                menu = QMenu()
                remove_action = menu.addAction("Usuń urządzenie 🗑️")
                action = menu.exec_(b.mapToGlobal(pos))
                if action == remove_action:
                    self.remove_device(d["host"])

            btn.customContextMenuRequested.connect(open_context_menu)
            self.devices_layout.addWidget(btn)

        self.devices_layout.setAlignment(Qt.AlignTop)

    def add_device_dialog(self):
        dialog = AddDeviceDialog(self)
        if dialog.exec() == QDialog.Accepted:
            new_dev = dialog.get_data()
            if new_dev["host"]:  # minimalna walidacja
                self.device_list.add_device(**new_dev)
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
            self.show_device_details({})

    def show_device_details(self, device: dict | None):
        if not device:
            host = username = device_type = "-"
        else:
            try:
                host = device["host"]
                username = device["username"]
                device_type = device["device_type"]
            except KeyError as _:
                host = username = device_type = "-"

        self.label_host.setText(f"Host: {host}")
        self.label_username.setText(f"Użytkownik: {username}")
        self.label_type.setText(f"Typ urządzenia: {device_type}")

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

    # --- nowa metoda w MainWindow ---
    def open_settings_dialog(self):
        dialog = SettingsDialog(self, self.connection_type)
        if dialog.exec() == QDialog.Accepted:
            self.connection_type = dialog.get_connection_type()

    def closeEvent(self, event):
        self.settings.setValue("connection_type", self.connection_type)
        super().closeEvent(event)
