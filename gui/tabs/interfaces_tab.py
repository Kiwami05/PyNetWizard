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
    QCheckBox,
    QSpinBox,
)
from PySide6.QtCore import Qt

import ipaddress

from operations.operation import Operation
from operations.operation_type import OperationType
from services.parsed_config import ParsedConfig


# ================================================================
#                    WALIDACJE + KONWERSJE MASK
# ================================================================


def is_valid_ip(addr: str) -> bool:
    try:
        ipaddress.ip_address(addr)
        return True
    except Exception:
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
    except Exception:
        return 0


# ================================================================
#                         KLASA TABA
# ================================================================


class InterfacesTab(QWidget):
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

    def __init__(self, parent=None):
        super().__init__(parent)

        self.pending_ops: list[Operation] = []
        self._loading: bool = False  # blokuje eventy podczas sync/import
        self._log_message = lambda _text: None

        # ============================================================
        #                           UI
        # ============================================================

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 15, 20, 15)
        main_layout.setSpacing(10)

        main_layout.addWidget(QLabel("<h2>Konfiguracja interfejsów</h2>"))

        # --- Tabela interfejsów ---
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            ["Nazwa", "Opis", "Adres IP", "Maska (/CIDR)", "Status"]
        )
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        main_layout.addWidget(self.table, 4)

        # --- Przyciski operacyjne (Enable/Disable) ---
        btns = QHBoxLayout()
        self.btn_enable = QPushButton("Włącz")
        self.btn_disable = QPushButton("Wyłącz")

        self.btn_enable.clicked.connect(lambda: self._cmd_on_selected("no shutdown"))
        self.btn_disable.clicked.connect(lambda: self._cmd_on_selected("shutdown"))

        for b in (self.btn_enable, self.btn_disable):
            btns.addWidget(b)
        btns.addStretch()

        main_layout.addLayout(btns)

    def set_logger(self, log_message):
        self._log_message = log_message or (lambda _text: None)

    def _append_log(self, text: str):
        self._log_message(text)

    # ================================================================
    #                       TWORZENIE WIERSZA
    # ================================================================

    def _create_interface_row(self, name, desc, ip, cidr_str, status):
        row = self.table.rowCount()
        self.table.insertRow(row)

        # ==== NAME ====
        item_name = QTableWidgetItem(name)
        item_name.setFlags(item_name.flags() & ~Qt.ItemIsEditable)
        self.table.setItem(row, self.COL_NAME, item_name)

        # ==== DESC ====
        edit_desc = QLineEdit(desc)
        edit_desc.setToolTip("Opis interfejsu (opcjonalny).")
        edit_desc.setProperty("iface", name)
        edit_desc.editingFinished.connect(self._on_desc_changed)
        self.table.setCellWidget(row, self.COL_DESC, edit_desc)

        # ==== IP ====
        edit_ip = QLineEdit(ip)
        edit_ip.setToolTip("Adres IPv4 (np. 192.168.1.1).")
        edit_ip.setProperty("iface", name)
        edit_ip.editingFinished.connect(self._on_ip_changed)
        self.table.setCellWidget(row, self.COL_IP, edit_ip)

        # ==== MASK (CIDR) ====
        spin_mask = QSpinBox()
        spin_mask.setRange(0, 32)
        spin_mask.setValue(int(cidr_str))
        spin_mask.setToolTip(
            "Maska w formacie CIDR (0–32). Do IOS trafia maska kropkowa."
        )
        spin_mask.setProperty("iface", name)
        spin_mask.valueChanged.connect(self._on_mask_changed)
        self.table.setCellWidget(row, self.COL_MASK, spin_mask)

        # ==== STATUS ====
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

    # ================================================================
    #                   HANDLERY ZMIAN (AUTO-COMMANDS)
    # ================================================================

    def _on_desc_changed(self):
        if self._loading:
            return

        w = self.sender()
        iface = w.property("iface")
        desc = w.text().strip()

        self.pending_ops.append(
            Operation(
                OperationType.SET_INTERFACE_DESCRIPTION,
                iface=iface,
                description=desc or None,
            )
        )

        self._append_log(f"[OP] set description on {iface}: {desc or '(clear)'}")

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

    def _on_mask_changed(self, _val):
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

        if not ip or cidr == 0:
            self.pending_ops.append(
                Operation(
                    OperationType.CLEAR_INTERFACE_IP,
                    iface=iface,
                )
            )
            self._append_log(f"[OP] clear IP on {iface}")

        else:
            mask = cidr_to_mask(cidr)
            self.pending_ops.append(
                Operation(
                    OperationType.SET_INTERFACE_IP,
                    iface=iface,
                    ip=ip,
                    mask=mask,
                )
            )
            self._append_log(f"[OP] set IP on {iface}: {ip}/{cidr}")

    def _on_status_changed(self, is_up: bool):
        if self._loading:
            return

        w = self.sender()
        iface = w.property("iface")

        self.pending_ops.append(
            Operation(
                OperationType.SET_INTERFACE_STATUS,
                iface=iface,
                enabled=is_up,
            )
        )

        self._append_log(f"[OP] {'enable' if is_up else 'disable'} {iface}")

    # ================================================================
    #                   PRZYCISKI Enable/Disable
    # ================================================================

    def _cmd_on_selected(self, cmd: str):
        row = self.table.currentRow()
        if row == -1:
            self._append_log(f"[WARN] Brak zaznaczonego interfejsu ({cmd}).")
            return

        iface = self.table.item(row, self.COL_NAME).text()
        self.pending_ops.append(
            Operation(
                OperationType.SET_INTERFACE_STATUS,
                iface=iface,
                enabled=(cmd == "no shutdown"),
            )
        )

        self._append_log(
            f"[OP] {'enable' if cmd == 'no shutdown' else 'disable'} {iface}"
        )

    # ================================================================
    #                        BUFORY / PENDING CMDS
    # ================================================================

    def get_pending_operations(self, clear=False) -> list[Operation]:
        ops = list(self.pending_ops)
        if clear:
            self.pending_ops.clear()
        return ops

    def clear_pending_operations(self):
        self.pending_ops.clear()

    # ================================================================
    #                        EXPORT / IMPORT
    # ================================================================

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
            "pending_ops": list(self.pending_ops),
        }

    def import_state(self, data: dict):
        self._loading = True
        try:
            self.table.setRowCount(0)
            for row in data.get("rows", []):
                name, desc, ip, cidr, status = row
                self._create_interface_row(name, desc, ip, cidr, status)

            self.pending_ops = list(data.get("pending_ops", []))
        finally:
            self._loading = False

    # ================================================================
    #                      SYNC Z PARSED CONFIG
    # ================================================================

    def sync_from_config(self, conf: ParsedConfig):
        self._loading = True
        try:
            self.table.setRowCount(0)

            for name, data in conf.interfaces.items.items():
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
            self._append_log("[SYNC] Interfaces updated from running-config.")
        finally:
            self._loading = False
