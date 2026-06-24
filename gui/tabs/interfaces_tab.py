from PySide6.QtWidgets import (
    QVBoxLayout,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QLineEdit,
    QCheckBox,
    QSpinBox,
)
from PySide6.QtCore import Qt

import ipaddress

from operations.operation import Operation
from operations.operation_type import OperationType
from gui.tabs.base_config_tab import BaseConfigTab
from services.parsed_config import ParsedConfig, iter_user_visible_interfaces


def is_valid_ip(addr: str) -> bool:
    try:
        ipaddress.ip_address(addr)
        return True
    except ValueError:
        return False


def set_error_style(widget, message: str):
    widget.setToolTip(message)
    widget.setStyleSheet("border: 1px solid red;")


def clear_error_style(widget):
    widget.setToolTip("")
    widget.setStyleSheet("")


def cidr_to_mask(cidr: int) -> str:
    cidr = max(0, min(32, int(cidr)))
    bits = "1" * cidr + "0" * (32 - cidr)
    return ".".join(str(int(bits[i : i + 8], 2)) for i in range(0, 32, 8))


def mask_to_cidr(mask: str) -> int:
    try:
        parts = [int(p) for p in mask.split(".")]
        if len(parts) != 4 or any(p < 0 or p > 255 for p in parts):
            return 0
        bits = "".join(f"{p:08b}" for p in parts)
        if "01" in bits:  # maski muszą mieć blok 1...10...0
            return 0
        return bits.count("1")
    except (TypeError, ValueError):
        return 0


