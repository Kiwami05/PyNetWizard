from PySide6.QtWidgets import (
    QVBoxLayout,
    QLabel,
    QPushButton,
    QGroupBox,
    QFormLayout,
    QLineEdit,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QHBoxLayout,
    QCheckBox,
    QMessageBox,
    QStackedWidget,
    QComboBox,
    QWidget,
)

from gui.tabs.base_config_tab import BaseConfigTab
from gui.tabs.routing_validators import is_valid_ip
from operations.operation import Operation
from operations.operation_type import OperationType
from platforms.vendor import Vendor
from services.parsed_config import (
    ParsedConfig,
    iter_user_visible_interfaces,
    is_user_visible_interface,
)


class RIPRoutingTab(BaseConfigTab):
    """
    Zakladka RIP dla Cisco i Junos.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.pending_ops: list[Operation] = []
        self._loading = False
        self._log_message = lambda _text: None
        self.vendor: Vendor | None = None
        self._rip_interfaces: list[str] = []

        layout = QVBoxLayout(self)

        self.rip_stack = QStackedWidget()
        self.rip_cisco_page = self._make_cisco_rip_page()
        self.rip_juniper_page = self._make_juniper_rip_page()
        self.rip_stack.addWidget(self.rip_cisco_page)
        self.rip_stack.addWidget(self.rip_juniper_page)
        layout.addWidget(self.rip_stack)

    def set_device_context(self, device):
        self.vendor = getattr(device, "vendor", None)
        self._apply_vendor_context()

    def _apply_vendor_context(self):
        is_juniper = self.vendor == Vendor.JUNIPER
        self.rip_stack.setCurrentWidget(
            self.rip_juniper_page if is_juniper else self.rip_cisco_page
        )

    def set_logger(self, log_message):
        self._log_message = log_message or (lambda _text: None)

    def _append_log(self, text: str):
        self._log_message(text)

    def _make_cisco_rip_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)

        self.rip_enabled = QCheckBox("Włącz RIP v2")
        self.rip_enabled.toggled.connect(self._rip_toggle)
        layout.addWidget(self.rip_enabled)

        self.rip_table = QTableWidget(0, 1)
        self.rip_table.setHorizontalHeaderLabels(["Sieć"])
        self.rip_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.rip_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.rip_table.setSelectionMode(QTableWidget.SingleSelection)
        layout.addWidget(self.rip_table, 1)

        form = QGroupBox("Dodaj sieć RIP")
        form_layout = QFormLayout(form)
        self.rip_net = QLineEdit()
        self.rip_net.setPlaceholderText("10.0.0.0")
        form_layout.addRow("Sieć:", self.rip_net)

        btn_add = QPushButton("Dodaj")
        btn_add.clicked.connect(self._rip_add)
        btn_del = QPushButton("Usuń")
        btn_del.clicked.connect(self._rip_delete)
        row = QHBoxLayout()
        row.addWidget(btn_add)
        row.addWidget(btn_del)
        form_layout.addRow(row)

        layout.addWidget(form)
        return page

    def _make_juniper_rip_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)

        layout.addWidget(QLabel("<b>RIP Juniper</b>"))

        self.junos_rip_table = QTableWidget(0, 2)
        self.junos_rip_table.setHorizontalHeaderLabels(["Grupa", "Interfejs"])
        self.junos_rip_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch
        )
        self.junos_rip_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.junos_rip_table.setSelectionMode(QTableWidget.SingleSelection)
        self.junos_rip_table.itemSelectionChanged.connect(self._junos_rip_selection)
        layout.addWidget(self.junos_rip_table, 1)

        form = QGroupBox("Dodaj / edytuj interfejs RIP")
        form_layout = QFormLayout(form)

        self.junos_rip_group = QLineEdit()
        self.junos_rip_iface = QComboBox()
        self.junos_rip_iface.setEditable(True)
        self.junos_rip_group.setPlaceholderText("default")
        self.junos_rip_group.setText("default")
        self.junos_rip_iface.lineEdit().setPlaceholderText("ge-0/0/0.0")

        form_layout.addRow("Grupa:", self.junos_rip_group)
        form_layout.addRow("Interfejs:", self.junos_rip_iface)

        btn_add = QPushButton("Dodaj")
        btn_update = QPushButton("Aktualizuj")
        btn_del = QPushButton("Usuń")

        btn_add.clicked.connect(self._on_junos_rip_add)
        btn_update.clicked.connect(self._on_junos_rip_update)
        btn_del.clicked.connect(self._junos_rip_delete)

        row = QHBoxLayout()
        row.addWidget(btn_add)
        row.addWidget(btn_update)
        row.addWidget(btn_del)
        form_layout.addRow(row)

        layout.addWidget(form)
        return page

    def _rip_selected_row(self):
        rows = self.rip_table.selectionModel().selectedRows()
        return rows[0].row() if rows else None

    def _rip_toggle(self, enabled: bool):
        if self._loading:
            return
        if enabled:
            self.pending_ops.append(Operation(OperationType.ENABLE_RIP))
        else:
            self.pending_ops.append(Operation(OperationType.DISABLE_RIP))
        self._append_log(f"[OP] {'WŁĄCZONO' if enabled else 'WYŁĄCZONO'} RIP")

    def _rip_add(self):
        net = self.rip_net.text().strip()

        if not is_valid_ip(net):
            QMessageBox.warning(self, "Błąd", "Niepoprawna sieć RIP.")
            return

        if not self.rip_enabled.isChecked():
            QMessageBox.warning(self, "Informacja", "Najpierw włącz RIP.")
            return

        for row in range(self.rip_table.rowCount()):
            if self.rip_table.item(row, 0).text() == net:
                QMessageBox.information(self, "Informacja", "Ta sieć już istnieje.")
                return

        row = self.rip_table.rowCount()
        self.rip_table.insertRow(row)
        self.rip_table.setItem(row, 0, QTableWidgetItem(net))
        self.pending_ops.append(
            Operation(
                OperationType.ADD_RIP_NETWORK,
                network=net,
            )
        )
        self._append_log(f"[OP] Dodano {net} do RIP")
        self.rip_table.selectRow(row)
        self.rip_net.clear()

    def _rip_delete(self):
        row = self._rip_selected_row()
        if row is None:
            QMessageBox.information(self, "Informacja", "Wybierz sieć do usunięcia.")
            return
        net = self.rip_table.item(row, 0).text()
        self.pending_ops.append(
            Operation(
                OperationType.DEL_RIP_NETWORK,
                network=net,
            )
        )
        self._append_log(f"[OP] Usunięto {net} z RIP")
        self.rip_table.removeRow(row)

    def _junos_rip_selected_row(self):
        rows = self.junos_rip_table.selectionModel().selectedRows()
        return rows[0].row() if rows else None

    def _junos_rip_selection(self):
        if self._loading:
            return
        row = self._junos_rip_selected_row()
        if row is None:
            return
        self.junos_rip_group.setText(self.junos_rip_table.item(row, 0).text())
        self._set_junos_rip_iface(self.junos_rip_table.item(row, 1).text())

    def _on_junos_rip_add(self):
        group = self.junos_rip_group.text().strip() or "default"
        iface = self._current_junos_rip_iface()
        if not iface:
            QMessageBox.warning(self, "Błąd", "Wybierz interfejs RIP.")
            return

        for row in range(self.junos_rip_table.rowCount()):
            if (
                self.junos_rip_table.item(row, 0).text() == group
                and self.junos_rip_table.item(row, 1).text() == iface
            ):
                QMessageBox.information(
                    self, "Informacja", "Taki wpis RIP już istnieje."
                )
                return

        row = self.junos_rip_table.rowCount()
        self.junos_rip_table.insertRow(row)
        self.junos_rip_table.setItem(row, 0, QTableWidgetItem(group))
        self.junos_rip_table.setItem(row, 1, QTableWidgetItem(iface))
        self.pending_ops.append(
            Operation(
                OperationType.ADD_RIP_INTERFACE,
                group=group,
                interface=iface,
            )
        )
        self._append_log(f"[OP] Dodano {iface} do grupy RIP {group}")
        self.junos_rip_table.selectRow(row)

    def _on_junos_rip_update(self):
        row = self._junos_rip_selected_row()
        if row is None:
            QMessageBox.information(
                self, "Informacja", "Wybierz wpis RIP do aktualizacji."
            )
            return

        group = self.junos_rip_group.text().strip() or "default"
        iface = self._current_junos_rip_iface()
        if not iface:
            QMessageBox.warning(self, "Błąd", "Wybierz interfejs RIP.")
            return

        old_group = self.junos_rip_table.item(row, 0).text()
        old_iface = self.junos_rip_table.item(row, 1).text()
        if group == old_group and iface == old_iface:
            return

        self.pending_ops.append(
            Operation(
                OperationType.DEL_RIP_INTERFACE,
                group=old_group,
                interface=old_iface,
            )
        )
        self.pending_ops.append(
            Operation(
                OperationType.ADD_RIP_INTERFACE,
                group=group,
                interface=iface,
            )
        )
        self.junos_rip_table.setItem(row, 0, QTableWidgetItem(group))
        self.junos_rip_table.setItem(row, 1, QTableWidgetItem(iface))
        self._append_log(f"[OP] Zaktualizowano interfejs RIP {iface}")

    def _junos_rip_delete(self):
        row = self._junos_rip_selected_row()
        if row is None:
            QMessageBox.information(
                self, "Informacja", "Wybierz wpis RIP do usunięcia."
            )
            return

        group = self.junos_rip_table.item(row, 0).text()
        iface = self.junos_rip_table.item(row, 1).text()
        self.pending_ops.append(
            Operation(
                OperationType.DEL_RIP_INTERFACE,
                group=group,
                interface=iface,
            )
        )
        self._append_log(f"[OP] Usunięto {iface} z grupy RIP {group}")
        self.junos_rip_table.removeRow(row)

    def _current_junos_rip_iface(self) -> str:
        return self.junos_rip_iface.currentText().strip()

    def _set_junos_rip_iface(self, iface: str):
        if not iface:
            self.junos_rip_iface.setCurrentText("")
            return
        self._ensure_junos_rip_iface_option(iface)
        self.junos_rip_iface.setCurrentText(iface)

    def _ensure_junos_rip_iface_option(self, iface: str):
        if not iface:
            return
        if self.junos_rip_iface.findText(iface) == -1:
            self.junos_rip_iface.addItem(iface)

    def _refresh_junos_rip_interfaces(self, conf: ParsedConfig):
        selected = self._current_junos_rip_iface()
        interfaces: list[str] = []
        for name, _data in sorted(
            iter_user_visible_interfaces(conf), key=lambda item: item[0]
        ):
            candidates = [name]
            if "." not in name:
                candidates.append(f"{name}.0")
            for candidate in candidates:
                if candidate not in interfaces:
                    interfaces.append(candidate)

        for row in range(self.junos_rip_table.rowCount()):
            item = self.junos_rip_table.item(row, 1)
            if (
                item
                and item.text() not in interfaces
                and is_user_visible_interface(conf, item.text())
            ):
                interfaces.append(item.text())

        self._rip_interfaces = interfaces
        self.junos_rip_iface.clear()
        self.junos_rip_iface.addItems(interfaces)
        if selected:
            self._set_junos_rip_iface(selected)

    def get_pending_operations(self, clear=False) -> list[Operation]:
        ops = list(self.pending_ops)
        if clear:
            self.pending_ops.clear()
        return ops

    def clear_pending_operations(self):
        self.pending_ops.clear()

    def export_state(self):
        data = {
            "rip_enabled": self.rip_enabled.isChecked(),
            "rip": [],
            "junos_rip": [],
            "pending_ops": list(self.pending_ops),
        }

        for row in range(self.rip_table.rowCount()):
            data["rip"].append(self.rip_table.item(row, 0).text())

        for row in range(self.junos_rip_table.rowCount()):
            data["junos_rip"].append(
                [
                    self.junos_rip_table.item(row, 0).text(),
                    self.junos_rip_table.item(row, 1).text(),
                ]
            )

        return data

    def import_state(self, data):
        self._loading = True
        try:
            self.rip_enabled.setChecked(data.get("rip_enabled", False))
            self.rip_table.setRowCount(0)
            for net in data.get("rip", []):
                row = self.rip_table.rowCount()
                self.rip_table.insertRow(row)
                self.rip_table.setItem(row, 0, QTableWidgetItem(net))

            self.junos_rip_table.setRowCount(0)
            for item in data.get("junos_rip", []):
                if len(item) < 2:
                    continue
                row = self.junos_rip_table.rowCount()
                self.junos_rip_table.insertRow(row)
                self.junos_rip_table.setItem(row, 0, QTableWidgetItem(item[0]))
                self.junos_rip_table.setItem(row, 1, QTableWidgetItem(item[1]))
                self._ensure_junos_rip_iface_option(item[1])

            self.pending_ops = list(data.get("pending_ops", []))
        finally:
            self._loading = False

    def sync_from_config(self, conf: ParsedConfig):
        self._loading = True
        try:
            self.rip_table.setRowCount(0)
            self.junos_rip_table.setRowCount(0)

            for net in conf.routing.rip_networks:
                row = self.rip_table.rowCount()
                self.rip_table.insertRow(row)
                self.rip_table.setItem(row, 0, QTableWidgetItem(net))
            self.rip_enabled.setChecked(bool(conf.routing.rip_networks))

            for rip in getattr(conf.routing, "rip_interfaces", []):
                row = self.junos_rip_table.rowCount()
                self.junos_rip_table.insertRow(row)
                self.junos_rip_table.setItem(row, 0, QTableWidgetItem(rip["group"]))
                self.junos_rip_table.setItem(row, 1, QTableWidgetItem(rip["interface"]))
                self._ensure_junos_rip_iface_option(rip["interface"])

            self._refresh_junos_rip_interfaces(conf)
            self.pending_ops.clear()
        finally:
            self._loading = False
