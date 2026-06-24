from PySide6.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QLineEdit,
    QFormLayout,
    QGroupBox,
    QMessageBox,
)
from PySide6.QtCore import Qt

from gui.dialogs.message_box import ask_yes_no
from gui.tabs.base_config_tab import BaseConfigTab
from operations.operation import Operation
from operations.operation_type import OperationType
from services.parsed_config import ParsedConfig


class VLANsTab(BaseConfigTab):
    """
    Tab VLAN-ów
    - tylko dodawanie / modyfikacja / usuwanie VLANów,
    - przypisywanie portów odbywa się w SwitchInterfacesTab,
    - kliknięcie w wiersz wypełnia pola VLAN ID / Name,
    - zmiana ID realizowana jako: no vlan OLD + vlan NEW (+ name ...),
    - generuje pending_ops oraz log w dolnej konsoli.
    """

    COL_ID = 0
    COL_NAME = 1
    COL_PORTS = 2  # tylko do wyświetlania (read-only), porty z ParsedConfig

    def __init__(self, parent=None):
        super().__init__(parent)

        self.pending_ops: list[Operation] = []
        self._log_message = lambda _text: None

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 15, 20, 15)
        main_layout.setSpacing(10)

        # Nagłówek
        main_layout.addWidget(QLabel("<h2>Konfiguracja VLAN-ów</h2>"))

        # Sekcja dodawania / edycji VLAN-u
        add_box = QGroupBox("Dodaj / edytuj VLAN")
        form = QFormLayout(add_box)
        self.vlan_id = QLineEdit()
        self.vlan_name = QLineEdit()
        self.vlan_id.setPlaceholderText("np. 10")
        self.vlan_name.setPlaceholderText("np. Zarządzanie")
        self.vlan_id.setToolTip(
            "Numer VLAN (1–4094). Zmiana ID usuwa stary VLAN i tworzy nowy."
        )
        self.vlan_name.setToolTip("Opcjonalna nazwa VLAN-u.")

        self.btn_add_update = QPushButton("Dodaj / aktualizuj VLAN")
        self.btn_add_update.clicked.connect(self._on_add_update_vlan)

        form.addRow("VLAN ID:", self.vlan_id)
        form.addRow("Nazwa:", self.vlan_name)
        form.addRow(self.btn_add_update)
        main_layout.addWidget(add_box)

        # Tabela VLAN-ów
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["VLAN ID", "Nazwa", "Porty"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.itemSelectionChanged.connect(self._on_table_selection_changed)
        main_layout.addWidget(self.table, 4)

        # Przyciski operacyjne
        btn_row = QHBoxLayout()
        self.btn_delete = QPushButton("Usuń VLAN")
        self.btn_delete.clicked.connect(self._on_delete_vlan)
        btn_row.addWidget(self.btn_delete)
        btn_row.addStretch()
        main_layout.addLayout(btn_row)

    def set_logger(self, log_message):
        self._log_message = log_message or (lambda _text: None)

    def _append_console(self, text: str):
        self._log_message(text.rstrip())

    def _find_vlan_row_by_id(self, vlan_id: str):
        for row in range(self.table.rowCount()):
            item = self.table.item(row, self.COL_ID)
            if item and item.text() == vlan_id:
                return row
        return None

    def _get_selected_row(self):
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return None
        return rows[0].row()

    def _validate_vlan_id(self, vlan_id: str) -> bool:
        if not vlan_id.strip():
            QMessageBox.warning(self, "Błąd", "Pole VLAN ID jest wymagane.")
            return False
        if not vlan_id.isdigit():
            QMessageBox.warning(self, "Błąd", "VLAN ID musi być liczbą całkowitą.")
            return False
        vid = int(vlan_id)
        if vid < 1 or vid > 4094:
            QMessageBox.warning(self, "Błąd", "VLAN ID musi być w zakresie 1–4094.")
            return False
        return True

    def _on_table_selection_changed(self):
        row = self._get_selected_row()
        if row is None:
            return
        id_item = self.table.item(row, self.COL_ID)
        name_item = self.table.item(row, self.COL_NAME)
        vlan_id = id_item.text() if id_item else ""
        vlan_name = name_item.text() if name_item else ""
        # Wypełnij pola formularza
        self.vlan_id.setText(vlan_id)
        self.vlan_name.setText(vlan_name)

    def _on_add_update_vlan(self):
        new_id = self.vlan_id.text().strip()
        new_name = self.vlan_name.text().strip()

        if not self._validate_vlan_id(new_id):
            return

        selected_row = self._get_selected_row()

        if selected_row is None:
            # Brak zaznaczenia — traktujemy jako dodanie nowego VLAN-u
            self._create_new_vlan(new_id, new_name)
        else:
            # Zaznaczony istniejący VLAN — modyfikacja (ID i/lub nazwy)
            self._update_existing_vlan(selected_row, new_id, new_name)

    def _create_new_vlan(self, vlan_id: str, name: str):
        # Sprawdź, czy VLAN o takim ID już istnieje
        existing_row = self._find_vlan_row_by_id(vlan_id)
        if existing_row is not None:
            QMessageBox.warning(
                self,
                "Błąd",
                f"VLAN {vlan_id} już istnieje. Zaznacz go w tabeli, aby go edytować.",
            )
            return

        # Dodaj do tabeli
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, self.COL_ID, QTableWidgetItem(vlan_id))
        self.table.setItem(row, self.COL_NAME, QTableWidgetItem(name))
        # Ports zostawiamy pusty
        self.table.setItem(row, self.COL_PORTS, QTableWidgetItem(""))

        # Pending commands
        self._append_console(f"vlan {vlan_id}")
        if name:
            self._append_console(f" name {name}")
        self._append_console(" exit\n")

        self.pending_ops.append(
            Operation(
                OperationType.CREATE_VLAN,
                vlan_id=int(vlan_id),
                name=name or None,
            )
        )

    def _update_existing_vlan(self, row: int, new_id: str, new_name: str):
        id_item = self.table.item(row, self.COL_ID)
        name_item = self.table.item(row, self.COL_NAME)
        old_id = id_item.text() if id_item else ""
        old_name = name_item.text() if name_item else ""

        # VLAN 1 — nie wolno zmieniać ID ani usuwać, ale nazwę można zmienić
        if old_id == "1" and new_id != "1":
            QMessageBox.warning(
                self,
                "Błąd",
                "VLAN 1 nie może mieć zmienionego ID.",
            )
            self.vlan_id.setText(old_id)
            return

        # Jeśli ID się zmienia — wariant A: no vlan OLD + vlan NEW
        if new_id != old_id:
            # sprawdź, czy new_id nie koliduje z innym VLAN-em
            existing_row = self._find_vlan_row_by_id(new_id)
            if existing_row is not None and existing_row != row:
                QMessageBox.warning(
                    self,
                    "Błąd",
                    f"VLAN {new_id} już istnieje. Wybierz inne ID lub edytuj istniejący VLAN.",
                )
                self.vlan_id.setText(old_id)
                return

            # Komendy
            self.pending_ops.append(
                Operation(
                    OperationType.DELETE_VLAN,
                    vlan_id=int(old_id),
                    vlan_name=old_name or None,
                )
            )
            self.pending_ops.append(
                Operation(
                    OperationType.CREATE_VLAN,
                    vlan_id=int(new_id),
                    name=new_name or None,
                )
            )

            # Aktualizacja tabeli
            id_item.setText(new_id)
            name_item.setText(new_name)

        else:
            # ID bez zmian. Sprawdzamy, czy nazwa się zmieniła
            if new_name == old_name:
                # nic się nie zmieniło
                return

            self.pending_ops.append(
                Operation(
                    OperationType.RENAME_VLAN,
                    vlan_id=int(old_id),
                    name=new_name or None,
                    old_name=old_name or None,
                )
            )

            name_item.setText(new_name)

    def _on_delete_vlan(self):
        row = self._get_selected_row()
        if row is None:
            QMessageBox.information(self, "Informacja", "Wybierz VLAN do usunięcia.")
            return

        id_item = self.table.item(row, self.COL_ID)
        vlan_id = id_item.text() if id_item else ""

        if vlan_id == "1":
            QMessageBox.warning(self, "Błąd", "VLAN 1 nie może być usunięty.")
            return

        # Potwierdzenie
        reply = ask_yes_no(
            self,
            "Potwierdzenie",
            f"Czy na pewno chcesz usunąć VLAN {vlan_id}?",
        )
        if reply != QMessageBox.Yes:
            return

        self.pending_ops.append(
            Operation(
                OperationType.DELETE_VLAN,
                vlan_id=int(vlan_id),
                vlan_name=(
                    self.table.item(row, self.COL_NAME).text()
                    if self.table.item(row, self.COL_NAME)
                    else None
                )
                or None,
            )
        )

        # Usunięcie z tabeli
        self.table.removeRow(row)

        # Wyczyść pola formularza, jeśli wczytano usunięty
        self.vlan_id.clear()
        self.vlan_name.clear()

    def get_pending_operations(self, clear: bool = False) -> list[Operation]:
        ops = list(self.pending_ops)
        if clear:
            self.pending_ops.clear()
        return ops

    def clear_pending_operations(self):
        self.pending_ops.clear()

    def export_state(self):
        rows = []
        for r in range(self.table.rowCount()):
            row = []
            for c in range(self.table.columnCount()):
                item = self.table.item(r, c)
                row.append(item.text() if item else "")
            rows.append(row)
        return {
            "rows": rows,
            "pending_ops": list(self.pending_ops),
        }

    def import_state(self, data):
        self.table.setRowCount(0)
        for row in data.get("rows", []):
            r = self.table.rowCount()
            self.table.insertRow(r)
            for c, val in enumerate(row):
                self.table.setItem(r, c, QTableWidgetItem(val))
        self.pending_ops = list(data.get("pending_ops", []))

    def sync_from_config(self, conf: ParsedConfig):
        """
        Wypełnia tabelę VLAN-ami z ParsedConfig.
        Ports są tylko do podglądu (read-only).
        """
        self.table.setRowCount(0)

        # posortuj po numerze VLAN-u (string -> int)
        vids = sorted(conf.vlans.items.keys(), key=lambda x: int(x))

        for vid in vids:
            v = conf.vlans.items[vid]
            name = v.get("name", "")
            ports = ", ".join(v.get("ports", []))

            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.setItem(r, self.COL_ID, QTableWidgetItem(vid))
            self.table.setItem(r, self.COL_NAME, QTableWidgetItem(name))
            ports_item = QTableWidgetItem(ports)
            ports_item.setFlags(ports_item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(r, self.COL_PORTS, ports_item)

        self.pending_ops.clear()
        self._append_console("[SYNC] VLANy zaktualizowane z bieżącą konfiguracją.")
