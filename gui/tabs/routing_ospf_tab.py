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
    QMessageBox,
    QStackedWidget,
    QComboBox,
    QWidget,
)

from gui.tabs.base_config_tab import BaseConfigTab
from gui.tabs.routing_validators import (
    is_valid_ip,
    is_valid_wildcard,
)
from operations.operation import Operation
from operations.operation_type import OperationType
from platforms.vendor import Vendor
from services.parsed_config import (
    ParsedConfig,
    iter_user_visible_interfaces,
    is_user_visible_interface,
)


class OSPFRoutingTab(BaseConfigTab):
    """
    Zakladka OSPF dla Cisco i Junos.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.pending_ops: list[Operation] = []
        self._loading = False
        self._log_message = lambda _text: None
        self.vendor: Vendor | None = None
        self._ospf_interfaces: list[str] = []

        layout = QVBoxLayout(self)

        self.ospf_stack = QStackedWidget()
        self.ospf_cisco_page = self._make_cisco_ospf_page()
        self.ospf_juniper_page = self._make_juniper_ospf_page()
        self.ospf_stack.addWidget(self.ospf_cisco_page)
        self.ospf_stack.addWidget(self.ospf_juniper_page)
        layout.addWidget(self.ospf_stack)

    def set_device_context(self, device):
        self.vendor = getattr(device, "vendor", None)
        self._apply_vendor_context()

    def _apply_vendor_context(self):
        is_juniper = self.vendor == Vendor.JUNIPER
        self.ospf_stack.setCurrentWidget(
            self.ospf_juniper_page if is_juniper else self.ospf_cisco_page
        )

    def set_logger(self, log_message):
        self._log_message = log_message or (lambda _text: None)

    def _append_log(self, text: str):
        self._log_message(text)

    def _make_cisco_ospf_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)

        layout.addWidget(QLabel("<b>OSPF Cisco (proces 1)</b>"))

        self.ospf_table = QTableWidget(0, 3)
        self.ospf_table.setHorizontalHeaderLabels(["Sieć", "Wildcard", "Obszar"])
        self.ospf_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.ospf_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.ospf_table.setSelectionMode(QTableWidget.SingleSelection)
        self.ospf_table.itemSelectionChanged.connect(self._ospf_selection)
        layout.addWidget(self.ospf_table, 1)

        form = QGroupBox("Dodaj / edytuj sieć OSPF")
        form_layout = QFormLayout(form)

        self.ospf_network = QLineEdit()
        self.ospf_wild = QLineEdit()
        self.ospf_area = QLineEdit()

        self.ospf_network.setPlaceholderText("192.168.0.0")
        self.ospf_wild.setPlaceholderText("0.0.0.255")
        self.ospf_area.setPlaceholderText("0")

        form_layout.addRow("Sieć:", self.ospf_network)
        form_layout.addRow("Wildcard:", self.ospf_wild)
        form_layout.addRow("Obszar:", self.ospf_area)

        btn_add = QPushButton("Dodaj")
        btn_update = QPushButton("Aktualizuj")
        btn_del = QPushButton("Usuń")

        btn_add.clicked.connect(self._on_ospf_add)
        btn_update.clicked.connect(self._on_ospf_update)
        btn_del.clicked.connect(self._ospf_delete)

        row = QHBoxLayout()
        row.addWidget(btn_add)
        row.addWidget(btn_update)
        row.addWidget(btn_del)
        form_layout.addRow(row)

        layout.addWidget(form)
        return page

    def _make_juniper_ospf_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)

        layout.addWidget(QLabel("<b>OSPF Juniper</b>"))

        self.junos_ospf_table = QTableWidget(0, 2)
        self.junos_ospf_table.setHorizontalHeaderLabels(["Obszar", "Interfejs"])
        self.junos_ospf_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch
        )
        self.junos_ospf_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.junos_ospf_table.setSelectionMode(QTableWidget.SingleSelection)
        self.junos_ospf_table.itemSelectionChanged.connect(self._junos_ospf_selection)
        layout.addWidget(self.junos_ospf_table, 1)

        form = QGroupBox("Dodaj / edytuj interfejs OSPF")
        form_layout = QFormLayout(form)

        self.junos_ospf_area = QLineEdit()
        self.junos_ospf_iface = QComboBox()
        self.junos_ospf_iface.setEditable(True)
        self.junos_ospf_area.setPlaceholderText("0.0.0.0")
        self.junos_ospf_iface.lineEdit().setPlaceholderText("ge-0/0/0.0")

        form_layout.addRow("Obszar:", self.junos_ospf_area)
        form_layout.addRow("Interfejs:", self.junos_ospf_iface)

        btn_add = QPushButton("Dodaj")
        btn_update = QPushButton("Aktualizuj")
        btn_del = QPushButton("Usuń")

        btn_add.clicked.connect(self._on_junos_ospf_add)
        btn_update.clicked.connect(self._on_junos_ospf_update)
        btn_del.clicked.connect(self._junos_ospf_delete)

        row = QHBoxLayout()
        row.addWidget(btn_add)
        row.addWidget(btn_update)
        row.addWidget(btn_del)
        form_layout.addRow(row)

        layout.addWidget(form)
        return page

    def _ospf_selected_row(self):
        rows = self.ospf_table.selectionModel().selectedRows()
        return rows[0].row() if rows else None

    def _ospf_selection(self):
        if self._loading:
            return
        row = self._ospf_selected_row()
        if row is None:
            return
        self.ospf_network.setText(self.ospf_table.item(row, 0).text())
        self.ospf_wild.setText(self.ospf_table.item(row, 1).text())
        self.ospf_area.setText(self.ospf_table.item(row, 2).text())

    def _on_ospf_add(self):
        net = self.ospf_network.text().strip()
        wildcard = self.ospf_wild.text().strip()
        area = self.ospf_area.text().strip()

        if not (is_valid_ip(net) and is_valid_wildcard(wildcard)):
            QMessageBox.warning(self, "Błąd", "Niepoprawne Network / Wildcard.")
            return

        if not area.isdigit():
            QMessageBox.warning(self, "Błąd", "Pole obszaru musi być liczbą.")
            return

        for row in range(self.ospf_table.rowCount()):
            if (
                self.ospf_table.item(row, 0).text() == net
                and self.ospf_table.item(row, 1).text() == wildcard
                and self.ospf_table.item(row, 2).text() == area
            ):
                QMessageBox.information(
                    self, "Informacja", "Taki wpis OSPF już istnieje."
                )
                return

        row = self.ospf_table.rowCount()
        self.ospf_table.insertRow(row)
        self.ospf_table.setItem(row, 0, QTableWidgetItem(net))
        self.ospf_table.setItem(row, 1, QTableWidgetItem(wildcard))
        self.ospf_table.setItem(row, 2, QTableWidgetItem(area))

        self.pending_ops.append(
            Operation(
                OperationType.ADD_OSPF_NETWORK,
                process=1,
                network=net,
                wildcard=wildcard,
                area=area,
            )
        )
        self._append_log(f"[OP] add {net} to OSPF")
        self.ospf_table.selectRow(row)

    def _on_ospf_update(self):
        row = self._ospf_selected_row()
        if row is None:
            QMessageBox.information(
                self, "Informacja", "Wybierz wpis OSPF do aktualizacji."
            )
            return

        net = self.ospf_network.text().strip()
        wildcard = self.ospf_wild.text().strip()
        area = self.ospf_area.text().strip()

        if not (is_valid_ip(net) and is_valid_wildcard(wildcard)):
            QMessageBox.warning(self, "Błąd", "Niepoprawne Network / Wildcard.")
            return

        if not area.isdigit():
            QMessageBox.warning(self, "Błąd", "Pole obszaru musi być liczbą.")
            return

        old_net = self.ospf_table.item(row, 0).text()
        old_wildcard = self.ospf_table.item(row, 1).text()
        old_area = self.ospf_table.item(row, 2).text()

        if net == old_net and wildcard == old_wildcard and area == old_area:
            return

        self.pending_ops.append(
            Operation(
                OperationType.DEL_OSPF_NETWORK,
                process=1,
                network=old_net,
                wildcard=old_wildcard,
                area=old_area,
            )
        )
        self.pending_ops.append(
            Operation(
                OperationType.ADD_OSPF_NETWORK,
                process=1,
                network=net,
                wildcard=wildcard,
                area=area,
            )
        )
        self._append_log(f"[OP] update {net} to OSPF")

        self.ospf_table.setItem(row, 0, QTableWidgetItem(net))
        self.ospf_table.setItem(row, 1, QTableWidgetItem(wildcard))
        self.ospf_table.setItem(row, 2, QTableWidgetItem(area))

    def _ospf_delete(self):
        row = self._ospf_selected_row()
        if row is None:
            QMessageBox.information(
                self, "Informacja", "Wybierz wpis OSPF do usunięcia."
            )
            return

        net = self.ospf_table.item(row, 0).text()
        wildcard = self.ospf_table.item(row, 1).text()
        area = self.ospf_table.item(row, 2).text()

        self.pending_ops.append(
            Operation(
                OperationType.DEL_OSPF_NETWORK,
                process=1,
                network=net,
                wildcard=wildcard,
                area=area,
            )
        )
        self._append_log(f"[OP] delete {net} from OSPF")
        self.ospf_table.removeRow(row)

    def _junos_ospf_selected_row(self):
        rows = self.junos_ospf_table.selectionModel().selectedRows()
        return rows[0].row() if rows else None

    def _junos_ospf_selection(self):
        if self._loading:
            return
        row = self._junos_ospf_selected_row()
        if row is None:
            return
        self.junos_ospf_area.setText(self.junos_ospf_table.item(row, 0).text())
        self._set_junos_ospf_iface(self.junos_ospf_table.item(row, 1).text())

    def _on_junos_ospf_add(self):
        area = self.junos_ospf_area.text().strip()
        iface = self._current_junos_ospf_iface()

        if not area or not iface:
            QMessageBox.warning(self, "Błąd", "Podaj obszar i interfejs OSPF.")
            return

        for row in range(self.junos_ospf_table.rowCount()):
            if (
                self.junos_ospf_table.item(row, 0).text() == area
                and self.junos_ospf_table.item(row, 1).text() == iface
            ):
                QMessageBox.information(
                    self, "Informacja", "Taki wpis OSPF już istnieje."
                )
                return

        row = self.junos_ospf_table.rowCount()
        self.junos_ospf_table.insertRow(row)
        self.junos_ospf_table.setItem(row, 0, QTableWidgetItem(area))
        self.junos_ospf_table.setItem(row, 1, QTableWidgetItem(iface))

        self.pending_ops.append(
            Operation(
                OperationType.ADD_OSPF_INTERFACE,
                area=area,
                interface=iface,
            )
        )
        self._append_log(f"[OP] add {iface} to OSPF area {area}")
        self.junos_ospf_table.selectRow(row)

    def _on_junos_ospf_update(self):
        row = self._junos_ospf_selected_row()
        if row is None:
            QMessageBox.information(
                self, "Informacja", "Wybierz wpis OSPF do aktualizacji."
            )
            return

        area = self.junos_ospf_area.text().strip()
        iface = self._current_junos_ospf_iface()
        if not area or not iface:
            QMessageBox.warning(self, "Błąd", "Podaj obszar i interfejs OSPF.")
            return

        old_area = self.junos_ospf_table.item(row, 0).text()
        old_iface = self.junos_ospf_table.item(row, 1).text()
        if area == old_area and iface == old_iface:
            return

        self.pending_ops.append(
            Operation(
                OperationType.DEL_OSPF_INTERFACE,
                area=old_area,
                interface=old_iface,
            )
        )
        self.pending_ops.append(
            Operation(
                OperationType.ADD_OSPF_INTERFACE,
                area=area,
                interface=iface,
            )
        )

        self.junos_ospf_table.setItem(row, 0, QTableWidgetItem(area))
        self.junos_ospf_table.setItem(row, 1, QTableWidgetItem(iface))
        self._append_log(f"[OP] update OSPF interface {iface}")

    def _junos_ospf_delete(self):
        row = self._junos_ospf_selected_row()
        if row is None:
            QMessageBox.information(
                self, "Informacja", "Wybierz wpis OSPF do usunięcia."
            )
            return

        area = self.junos_ospf_table.item(row, 0).text()
        iface = self.junos_ospf_table.item(row, 1).text()
        self.pending_ops.append(
            Operation(
                OperationType.DEL_OSPF_INTERFACE,
                area=area,
                interface=iface,
            )
        )
        self._append_log(f"[OP] delete {iface} from OSPF area {area}")
        self.junos_ospf_table.removeRow(row)

    def _current_junos_ospf_iface(self) -> str:
        return self.junos_ospf_iface.currentText().strip()

    def _set_junos_ospf_iface(self, iface: str):
        if not iface:
            self.junos_ospf_iface.setCurrentText("")
            return
        self._ensure_junos_ospf_iface_option(iface)
        self.junos_ospf_iface.setCurrentText(iface)

    def _ensure_junos_ospf_iface_option(self, iface: str):
        if not iface:
            return
        if self.junos_ospf_iface.findText(iface) == -1:
            self.junos_ospf_iface.addItem(iface)

    def _refresh_junos_ospf_interfaces(self, conf: ParsedConfig):
        selected = self._current_junos_ospf_iface()
        interfaces: list[str] = []
        for name, _data in sorted(iter_user_visible_interfaces(conf), key=lambda item: item[0]):
            candidates = [name]
            if "." not in name:
                candidates.append(f"{name}.0")
            for candidate in candidates:
                if candidate not in interfaces:
                    interfaces.append(candidate)

        for row in range(self.junos_ospf_table.rowCount()):
            item = self.junos_ospf_table.item(row, 1)
            if (
                item
                and item.text() not in interfaces
                and is_user_visible_interface(conf, item.text())
            ):
                interfaces.append(item.text())

        self._ospf_interfaces = interfaces
        self.junos_ospf_iface.clear()
        self.junos_ospf_iface.addItems(interfaces)
        if selected:
            self._set_junos_ospf_iface(selected)

    def get_pending_operations(self, clear=False) -> list[Operation]:
        ops = list(self.pending_ops)
        if clear:
            self.pending_ops.clear()
        return ops

    def clear_pending_operations(self):
        self.pending_ops.clear()

    def export_state(self):
        data = {
            "ospf": [],
            "junos_ospf": [],
            "pending_ops": list(self.pending_ops),
        }

        for row in range(self.ospf_table.rowCount()):
            data["ospf"].append(
                [
                    self.ospf_table.item(row, 0).text(),
                    self.ospf_table.item(row, 1).text(),
                    self.ospf_table.item(row, 2).text(),
                ]
            )

        for row in range(self.junos_ospf_table.rowCount()):
            data["junos_ospf"].append(
                [
                    self.junos_ospf_table.item(row, 0).text(),
                    self.junos_ospf_table.item(row, 1).text(),
                ]
            )

        return data

    def import_state(self, data):
        self._loading = True
        try:
            self.ospf_table.setRowCount(0)
            for item in data.get("ospf", []):
                row = self.ospf_table.rowCount()
                self.ospf_table.insertRow(row)
                for column in range(min(3, len(item))):
                    self.ospf_table.setItem(row, column, QTableWidgetItem(item[column]))

            self.junos_ospf_table.setRowCount(0)
            for item in data.get("junos_ospf", []):
                if len(item) < 2:
                    continue
                row = self.junos_ospf_table.rowCount()
                self.junos_ospf_table.insertRow(row)
                self.junos_ospf_table.setItem(row, 0, QTableWidgetItem(item[0]))
                self.junos_ospf_table.setItem(row, 1, QTableWidgetItem(item[1]))
                self._ensure_junos_ospf_iface_option(item[1])

            self.pending_ops = list(data.get("pending_ops", []))
        finally:
            self._loading = False

    def sync_from_config(self, conf: ParsedConfig):
        self._loading = True
        try:
            self.ospf_table.setRowCount(0)
            self.junos_ospf_table.setRowCount(0)

            for ospf in conf.routing.ospf:
                if ospf.get("type") == "interface":
                    row = self.junos_ospf_table.rowCount()
                    self.junos_ospf_table.insertRow(row)
                    self.junos_ospf_table.setItem(
                        row, 0, QTableWidgetItem(ospf["area"])
                    )
                    self.junos_ospf_table.setItem(
                        row, 1, QTableWidgetItem(ospf["interface"])
                    )
                    self._ensure_junos_ospf_iface_option(ospf["interface"])
                    continue

                if ospf.get("process") != "1":
                    continue
                row = self.ospf_table.rowCount()
                self.ospf_table.insertRow(row)
                self.ospf_table.setItem(row, 0, QTableWidgetItem(ospf["network"]))
                self.ospf_table.setItem(row, 1, QTableWidgetItem(ospf["wildcard"]))
                self.ospf_table.setItem(row, 2, QTableWidgetItem(ospf["area"]))

            self._refresh_junos_ospf_interfaces(conf)
            self.pending_ops.clear()
        finally:
            self._loading = False
