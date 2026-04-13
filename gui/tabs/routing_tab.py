from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QPushButton,
    QTabWidget,
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
)
import ipaddress

from platforms.vendor import Vendor
from operations.operation import Operation
from operations.operation_type import OperationType
from services.parsed_config import ParsedConfig


# ================================================================
#                 WALIDACJA IP / MASK / WILDCARD
# ================================================================


def is_valid_ip(ip: str) -> bool:
    try:
        ipaddress.ip_address(ip)
        return True
    except Exception:
        return False


def is_valid_netmask(mask: str) -> bool:
    try:
        parts = [int(p) for p in mask.split(".")]
        if len(parts) != 4:
            return False
        bits = "".join(f"{p:08b}" for p in parts)
        return "01" not in bits  # maska ciągła np. 11111000....
    except Exception:
        return False


def is_valid_wildcard(w: str) -> bool:
    try:
        parts = [int(p) for p in w.split(".")]
        if len(parts) != 4:
            return False
        for p in parts:
            if p < 0 or p > 255:
                return False
        return True
    except Exception:
        return False


def wildcard_to_mask(w: str) -> str:
    parts = [255 - int(p) for p in w.split(".")]
    return ".".join(str(p) for p in parts)


class RoutingTab(QWidget):
    """
    Pełna, działająca implementacja RoutingTab:
    - Static routing
    - RIP v2 (checkbox enable)
    - OSPF process 1
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        self.pending_ops: list[Operation] = []
        self._loading: bool = False  # blokuje eventy podczas sync/import
        self._log_message = lambda _text: None
        self.vendor: Vendor | None = None
        self._ospf_interfaces: list[str] = []
        self._rip_interfaces: list[str] = []

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 15, 20, 15)
        main_layout.setSpacing(10)

        # === Tytuł ===
        main_layout.addWidget(QLabel("<h2>Konfiguracja routingu</h2>"))

        # === Subtaba ===
        self.subtabs = QTabWidget()
        self.static_tab = self._make_static_tab()
        self.rip_tab = self._make_rip_tab()
        self.ospf_tab = self._make_ospf_tab()
        self.subtabs.addTab(self.static_tab, "Statyczny")
        self.subtabs.addTab(self.rip_tab, "RIP")
        self.subtabs.addTab(self.ospf_tab, "OSPF")
        main_layout.addWidget(self.subtabs, 4)

    def set_device_context(self, device):
        self.vendor = getattr(device, "vendor", None)
        self._apply_vendor_context()

    def _apply_vendor_context(self):
        if not hasattr(self, "ospf_stack"):
            return
        is_juniper = self.vendor == Vendor.JUNIPER
        self.ospf_stack.setCurrentWidget(
            self.ospf_juniper_page if is_juniper else self.ospf_cisco_page
        )
        if hasattr(self, "rip_stack"):
            self.rip_stack.setCurrentWidget(
                self.rip_juniper_page if is_juniper else self.rip_cisco_page
            )
        rip_index = self.subtabs.indexOf(self.rip_tab)
        if rip_index >= 0:
            self.subtabs.setTabToolTip(rip_index, "")

    def set_logger(self, log_message):
        self._log_message = log_message or (lambda _text: None)

    def _append_log(self, text: str):
        self._log_message(text)

    # ============================================================
    #                         STATIC
    # ============================================================

    def _make_static_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # --- Form ---
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

        # --- Table ---
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

        # --- Delete ---
        btn_delete = QPushButton("Usuń trasę")
        btn_delete.clicked.connect(self._on_static_delete)
        row = QHBoxLayout()
        row.addWidget(btn_delete)
        row.addStretch()
        layout.addLayout(row)

        return tab

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

        # walidacja
        if not (is_valid_ip(dest) and is_valid_netmask(mask) and is_valid_ip(nh)):
            QMessageBox.warning(
                self, "Błąd", "Wprowadź poprawne Destination / Mask / Next Hop."
            )
            return

        # sprawdź duplikat
        for r in range(self.static_table.rowCount()):
            d = self.static_table.item(r, 0).text()
            m = self.static_table.item(r, 1).text()
            n = self.static_table.item(r, 2).text()
            if d == dest and m == mask and n == nh:
                QMessageBox.information(self, "Informacja", "Taka trasa już istnieje.")
                return

        r = self.static_table.rowCount()
        self.static_table.insertRow(r)
        self.static_table.setItem(r, 0, QTableWidgetItem(dest))
        self.static_table.setItem(r, 1, QTableWidgetItem(mask))
        self.static_table.setItem(r, 2, QTableWidgetItem(nh))

        self.pending_ops.append(
            Operation(
                OperationType.ADD_STATIC_ROUTE,
                dest=dest,
                mask=mask,
                nh=nh,
            )
        )
        self._append_log(f"[OP] add static route to {dest}")
        self.static_table.selectRow(r)

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

    # ============================================================
    #                           RIP
    # ============================================================

    def _make_rip_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        self.rip_stack = QStackedWidget()
        self.rip_cisco_page = self._make_cisco_rip_page()
        self.rip_juniper_page = self._make_juniper_rip_page()
        self.rip_stack.addWidget(self.rip_cisco_page)
        self.rip_stack.addWidget(self.rip_juniper_page)
        layout.addWidget(self.rip_stack)
        return tab

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

        # Form add
        form = QGroupBox("Dodaj sieć RIP")
        f = QFormLayout(form)
        self.rip_net = QLineEdit()
        self.rip_net.setPlaceholderText("10.0.0.0")
        f.addRow("Sieć:", self.rip_net)

        btn_add = QPushButton("Dodaj")
        btn_add.clicked.connect(self._rip_add)
        btn_del = QPushButton("Usuń")
        btn_del.clicked.connect(self._rip_delete)
        row = QHBoxLayout()
        row.addWidget(btn_add)
        row.addWidget(btn_del)
        f.addRow(row)

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
        f = QFormLayout(form)

        self.junos_rip_group = QLineEdit()
        self.junos_rip_iface = QComboBox()
        self.junos_rip_iface.setEditable(True)
        self.junos_rip_group.setPlaceholderText("default")
        self.junos_rip_group.setText("default")
        self.junos_rip_iface.lineEdit().setPlaceholderText("ge-0/0/0.0")

        f.addRow("Grupa:", self.junos_rip_group)
        f.addRow("Interfejs:", self.junos_rip_iface)

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
        f.addRow(row)

        layout.addWidget(form)
        return page

    def _rip_selected_row(self):
        rows = self.rip_table.selectionModel().selectedRows()
        return rows[0].row() if rows else None

    def _rip_toggle(self, enabled: bool):
        if self._loading:
            return
        if enabled:
            self.pending_ops.append(
                Operation(
                    OperationType.ENABLE_RIP,
                )
            )
        else:
            self.pending_ops.append(
                Operation(
                    OperationType.DISABLE_RIP,
                )
            )
        self._append_log(f"[OP] turn RIP {'ON' if enabled else 'OFF'}")

    def _rip_add(self):
        net = self.rip_net.text().strip()

        if not is_valid_ip(net):
            QMessageBox.warning(self, "Błąd", "Niepoprawna sieć RIP.")
            return

        if not self.rip_enabled.isChecked():
            QMessageBox.warning(self, "Informacja", "Najpierw włącz RIP.")
            return

        # duplikaty
        for r in range(self.rip_table.rowCount()):
            if self.rip_table.item(r, 0).text() == net:
                QMessageBox.information(self, "Informacja", "Ta sieć już istnieje.")
                return

        r = self.rip_table.rowCount()
        self.rip_table.insertRow(r)
        self.rip_table.setItem(r, 0, QTableWidgetItem(net))
        self.pending_ops.append(
            Operation(
                OperationType.ADD_RIP_NETWORK,
                network=net,
            )
        )
        self._append_log(f"[OP] add {net} to RIP")
        self.rip_table.selectRow(r)
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
        self._append_log(f"[OP] delete {net} to RIP")
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

        for r in range(self.junos_rip_table.rowCount()):
            if (
                self.junos_rip_table.item(r, 0).text() == group
                and self.junos_rip_table.item(r, 1).text() == iface
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
        self._append_log(f"[OP] add {iface} to RIP group {group}")
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
        self._append_log(f"[OP] update RIP interface {iface}")

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
        self._append_log(f"[OP] delete {iface} from RIP group {group}")
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

    # ============================================================
    #                           OSPF
    # ============================================================

    def _make_ospf_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        self.ospf_stack = QStackedWidget()
        self.ospf_cisco_page = self._make_cisco_ospf_page()
        self.ospf_juniper_page = self._make_juniper_ospf_page()
        self.ospf_stack.addWidget(self.ospf_cisco_page)
        self.ospf_stack.addWidget(self.ospf_juniper_page)
        layout.addWidget(self.ospf_stack)
        return tab

    def _make_cisco_ospf_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)

        layout.addWidget(QLabel("<b>OSPF Cisco (proces 1)</b>"))

        # Table
        self.ospf_table = QTableWidget(0, 3)
        self.ospf_table.setHorizontalHeaderLabels(["Sieć", "Wildcard", "Obszar"])

        self.ospf_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.ospf_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.ospf_table.setSelectionMode(QTableWidget.SingleSelection)
        self.ospf_table.itemSelectionChanged.connect(self._ospf_selection)
        layout.addWidget(self.ospf_table, 1)

        # Form
        form = QGroupBox("Dodaj / edytuj sieć OSPF")
        f = QFormLayout(form)

        self.ospf_network = QLineEdit()
        self.ospf_wild = QLineEdit()
        self.ospf_area = QLineEdit()

        self.ospf_network.setPlaceholderText("192.168.0.0")
        self.ospf_wild.setPlaceholderText("0.0.0.255")
        self.ospf_area.setPlaceholderText("0")

        f.addRow("Sieć:", self.ospf_network)
        f.addRow("Wildcard:", self.ospf_wild)
        f.addRow("Obszar:", self.ospf_area)

        row = QHBoxLayout()
        btn_add = QPushButton("Dodaj")
        btn_update = QPushButton("Aktualizuj")

        btn_add.clicked.connect(self._on_ospf_add)
        btn_update.clicked.connect(self._on_ospf_update)

        row.addWidget(btn_add)
        row.addWidget(btn_update)
        f.addRow(row)
        btn_del = QPushButton("Usuń")
        btn_del.clicked.connect(self._ospf_delete)

        row = QHBoxLayout()
        row.addWidget(btn_add)
        row.addWidget(btn_del)
        f.addRow(row)

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
        f = QFormLayout(form)

        self.junos_ospf_area = QLineEdit()
        self.junos_ospf_iface = QComboBox()
        self.junos_ospf_iface.setEditable(True)
        self.junos_ospf_area.setPlaceholderText("0.0.0.0")
        self.junos_ospf_iface.lineEdit().setPlaceholderText("ge-0/0/0.0")

        f.addRow("Obszar:", self.junos_ospf_area)
        f.addRow("Interfejs:", self.junos_ospf_iface)

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
        f.addRow(row)

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
        wc = self.ospf_wild.text().strip()
        area = self.ospf_area.text().strip()

        if not (is_valid_ip(net) and is_valid_wildcard(wc)):
            QMessageBox.warning(self, "Błąd", "Niepoprawne Network / Wildcard.")
            return

        if not area.isdigit():
            QMessageBox.warning(self, "Błąd", "Pole obszaru musi być liczbą.")
            return

        # duplikaty
        for r in range(self.ospf_table.rowCount()):
            if (
                self.ospf_table.item(r, 0).text() == net
                and self.ospf_table.item(r, 1).text() == wc
                and self.ospf_table.item(r, 2).text() == area
            ):
                QMessageBox.information(
                    self, "Informacja", "Taki wpis OSPF już istnieje."
                )
                return

        r = self.ospf_table.rowCount()
        self.ospf_table.insertRow(r)
        self.ospf_table.setItem(r, 0, QTableWidgetItem(net))
        self.ospf_table.setItem(r, 1, QTableWidgetItem(wc))
        self.ospf_table.setItem(r, 2, QTableWidgetItem(area))

        self.pending_ops.append(
            Operation(
                OperationType.ADD_OSPF_NETWORK,
                process=1,
                network=net,
                wildcard=wc,
                area=area,
            )
        )
        self._append_log(f"[OP] add {net} to OSPF")
        self.ospf_table.selectRow(r)

    def _on_ospf_update(self):
        row = self._ospf_selected_row()
        if row is None:
            QMessageBox.information(
                self, "Informacja", "Wybierz wpis OSPF do aktualizacji."
            )
            return

        net = self.ospf_network.text().strip()
        wc = self.ospf_wild.text().strip()
        area = self.ospf_area.text().strip()

        if not (is_valid_ip(net) and is_valid_wildcard(wc)):
            QMessageBox.warning(self, "Błąd", "Niepoprawne Network / Wildcard.")
            return

        if not area.isdigit():
            QMessageBox.warning(self, "Błąd", "Pole obszaru musi być liczbą.")
            return

        old_net = self.ospf_table.item(row, 0).text()
        old_wc = self.ospf_table.item(row, 1).text()
        old_area = self.ospf_table.item(row, 2).text()

        if net == old_net and wc == old_wc and area == old_area:
            return

        self.pending_ops.append(
            Operation(
                OperationType.DEL_OSPF_NETWORK,
                process=1,
                network=old_net,
                wildcard=old_wc,
                area=old_area,
            )
        )
        self.pending_ops.append(
            Operation(
                OperationType.ADD_OSPF_NETWORK,
                process=1,
                network=net,
                wildcard=wc,
                area=area,
            )
        )
        self._append_log(f"[OP] update {net} to OSPF")

        self.ospf_table.setItem(row, 0, QTableWidgetItem(net))
        self.ospf_table.setItem(row, 1, QTableWidgetItem(wc))
        self.ospf_table.setItem(row, 2, QTableWidgetItem(area))

    def _ospf_delete(self):
        row = self._ospf_selected_row()
        if row is None:
            QMessageBox.information(
                self, "Informacja", "Wybierz wpis OSPF do usunięcia."
            )
            return

        net = self.ospf_table.item(row, 0).text()
        w = self.ospf_table.item(row, 1).text()
        area = self.ospf_table.item(row, 2).text()

        self.pending_ops.append(
            Operation(
                OperationType.DEL_OSPF_NETWORK,
                process=1,
                network=net,
                wildcard=w,
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

        for r in range(self.junos_ospf_table.rowCount()):
            if (
                self.junos_ospf_table.item(r, 0).text() == area
                and self.junos_ospf_table.item(r, 1).text() == iface
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
        for name in sorted(conf.interfaces.items.keys()):
            candidates = [name]
            if "." not in name:
                candidates.append(f"{name}.0")
            for candidate in candidates:
                if candidate not in interfaces:
                    interfaces.append(candidate)

        for r in range(self.junos_ospf_table.rowCount()):
            item = self.junos_ospf_table.item(r, 1)
            if item and item.text() not in interfaces:
                interfaces.append(item.text())

        self._ospf_interfaces = interfaces
        self.junos_ospf_iface.clear()
        self.junos_ospf_iface.addItems(interfaces)
        if selected:
            self._set_junos_ospf_iface(selected)

    def _refresh_junos_rip_interfaces(self, conf: ParsedConfig):
        selected = self._current_junos_rip_iface()
        interfaces: list[str] = []
        for name in sorted(conf.interfaces.items.keys()):
            candidates = [name]
            if "." not in name:
                candidates.append(f"{name}.0")
            for candidate in candidates:
                if candidate not in interfaces:
                    interfaces.append(candidate)

        for r in range(self.junos_rip_table.rowCount()):
            item = self.junos_rip_table.item(r, 1)
            if item and item.text() not in interfaces:
                interfaces.append(item.text())

        self._rip_interfaces = interfaces
        self.junos_rip_iface.clear()
        self.junos_rip_iface.addItems(interfaces)
        if selected:
            self._set_junos_rip_iface(selected)

    # ============================================================
    #                     BUFORY + IMPORT / EXPORT
    # ============================================================

    def get_pending_operations(self, clear=False) -> list[Operation]:
        ops = list(self.pending_ops)
        if clear:
            self.pending_ops.clear()
        return ops

    def clear_pending_operations(self):
        self.pending_ops.clear()

    def export_state(self):
        data = {
            "static": [],
            "rip_enabled": self.rip_enabled.isChecked(),
            "rip": [],
            "junos_rip": [],
            "ospf": [],
            "junos_ospf": [],
            "pending_ops": list(self.pending_ops),
        }

        # static
        for r in range(self.static_table.rowCount()):
            row = [
                self.static_table.item(r, 0).text(),
                self.static_table.item(r, 1).text(),
                self.static_table.item(r, 2).text(),
            ]
            data["static"].append(row)

        for r in range(self.rip_table.rowCount()):
            data["rip"].append(self.rip_table.item(r, 0).text())

        for r in range(self.junos_rip_table.rowCount()):
            data["junos_rip"].append(
                [
                    self.junos_rip_table.item(r, 0).text(),
                    self.junos_rip_table.item(r, 1).text(),
                ]
            )

        for r in range(self.ospf_table.rowCount()):
            data["ospf"].append(
                [
                    self.ospf_table.item(r, 0).text(),
                    self.ospf_table.item(r, 1).text(),
                    self.ospf_table.item(r, 2).text(),
                ]
            )

        for r in range(self.junos_ospf_table.rowCount()):
            data["junos_ospf"].append(
                [
                    self.junos_ospf_table.item(r, 0).text(),
                    self.junos_ospf_table.item(r, 1).text(),
                ]
            )

        return data

    def import_state(self, data):
        self._loading = True
        try:
            # static
            self.static_table.setRowCount(0)
            for row in data.get("static", []):
                r = self.static_table.rowCount()
                self.static_table.insertRow(r)
                self.static_table.setItem(r, 0, QTableWidgetItem(row[0]))
                self.static_table.setItem(r, 1, QTableWidgetItem(row[1]))
                self.static_table.setItem(r, 2, QTableWidgetItem(row[2]))

            # RIP
            self.rip_enabled.setChecked(data.get("rip_enabled", False))
            self.rip_table.setRowCount(0)
            for net in data.get("rip", []):
                r = self.rip_table.rowCount()
                self.rip_table.insertRow(r)
                self.rip_table.setItem(r, 0, QTableWidgetItem(net))

            self.junos_rip_table.setRowCount(0)
            for row in data.get("junos_rip", []):
                if len(row) < 2:
                    continue
                r = self.junos_rip_table.rowCount()
                self.junos_rip_table.insertRow(r)
                self.junos_rip_table.setItem(r, 0, QTableWidgetItem(row[0]))
                self.junos_rip_table.setItem(r, 1, QTableWidgetItem(row[1]))
                self._ensure_junos_rip_iface_option(row[1])

            # OSPF
            self.ospf_table.setRowCount(0)
            for row in data.get("ospf", []):
                r = self.ospf_table.rowCount()
                self.ospf_table.insertRow(r)
                for i in range(min(3, len(row))):
                    self.ospf_table.setItem(r, i, QTableWidgetItem(row[i]))

            self.junos_ospf_table.setRowCount(0)
            for row in data.get("junos_ospf", []):
                if len(row) < 2:
                    continue
                r = self.junos_ospf_table.rowCount()
                self.junos_ospf_table.insertRow(r)
                self.junos_ospf_table.setItem(r, 0, QTableWidgetItem(row[0]))
                self.junos_ospf_table.setItem(r, 1, QTableWidgetItem(row[1]))
                self._ensure_junos_ospf_iface_option(row[1])

            self.pending_ops = list(data.get("pending_ops", []))
        finally:
            self._loading = False

    # ============================================================
    #                     SYNC Z PARSED CONFIG
    # ============================================================

    def sync_from_config(self, conf: ParsedConfig):
        self._loading = True
        try:
            # static
            self.static_table.setRowCount(0)
            for r in conf.routing.static:
                dest, mask, nh = r["dest"], r["mask"], r["nh"]
                row = self.static_table.rowCount()
                self.static_table.insertRow(row)
                self.static_table.setItem(row, 0, QTableWidgetItem(dest))
                self.static_table.setItem(row, 1, QTableWidgetItem(mask))
                self.static_table.setItem(row, 2, QTableWidgetItem(nh))

            # RIP
            self.rip_table.setRowCount(0)
            self.junos_rip_table.setRowCount(0)
            for net in conf.routing.rip_networks:
                r = self.rip_table.rowCount()
                self.rip_table.insertRow(r)
                self.rip_table.setItem(r, 0, QTableWidgetItem(net))
            self.rip_enabled.setChecked(bool(conf.routing.rip_networks))

            for rip in getattr(conf.routing, "rip_interfaces", []):
                row = self.junos_rip_table.rowCount()
                self.junos_rip_table.insertRow(row)
                self.junos_rip_table.setItem(row, 0, QTableWidgetItem(rip["group"]))
                self.junos_rip_table.setItem(row, 1, QTableWidgetItem(rip["interface"]))
                self._ensure_junos_rip_iface_option(rip["interface"])

            # OSPF
            self.ospf_table.setRowCount(0)
            self.junos_ospf_table.setRowCount(0)
            for o in conf.routing.ospf:
                if o.get("type") == "interface":
                    row = self.junos_ospf_table.rowCount()
                    self.junos_ospf_table.insertRow(row)
                    self.junos_ospf_table.setItem(row, 0, QTableWidgetItem(o["area"]))
                    self.junos_ospf_table.setItem(
                        row, 1, QTableWidgetItem(o["interface"])
                    )
                    self._ensure_junos_ospf_iface_option(o["interface"])
                    continue

                if o.get("process") != "1":
                    continue
                row = self.ospf_table.rowCount()
                self.ospf_table.insertRow(row)
                self.ospf_table.setItem(row, 0, QTableWidgetItem(o["network"]))
                self.ospf_table.setItem(row, 1, QTableWidgetItem(o["wildcard"]))
                self.ospf_table.setItem(row, 2, QTableWidgetItem(o["area"]))

            self._refresh_junos_ospf_interfaces(conf)
            self._refresh_junos_rip_interfaces(conf)
            self.pending_ops.clear()
            self._append_log("[SYNC] Routing updated from running-config.")
        finally:
            self._loading = False
