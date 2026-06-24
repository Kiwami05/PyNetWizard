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

from gui.tabs.base_config_tab import BaseConfigTab
from operations.operation import Operation
from operations.operation_type import OperationType
from services.parsed_config import ParsedConfig


class SRXPoliciesTab(BaseConfigTab):
    """
    Widok polityk Juniper SRX.

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

        form_box = QGroupBox("Dodaj / edytuj politykę")
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

        btn_add = QPushButton("Dodaj / aktualizuj politykę")
        btn_add.clicked.connect(self._add_or_update_policy)
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
        self.table.itemSelectionChanged.connect(self._on_table_selection_changed)
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

    def _table_text(self, row: int, col: int) -> str:
        item = self.table.item(row, col)
        return item.text() if item else ""

    def _row_policy(self, row: int) -> dict[str, str]:
        return {
            "name": self._table_text(row, self.COL_NAME),
            "from_zone": self._table_text(row, self.COL_FROM),
            "to_zone": self._table_text(row, self.COL_TO),
            "src": self._table_text(row, self.COL_SRC),
            "dst": self._table_text(row, self.COL_DST),
            "application": self._table_text(row, self.COL_APP),
            "action": self._table_text(row, self.COL_ACTION),
        }

    def _form_policy(self) -> dict[str, str] | None:
        policy = {
            "name": self.policy_name.text().strip(),
            "from_zone": self.from_zone.text().strip(),
            "to_zone": self.to_zone.text().strip(),
            "src": self.src_addr.text().strip() or "any",
            "dst": self.dst_addr.text().strip() or "any",
            "application": self.application.text().strip() or "any",
            "action": self.action.currentText(),
        }

        if not policy["name"] or not policy["from_zone"] or not policy["to_zone"]:
            QMessageBox.warning(
                self,
                "Błąd",
                "Podaj nazwę polityki oraz strefy from/to.",
            )
            return None

        return policy

    def _find_policy_row(
        self, name: str, from_zone: str, to_zone: str, exclude_row: int | None = None
    ) -> int | None:
        for row in range(self.table.rowCount()):
            if exclude_row is not None and row == exclude_row:
                continue
            if self._table_text(row, self.COL_NAME) != name:
                continue
            if self._table_text(row, self.COL_FROM) != from_zone:
                continue
            if self._table_text(row, self.COL_TO) != to_zone:
                continue
            return row
        return None

    def _set_policy_row(self, row: int, policy: dict[str, str]):
        values = [
            policy["name"],
            policy["from_zone"],
            policy["to_zone"],
            policy["src"],
            policy["dst"],
            policy["application"],
            policy["action"],
        ]
        for col, value in enumerate(values):
            self.table.setItem(row, col, QTableWidgetItem(value))

    def _append_add_policy_operation(self, policy: dict[str, str]):
        self.pending_ops.append(
            Operation(
                OperationType.ADD_SRX_POLICY,
                name=policy["name"],
                from_zone=policy["from_zone"],
                to_zone=policy["to_zone"],
                src=policy["src"],
                dst=policy["dst"],
                application=policy["application"],
                action=policy["action"],
            )
        )

    def _append_delete_policy_operation(self, policy: dict[str, str]):
        self.pending_ops.append(
            Operation(
                OperationType.DEL_SRX_POLICY,
                name=policy["name"],
                from_zone=policy["from_zone"],
                to_zone=policy["to_zone"],
            )
        )

    def _on_table_selection_changed(self):
        if self._loading:
            return

        row = self._selected_row()
        if row is None:
            return

        policy = self._row_policy(row)
        self.policy_name.setText(policy["name"])
        self.from_zone.setText(policy["from_zone"])
        self.to_zone.setText(policy["to_zone"])
        self.src_addr.setText(policy["src"])
        self.dst_addr.setText(policy["dst"])
        self.application.setText(policy["application"])

        action_index = self.action.findText(policy["action"])
        if action_index >= 0:
            self.action.setCurrentIndex(action_index)

    def _add_or_update_policy(self):
        policy = self._form_policy()
        if policy is None:
            return

        selected_row = self._selected_row()
        duplicate_row = self._find_policy_row(
            policy["name"],
            policy["from_zone"],
            policy["to_zone"],
            exclude_row=selected_row,
        )
        if duplicate_row is not None:
            QMessageBox.information(
                self,
                "Informacja",
                "Taka polityka już istnieje dla tych stref.",
            )
            return

        if selected_row is None:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self._set_policy_row(row, policy)
            self._append_add_policy_operation(policy)
            self._append_log(
                f"[OP] Dodano politykę SRX {policy['name']}: "
                f"{policy['from_zone']} -> {policy['to_zone']} ({policy['action']})"
            )
            return

        old_policy = self._row_policy(selected_row)
        if old_policy == policy:
            return

        self._append_delete_policy_operation(old_policy)
        self._append_add_policy_operation(policy)
        self._set_policy_row(selected_row, policy)
        self._append_log(
            f"[OP] Zaktualizowano politykę SRX {old_policy['name']}: "
            f"{old_policy['from_zone']} -> {old_policy['to_zone']}"
        )

    def _delete_policy(self):
        row = self._selected_row()
        if row is None:
            QMessageBox.information(
                self, "Informacja", "Wybierz politykę do usunięcia."
            )
            return

        policy = self._row_policy(row)

        self._append_delete_policy_operation(policy)
        self.table.removeRow(row)
        self._append_log(
            f"[OP] Usunięto politykę SRX {policy['name']}: "
            f"{policy['from_zone']} -> {policy['to_zone']}"
        )

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
        self._loading = True
        try:
            self.pending_ops.clear()
            self.table.setRowCount(0)
            for policy in conf.srx_policies.policies:
                row = self.table.rowCount()
                self.table.insertRow(row)
                values = [
                    policy.get("name", ""),
                    policy.get("from_zone", ""),
                    policy.get("to_zone", ""),
                    policy.get("src", ""),
                    policy.get("dst", ""),
                    policy.get("application", ""),
                    policy.get("action", ""),
                ]
                for col, value in enumerate(values):
                    self.table.setItem(row, col, QTableWidgetItem(value))
        finally:
            self._loading = False

        self._append_log(
            f"[SYNC] Polityki SRX: wczytano {self.table.rowCount()} polityk."
        )