class InterfacesTab(BaseConfigTab):
    """
    Bazowy tab interfejsów (bez trybu portu).
    - tabela jest jedynym miejscem edycji,
    - zmiany generują pending commands,
    - maska jako CIDR, ale do IOS leci w formacie kropkowym.
    """

    COL_NAME = 0
    COL_DESC = 1
    COL_IP = 2
    COL_MASK = 3
    COL_STATUS = 4
    _BASELINE_ROLE = Qt.UserRole

    def __init__(self, parent=None):
        super().__init__(parent)

        self.pending_ops: list[Operation] = []
        self._loading: bool = False  # blokuje eventy podczas sync/import
        self._log_message = lambda _text: None

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 15, 20, 15)
        main_layout.setSpacing(10)

        main_layout.addWidget(QLabel("<h2>Konfiguracja interfejsów</h2>"))

        # Tabela interfejsów
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            ["Nazwa", "Opis", "Adres IP", "Maska (/CIDR)", "Status"]
        )
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        main_layout.addWidget(self.table, 4)

    def set_logger(self, log_message):
        self._log_message = log_message or (lambda _text: None)

    def _append_log(self, text: str):
        self._log_message(text)

    def _create_interface_row(self, name, desc, ip, cidr_str, status):
        row = self.table.rowCount()
        self.table.insertRow(row)

        # Nazwa interfejsu
        item_name = QTableWidgetItem(name)
        item_name.setFlags(item_name.flags() & ~Qt.ItemIsEditable)
        item_name.setData(
            self._BASELINE_ROLE,
            {
                "description": desc,
                "ip": ip,
                "cidr": int(cidr_str),
                "status": status.lower() != "down",
            },
        )
        self.table.setItem(row, self.COL_NAME, item_name)

        # Opis
        edit_desc = QLineEdit(desc)
        edit_desc.setToolTip("Opis interfejsu (opcjonalny).")
        edit_desc.setProperty("iface", name)
        edit_desc.editingFinished.connect(self._on_desc_changed)
        self.table.setCellWidget(row, self.COL_DESC, edit_desc)

        # IP
        edit_ip = QLineEdit(ip)
        edit_ip.setToolTip("Adres IPv4 (np. 192.168.1.1).")
        edit_ip.setProperty("iface", name)
        edit_ip.editingFinished.connect(self._on_ip_changed)
        self.table.setCellWidget(row, self.COL_IP, edit_ip)

        # Maska (CIDR)
        spin_mask = QSpinBox()
        spin_mask.setRange(0, 32)
        spin_mask.setValue(int(cidr_str))
        spin_mask.setToolTip(
            "Maska w formacie CIDR (0–32). Do IOS trafia maska kropkowa."
        )
        spin_mask.setProperty("iface", name)
        spin_mask.editingFinished.connect(self._on_mask_changed)
        self.table.setCellWidget(row, self.COL_MASK, spin_mask)

        # Status
        chk_status = QCheckBox("up")
        chk_status.setToolTip(
            "Stan interfejsu: zaznaczone = up (no shutdown), odznaczone = down (shutdown)."
        )
        chk_status.setChecked(status.lower() != "down")
        chk_status.setProperty("iface", name)
        chk_status.toggled.connect(self._on_status_changed)
        self.table.setCellWidget(row, self.COL_STATUS, chk_status)

    def _find_row(self, iface):
        for r in range(self.table.rowCount()):
            item = self.table.item(r, self.COL_NAME)
            if item and item.text() == iface:
                return r
        return -1

    def _baseline_for_iface(self, iface: str) -> dict:
        row = self._find_row(iface)
        if row == -1:
            return {}
        item = self.table.item(row, self.COL_NAME)
        if not item:
            return {}
        baseline = item.data(self._BASELINE_ROLE)
        return baseline if isinstance(baseline, dict) else {}

    def _replace_pending_operation(
        self, iface: str, types: set[OperationType], new_op=None
    ):
        self.pending_ops = [
            op
            for op in self.pending_ops
            if not (op.args.get("iface") == iface and op.operation_type in types)
        ]
        if new_op is not None:
            self.pending_ops.append(new_op)

    def _normalize_pending_operations(self, ops: list[Operation]) -> list[Operation]:
        normalized: list[Operation] = []
        for op in ops:
            iface = op.args.get("iface")
            if iface:
                conflict_types = self._conflicting_operation_types(op.operation_type)
                if conflict_types:
                    normalized = [
                        existing
                        for existing in normalized
                        if not (
                            existing.args.get("iface") == iface
                            and existing.operation_type in conflict_types
                        )
                    ]
            normalized.append(op)
        return normalized

    @staticmethod
    def _conflicting_operation_types(op_type: OperationType) -> set[OperationType]:
        if op_type == OperationType.SET_INTERFACE_DESCRIPTION:
            return {OperationType.SET_INTERFACE_DESCRIPTION}
        if op_type == OperationType.SET_INTERFACE_STATUS:
            return {OperationType.SET_INTERFACE_STATUS}
        if op_type in (
            OperationType.SET_INTERFACE_IP,
            OperationType.CLEAR_INTERFACE_IP,
        ):
            return {
                OperationType.SET_INTERFACE_IP,
                OperationType.CLEAR_INTERFACE_IP,
            }
        if op_type in (
            OperationType.SET_SWITCHPORT_MODE_ACCESS,
            OperationType.SET_SWITCHPORT_MODE_TRUNK,
            OperationType.SET_SWITCHPORT_MODE_ROUTED,
        ):
            return {
                OperationType.SET_SWITCHPORT_MODE_ACCESS,
                OperationType.SET_SWITCHPORT_MODE_TRUNK,
                OperationType.SET_SWITCHPORT_MODE_ROUTED,
                OperationType.SET_ACCESS_VLAN,
                OperationType.CLEAR_ACCESS_VLAN,
                OperationType.SET_TRUNK_ALLOWED_VLANS,
                OperationType.CLEAR_TRUNK_ALLOWED_VLANS,
            }
        if op_type in (
            OperationType.SET_ACCESS_VLAN,
            OperationType.CLEAR_ACCESS_VLAN,
            OperationType.SET_TRUNK_ALLOWED_VLANS,
            OperationType.CLEAR_TRUNK_ALLOWED_VLANS,
        ):
            return {
                OperationType.SET_ACCESS_VLAN,
                OperationType.CLEAR_ACCESS_VLAN,
                OperationType.SET_TRUNK_ALLOWED_VLANS,
                OperationType.CLEAR_TRUNK_ALLOWED_VLANS,
            }
        return set()

    def _on_desc_changed(self):
        if self._loading:
            return

        w = self.sender()
        iface = w.property("iface")
        desc = w.text().strip()
        baseline = self._baseline_for_iface(iface)
        if desc == baseline.get("description", ""):
            self._replace_pending_operation(
                iface, {OperationType.SET_INTERFACE_DESCRIPTION}
            )
            return

        self._replace_pending_operation(
            iface,
            {OperationType.SET_INTERFACE_DESCRIPTION},
            Operation(
                OperationType.SET_INTERFACE_DESCRIPTION,
                iface=iface,
                description=desc or None,
            ),
        )

        self._append_log(
            f"[OP] Ustawiono opis na interfejsie {iface}: {desc or '(BRAK)'}"
        )

    def _on_ip_changed(self):
        if self._loading:
            return

        w = self.sender()
        iface = w.property("iface")

        ip = w.text().strip()

        if ip and not is_valid_ip(ip):
            set_error_style(w, "Niepoprawny adres IPv4!")
            return
        else:
            clear_error_style(w)

        self._update_ip_mask(iface)

    def _on_mask_changed(self):
        if self._loading:
            return
        w = self.sender()
        iface = w.property("iface")
        self._update_ip_mask(iface)

    def _update_ip_mask(self, iface: str):
        row = self._find_row(iface)
        if row == -1:
            return

        ip_w = self.table.cellWidget(row, self.COL_IP)
        mask_w = self.table.cellWidget(row, self.COL_MASK)

        if not isinstance(ip_w, QLineEdit) or not isinstance(mask_w, QSpinBox):
            return

        ip = ip_w.text().strip()
        cidr = mask_w.value()
        baseline = self._baseline_for_iface(iface)
        ip_ops = {
            OperationType.SET_INTERFACE_IP,
            OperationType.CLEAR_INTERFACE_IP,
        }
        baseline_ip = baseline.get("ip", "")
        baseline_cidr = baseline.get("cidr", 0)

        if ip == baseline_ip and cidr == baseline_cidr:
            self._replace_pending_operation(iface, ip_ops)
            return

        if not ip or cidr == 0:
            if not baseline_ip and baseline_cidr == 0:
                self._replace_pending_operation(iface, ip_ops)
                return

        if not ip or cidr == 0:
            self._replace_pending_operation(
                iface,
                ip_ops,
                Operation(
                    OperationType.CLEAR_INTERFACE_IP,
                    iface=iface,
                    old_ip=baseline_ip or None,
                    old_mask=cidr_to_mask(baseline_cidr) if baseline_cidr else None,
                ),
            )
            self._append_log(f"[OP] Wyczyszczono adres IP na {iface}")

        else:
            mask = cidr_to_mask(cidr)
            self._replace_pending_operation(
                iface,
                ip_ops,
                Operation(
                    OperationType.SET_INTERFACE_IP,
                    iface=iface,
                    ip=ip,
                    mask=mask,
                    old_ip=baseline_ip or None,
                    old_mask=cidr_to_mask(baseline_cidr) if baseline_cidr else None,
                ),
            )
            self._append_log(f"[OP] Ustawiono adres IP na {iface}: {ip}/{cidr}")

    def _on_status_changed(self, is_up: bool):
        if self._loading:
            return

        w = self.sender()
        iface = w.property("iface")
        baseline = self._baseline_for_iface(iface)
        if is_up == baseline.get("status", True):
            self._replace_pending_operation(iface, {OperationType.SET_INTERFACE_STATUS})
            return

        self._replace_pending_operation(
            iface,
            {OperationType.SET_INTERFACE_STATUS},
            Operation(
                OperationType.SET_INTERFACE_STATUS,
                iface=iface,
                enabled=is_up,
            ),
        )

        self._append_log(f"[OP] {'Włączono' if is_up else 'Wyłączono'} {iface}")

    def get_pending_operations(self, clear=False) -> list[Operation]:
        self.pending_ops = self._normalize_pending_operations(list(self.pending_ops))
        ops = list(self.pending_ops)
        if clear:
            self.pending_ops.clear()
        return ops

    def clear_pending_operations(self):
        self.pending_ops.clear()

    def export_state(self):
        rows = []
        for r in range(self.table.rowCount()):
            name = self.table.item(r, self.COL_NAME).text()

            desc = self.table.cellWidget(r, self.COL_DESC).text()
            ip = self.table.cellWidget(r, self.COL_IP).text()
            cidr = self.table.cellWidget(r, self.COL_MASK).value()
            status = (
                "up"
                if self.table.cellWidget(r, self.COL_STATUS).isChecked()
                else "down"
            )

            rows.append([name, desc, ip, str(cidr), status])

        return {
            "rows": rows,
            "pending_ops": self._normalize_pending_operations(list(self.pending_ops)),
        }

    def import_state(self, data: dict):
        self._loading = True
        try:
            self.table.setRowCount(0)
            for row in data.get("rows", []):
                name, desc, ip, cidr, status = row
                self._create_interface_row(name, desc, ip, cidr, status)

            self.pending_ops = self._normalize_pending_operations(
                list(data.get("pending_ops", []))
            )
        finally:
            self._loading = False

    def sync_from_config(self, conf: ParsedConfig):
        self._loading = True
        try:
            self.table.setRowCount(0)

            for name, data in iter_user_visible_interfaces(conf):
                desc = data.get("description", "")
                ip = data.get("ip", "")
                mask = data.get("mask", "")
                cidr = mask_to_cidr(mask) if mask else 0
                status = data.get("status", "")

                self._create_interface_row(
                    name=name,
                    desc=desc,
                    ip=ip,
                    cidr_str=str(cidr),
                    status=status,
                )

            self.pending_ops.clear()
            self._append_log("[SYNC] Interfejsy zaktualizowane z bieżącą konfiguracją.")
        finally:
            self._loading = False
