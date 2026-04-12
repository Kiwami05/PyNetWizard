from PySide6.QtWidgets import (
    QWidget,
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
    QComboBox,
    QMessageBox,
    QScrollArea,
)

from operations.Operation import Operation
from operations.OperationEnum import OperationEnum
from services.parsed_config import ParsedConfig


class SRXPoliciesTab(QWidget):
    """
    Minimalny, labowy widok polityk Juniper SRX.

    Zakladamy, ze strefy, adresy i aplikacje moga juz istniec na urzadzeniu
    albo zostana podane jako standardowe wartosci Junos, np. `any` lub
    `junos-https`.
    """

    COL_NAME = 0
    COL_FROM = 1
    COL_TO = 2
    COL_SRC = 3
    COL_DST = 4
    COL_APP = 5
    COL_ACTION = 6

    def __init__(self, parent=None):
        super().__init__(parent)
        self.pending_ops: list[Operation] = []
        self._loading = False
        self._log_message = lambda _text: None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        outer.addWidget(scroll)

        content = QWidget()
        scroll.setWidget(content)

        layout = QVBoxLayout(content)
        layout.setContentsMargins(20, 15, 20, 15)
        layout.setSpacing(10)

        layout.addWidget(QLabel("<h2>Polityki bezpieczeństwa Juniper SRX</h2>"))
        layout.addWidget(
            QLabel(
                "Minimalny tryb labowy: polityka między strefami z adresami i aplikacją."
            )
        )

        form_box = QGroupBox("Dodaj politykę")
        form = QFormLayout(form_box)

        self.policy_name = QLineEdit()
        self.from_zone = QLineEdit()
        self.to_zone = QLineEdit()
        self.src_addr = QLineEdit()
        self.dst_addr = QLineEdit()
        self.application = QLineEdit()
        self.action = QComboBox()
        self.action.addItems(["permit", "deny", "reject"])

        self.policy_name.setPlaceholderText("ALLOW-HTTPS")
        self.from_zone.setPlaceholderText("untrust")
        self.to_zone.setPlaceholderText("trust")
        self.src_addr.setPlaceholderText("any")
        self.dst_addr.setPlaceholderText("any lub WEB-SRV")
        self.application.setPlaceholderText("junos-https")

        form.addRow("Nazwa polityki:", self.policy_name)
        form.addRow("From zone:", self.from_zone)
        form.addRow("To zone:", self.to_zone)
        form.addRow("Source address:", self.src_addr)
        form.addRow("Destination address:", self.dst_addr)
        form.addRow("Application:", self.application)
        form.addRow("Akcja:", self.action)

        btn_add = QPushButton("Dodaj politykę")
        btn_add.clicked.connect(self._add_policy)
        form.addRow(btn_add)
        layout.addWidget(form_box)

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(
            [
                "Nazwa",
                "From",
                "To",
                "Źródło",
                "Cel",
                "Aplikacja",
                "Akcja",
            ]
        )
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        layout.addWidget(self.table, 1)

        row = QHBoxLayout()
        btn_delete = QPushButton("Usuń zaznaczoną politykę")
        btn_delete.clicked.connect(self._delete_policy)
        row.addWidget(btn_delete)
        row.addStretch()
        layout.addLayout(row)

    def set_logger(self, log_message):
        self._log_message = log_message or (lambda _text: None)

    def _append_log(self, text: str):
        self._log_message(text)

    def _selected_row(self) -> int | None:
        rows = self.table.selectionModel().selectedRows()
        return rows[0].row() if rows else None

    def _add_policy(self):
        name = self.policy_name.text().strip()
        from_zone = self.from_zone.text().strip()
        to_zone = self.to_zone.text().strip()
        src = self.src_addr.text().strip() or "any"
        dst = self.dst_addr.text().strip() or "any"
        application = self.application.text().strip() or "any"
        action = self.action.currentText()

        if not name or not from_zone or not to_zone:
            QMessageBox.warning(
                self,
                "Błąd",
                "Podaj nazwę polityki oraz strefy from/to.",
            )
            return

        for row in range(self.table.rowCount()):
            if (
                self.table.item(row, self.COL_NAME).text() == name
                and self.table.item(row, self.COL_FROM).text() == from_zone
                and self.table.item(row, self.COL_TO).text() == to_zone
            ):
                QMessageBox.information(
                    self,
                    "Informacja",
                    "Taka polityka już istnieje dla tych stref.",
                )
                return

        row = self.table.rowCount()
        self.table.insertRow(row)
        values = [name, from_zone, to_zone, src, dst, application, action]
        for col, value in enumerate(values):
            self.table.setItem(row, col, QTableWidgetItem(value))

        self.pending_ops.append(
            Operation(
                OperationEnum.ADD_SRX_POLICY,
                name=name,
                from_zone=from_zone,
                to_zone=to_zone,
                src=src,
                dst=dst,
                application=application,
                action=action,
            )
        )
        self._append_log(
            f"[OP] add SRX policy {name}: {from_zone} -> {to_zone} ({action})"
        )

    def _delete_policy(self):
        row = self._selected_row()
        if row is None:
            QMessageBox.information(
                self, "Informacja", "Wybierz politykę do usunięcia."
            )
            return

        name = self.table.item(row, self.COL_NAME).text()
        from_zone = self.table.item(row, self.COL_FROM).text()
        to_zone = self.table.item(row, self.COL_TO).text()

        self.pending_ops.append(
            Operation(
                OperationEnum.DEL_SRX_POLICY,
                name=name,
                from_zone=from_zone,
                to_zone=to_zone,
            )
        )
        self.table.removeRow(row)
        self._append_log(f"[OP] delete SRX policy {name}: {from_zone} -> {to_zone}")

    def get_pending_operations(self, clear=False) -> list[Operation]:
        ops = list(self.pending_ops)
        if clear:
            self.pending_ops.clear()
        return ops

    def clear_pending_operations(self):
        self.pending_ops.clear()

    def export_state(self):
        rows = []
        for row in range(self.table.rowCount()):
            rows.append(
                [
                    self.table.item(row, col).text()
                    for col in range(self.table.columnCount())
                ]
            )
        return {
            "rows": rows,
            "pending_ops": list(self.pending_ops),
        }

    def import_state(self, data):
        self._loading = True
        try:
            self.table.setRowCount(0)
            for values in data.get("rows", []):
                row = self.table.rowCount()
                self.table.insertRow(row)
                for col, value in enumerate(values[: self.table.columnCount()]):
                    self.table.setItem(row, col, QTableWidgetItem(value))
            self.pending_ops = list(data.get("pending_ops", []))
        finally:
            self._loading = False

    def sync_from_config(self, conf: ParsedConfig):
        self.pending_ops.clear()
        self._append_log(
            "[SYNC] SRX policies: parser polityk nie jest jeszcze częścią MVP."
        )
