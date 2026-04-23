from PySide6.QtWidgets import (
    QVBoxLayout,
    QPushButton,
    QGroupBox,
    QFormLayout,
    QLineEdit,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QHBoxLayout,
    QMessageBox,
)

from gui.tabs.base_config_tab import BaseConfigTab
from gui.tabs.routing_validators import is_valid_ip, is_valid_netmask
from operations.operation import Operation
from operations.operation_type import OperationType
from services.parsed_config import ParsedConfig


class StaticRoutingTab(BaseConfigTab):
    """
    Zakladka tras statycznych.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.pending_ops: list[Operation] = []
        self._loading = False
        self._log_message = lambda _text: None

        layout = QVBoxLayout(self)

        form_box = QGroupBox("Dodaj / edytuj trasę statyczną")
        form_layout = QFormLayout(form_box)

        self.static_dest = QLineEdit()
        self.static_mask = QLineEdit()
        self.static_next_hop = QLineEdit()
        self.static_dest.setPlaceholderText("192.168.10.0")
        self.static_mask.setPlaceholderText("255.255.255.0")
        self.static_next_hop.setPlaceholderText("10.0.0.2")

        form_layout.addRow("Sieć docelowa:", self.static_dest)
        form_layout.addRow("Maska:", self.static_mask)
        form_layout.addRow("Następny hop:", self.static_next_hop)

        row = QHBoxLayout()
        btn_add = QPushButton("Dodaj")
        btn_update = QPushButton("Aktualizuj")
        btn_add.clicked.connect(self._on_static_add)
        btn_update.clicked.connect(self._on_static_update)
        row.addWidget(btn_add)
        row.addWidget(btn_update)
        form_layout.addRow(row)

        layout.addWidget(form_box)

        self.static_table = QTableWidget(0, 3)
        self.static_table.setHorizontalHeaderLabels(
            ["Sieć docelowa", "Maska", "Następny hop"]
        )
        self.static_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.static_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.static_table.setSelectionMode(QTableWidget.SingleSelection)
        self.static_table.itemSelectionChanged.connect(
            self._on_static_selection_changed
        )
        layout.addWidget(self.static_table, 1)

        btn_delete = QPushButton("Usuń trasę")
        btn_delete.clicked.connect(self._on_static_delete)
        row = QHBoxLayout()
        row.addWidget(btn_delete)
        row.addStretch()
        layout.addLayout(row)

    def set_logger(self, log_message):
        self._log_message = log_message or (lambda _text: None)

    def _append_log(self, text: str):
        self._log_message(text)

    def _get_static_selected_row(self):
        rows = self.static_table.selectionModel().selectedRows()
        return rows[0].row() if rows else None

    def _on_static_selection_changed(self):
        if self._loading:
            return
        row = self._get_static_selected_row()
        if row is None:
            return
        self.static_dest.setText(self.static_table.item(row, 0).text())
        self.static_mask.setText(self.static_table.item(row, 1).text())
        self.static_next_hop.setText(self.static_table.item(row, 2).text())

    def _on_static_add(self):
        dest = self.static_dest.text().strip()
        mask = self.static_mask.text().strip()
        nh = self.static_next_hop.text().strip()

        if not (is_valid_ip(dest) and is_valid_netmask(mask) and is_valid_ip(nh)):
            QMessageBox.warning(
                self, "Błąd", "Wprowadź poprawne Destination / Mask / Next Hop."
            )
            return

        for row in range(self.static_table.rowCount()):
            current_dest = self.static_table.item(row, 0).text()
            current_mask = self.static_table.item(row, 1).text()
            current_nh = self.static_table.item(row, 2).text()
            if current_dest == dest and current_mask == mask and current_nh == nh:
                QMessageBox.information(self, "Informacja", "Taka trasa już istnieje.")
                return

        row = self.static_table.rowCount()
        self.static_table.insertRow(row)
        self.static_table.setItem(row, 0, QTableWidgetItem(dest))
        self.static_table.setItem(row, 1, QTableWidgetItem(mask))
        self.static_table.setItem(row, 2, QTableWidgetItem(nh))

        self.pending_ops.append(
            Operation(
                OperationType.ADD_STATIC_ROUTE,
                dest=dest,
                mask=mask,
                nh=nh,
            )
        )
        self._append_log(f"[OP] add static route to {dest}")
        self.static_table.selectRow(row)

    def _on_static_update(self):
        row = self._get_static_selected_row()
        if row is None:
            QMessageBox.information(
                self, "Informacja", "Najpierw wybierz istniejącą trasę."
            )
            return

        dest = self.static_dest.text().strip()
        mask = self.static_mask.text().strip()
        nh = self.static_next_hop.text().strip()

        if not (is_valid_ip(dest) and is_valid_netmask(mask) and is_valid_ip(nh)):
            QMessageBox.warning(
                self, "Błąd", "Wprowadź poprawne Destination / Mask / Next Hop."
            )
            return

        old_dest = self.static_table.item(row, 0).text()
        old_mask = self.static_table.item(row, 1).text()
        old_nh = self.static_table.item(row, 2).text()

        if dest == old_dest and mask == old_mask and nh == old_nh:
            return

        self.pending_ops.append(
            Operation(
                OperationType.DEL_STATIC_ROUTE,
                dest=old_dest,
                mask=old_mask,
                nh=old_nh,
            )
        )
        self.pending_ops.append(
            Operation(
                OperationType.ADD_STATIC_ROUTE,
                dest=dest,
                mask=mask,
                nh=nh,
            )
        )
        self._append_log(f"[OP] update static route to {dest}")

        self.static_table.setItem(row, 0, QTableWidgetItem(dest))
        self.static_table.setItem(row, 1, QTableWidgetItem(mask))
        self.static_table.setItem(row, 2, QTableWidgetItem(nh))

    def _on_static_delete(self):
        row = self._get_static_selected_row()
        if row is None:
            QMessageBox.information(self, "Informacja", "Wybierz trasę do usunięcia.")
            return

        dest = self.static_table.item(row, 0).text()
        mask = self.static_table.item(row, 1).text()
        nh = self.static_table.item(row, 2).text()

        self.pending_ops.append(
            Operation(
                OperationType.DEL_STATIC_ROUTE,
                dest=dest,
                mask=mask,
                nh=nh,
            )
        )
        self._append_log(f"[OP] delete static route to {dest}")
        self.static_table.removeRow(row)

    def get_pending_operations(self, clear=False) -> list[Operation]:
        ops = list(self.pending_ops)
        if clear:
            self.pending_ops.clear()
        return ops

    def clear_pending_operations(self):
        self.pending_ops.clear()

    def export_state(self):
        rows = []
        for row in range(self.static_table.rowCount()):
            rows.append(
                [
                    self.static_table.item(row, 0).text(),
                    self.static_table.item(row, 1).text(),
                    self.static_table.item(row, 2).text(),
                ]
            )
        return {
            "routes": rows,
            "pending_ops": list(self.pending_ops),
        }

    def import_state(self, data):
        self._loading = True
        try:
            self.static_table.setRowCount(0)
            for route in data.get("routes", []):
                self._append_route_row(route)
            self.pending_ops = list(data.get("pending_ops", []))
        finally:
            self._loading = False

    def sync_from_config(self, conf: ParsedConfig):
        self._loading = True
        try:
            self.static_table.setRowCount(0)
            for route in conf.routing.static:
                self._append_route_row([route["dest"], route["mask"], route["nh"]])
            self.pending_ops.clear()
        finally:
            self._loading = False

    def _append_route_row(self, route):
        if len(route) < 3:
            return
        row = self.static_table.rowCount()
        self.static_table.insertRow(row)
        self.static_table.setItem(row, 0, QTableWidgetItem(route[0]))
        self.static_table.setItem(row, 1, QTableWidgetItem(route[1]))
        self.static_table.setItem(row, 2, QTableWidgetItem(route[2]))
