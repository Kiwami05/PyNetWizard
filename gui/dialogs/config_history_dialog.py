import html
from pathlib import Path
from typing import List, Tuple

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QPushButton,
    QHBoxLayout,
    QTextEdit,
    QMessageBox,
    QSplitter,
    QAbstractItemView,
)

from devices.device import Device
from services.config_history import list_snapshots, ConfigSnapshot


class ConfigHistoryDialog(QDialog):
    """
    Dialog historii konfiguracji:
    - lista snapshotów z dysku (per urządzenie),
    - diff side-by-side z wybranymi snapshotami lub z aktualnym configiem,
    - synchronizowane przewijanie,
    - kolorowe wyróżnianie zmian.
    """

    def __init__(
        self,
        device: Device,
        current_config: str | None,
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle(f"Historia konfiguracji — {device.host}")
        self.resize(1100, 650)

        self.device = device
        self.current_config = current_config or ""
        self.snapshots: List[ConfigSnapshot] = []

        main_layout = QVBoxLayout(self)

        # === Nagłówek ===
        header = QLabel(
            f"<h3>Historia konfiguracji dla urządzenia: "
            f"<code>{html.escape(device.host)}</code></h3>"
        )
        header.setTextFormat(Qt.RichText)
        main_layout.addWidget(header)

        # === Tabela snapshotów ===
        self.table = QTableWidget(0, 4, self)
        self.table.setHorizontalHeaderLabels(["Data", "Typ", "Rozmiar [B]", "Plik"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        header_view = self.table.horizontalHeader()
        header_view.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header_view.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header_view.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header_view.setSectionResizeMode(3, QHeaderView.Stretch)

        main_layout.addWidget(self.table, 2)

        # === Przyciski akcji nad diffem ===
        btn_row = QHBoxLayout()
        self.btn_refresh = QPushButton("Odśwież")
        self.btn_refresh.clicked.connect(self._reload_snapshots)

        self.btn_compare_two = QPushButton("Porównaj zaznaczone (2 wersje)")
        self.btn_compare_two.clicked.connect(self._compare_two_selected)

        self.btn_compare_current = QPushButton(
            "Porównaj zaznaczoną z bieżącą konfiguracją"
        )
        self.btn_compare_current.clicked.connect(self._compare_with_current)

        self.btn_delete = QPushButton("Usuń zaznaczone")
        self.btn_delete.clicked.connect(self._delete_selected)

        btn_row.addWidget(self.btn_refresh)
        btn_row.addStretch()
        btn_row.addWidget(self.btn_compare_two)
        btn_row.addWidget(self.btn_compare_current)
        btn_row.addWidget(self.btn_delete)

        main_layout.addLayout(btn_row)

        # === Splitter z diffem side-by-side ===
        splitter = QSplitter(Qt.Horizontal, self)

        self.left_view = QTextEdit(self)
        self.left_view.setReadOnly(True)
        self.left_view.setAcceptRichText(True)
        self.left_view.setLineWrapMode(QTextEdit.NoWrap)
        self.left_view.setStyleSheet(
            "QTextEdit { font-family: monospace; font-size: 11px; }"
        )

        self.right_view = QTextEdit(self)
        self.right_view.setReadOnly(True)
        self.right_view.setAcceptRichText(True)
        self.right_view.setLineWrapMode(QTextEdit.NoWrap)
        self.right_view.setStyleSheet(
            "QTextEdit { font-family: monospace; font-size: 11px; }"
        )

        splitter.addWidget(self.left_view)
        splitter.addWidget(self.right_view)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)

        main_layout.addWidget(splitter, 3)

        # synchroniczne przewijanie
        self._scroll_sync = False
        self.left_view.verticalScrollBar().valueChanged.connect(
            self._on_left_scroll_changed
        )
        self.right_view.verticalScrollBar().valueChanged.connect(
            self._on_right_scroll_changed
        )

        # inicjalny load
        self._reload_snapshots()

    # ==========================================================
    #                ŁADOWANIE / LISTA SNAPSHOTÓW
    # ==========================================================

    def _reload_snapshots(self):
        self.snapshots = list_snapshots(self.device)
        self.table.setRowCount(0)

        for snap in self.snapshots:
            row = self.table.rowCount()
            self.table.insertRow(row)

            dt_str = snap.timestamp.strftime("%Y-%m-%d %H:%M:%S")
            item_dt = QTableWidgetItem(dt_str)
            item_dt.setFlags(item_dt.flags() & ~Qt.ItemIsEditable)

            item_kind = QTableWidgetItem(snap.kind)
            item_kind.setFlags(item_kind.flags() & ~Qt.ItemIsEditable)

            item_size = QTableWidgetItem(str(snap.size))
            item_size.setFlags(item_size.flags() & ~Qt.ItemIsEditable)

            item_path = QTableWidgetItem(snap.path)
            item_path.setFlags(item_path.flags() & ~Qt.ItemIsEditable)

            # schowaj indeks snapshotu w UserRole (wystarczy w pierwszej kolumnie)
            item_dt.setData(Qt.UserRole, row)

            self.table.setItem(row, 0, item_dt)
            self.table.setItem(row, 1, item_kind)
            self.table.setItem(row, 2, item_size)
            self.table.setItem(row, 3, item_path)

        self.left_view.clear()
        self.right_view.clear()

    def _selected_rows(self) -> List[int]:
        rows = self.table.selectionModel().selectedRows()
        return [r.row() for r in rows] if rows else []

    def _get_snapshot_text(self, index: int) -> str:
        if index < 0 or index >= len(self.snapshots):
            return ""
        path = self.snapshots[index].path
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                return f.read()
        except OSError:
            return ""

    # ==========================================================
    #                  AKCJE PRZYCISKÓW
    # ==========================================================

    def _compare_two_selected(self):
        rows = self._selected_rows()
        if len(rows) != 2:
            QMessageBox.information(
                self,
                "Wybór wersji",
                "Zaznacz dokładnie dwie wersje w tabeli, aby je porównać.",
            )
            return

        idx_a, idx_b = rows
        text_a = self._get_snapshot_text(idx_a)
        text_b = self._get_snapshot_text(idx_b)

        if not text_a and not text_b:
            QMessageBox.warning(self, "Błąd", "Nie udało się odczytać plików.")
            return

        self._show_diff(text_a, text_b)

    def _compare_with_current(self):
        rows = self._selected_rows()
        if len(rows) != 1:
            QMessageBox.information(
                self,
                "Wybór wersji",
                "Zaznacz jedną wersję, aby porównać ją z bieżącą konfiguracją.",
            )
            return

        if not self.current_config:
            QMessageBox.information(
                self,
                "Brak bieżącej konfiguracji",
                "Brak aktualnego snapshotu konfiguracji. "
                "Najpierw wykonaj Sync dla tego urządzenia.",
            )
            return

        idx = rows[0]
        text_a = self._get_snapshot_text(idx)
        text_b = self.current_config

        self._show_diff(text_a, text_b)

    def _delete_selected(self):
        rows = sorted(self._selected_rows(), reverse=True)
        if not rows:
            QMessageBox.information(
                self, "Usuwanie", "Zaznacz przynajmniej jedną wersję do usunięcia."
            )
            return

        reply = QMessageBox.question(
            self,
            "Potwierdzenie",
            f"Czy na pewno chcesz usunąć {len(rows)} wybranych plików z historii?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        errors = []
        for r in rows:
            snap = self.snapshots[r]
            try:
                Path(snap.path).unlink()
            except OSError as e:
                errors.append(f"{snap.path}: {e}")

        self._reload_snapshots()

        if errors:
            QMessageBox.warning(
                self,
                "Błędy usuwania",
                "Niektórych plików nie udało się usunąć:\n- " + "\n- ".join(errors),
            )

    # ==========================================================
    #                DIFF SIDE-BY-SIDE + HTML
    # ==========================================================

    def _show_diff(self, left_text: str, right_text: str):
        left_html, right_html = build_side_by_side_diff_html(
            left_text,
            right_text,
            self.palette(),
        )
        self.left_view.setHtml(left_html)
        self.right_view.setHtml(right_html)

        # przewiń na początek
        self.left_view.verticalScrollBar().setValue(0)
        self.right_view.verticalScrollBar().setValue(0)

    # ==========================================================
    #                  SYNCHRONIZACJA SKROLLOWANIA
    # ==========================================================

    def _on_left_scroll_changed(self, value: int):
        if self._scroll_sync:
            return
        self._scroll_sync = True
        self.right_view.verticalScrollBar().setValue(value)
        self._scroll_sync = False

    def _on_right_scroll_changed(self, value: int):
        if self._scroll_sync:
            return
        self._scroll_sync = True
        self.left_view.verticalScrollBar().setValue(value)
        self._scroll_sync = False


# ==========================================================
#           FUNKCJA BUDUJĄCA HTML SIDE-BY-SIDE
# ==========================================================


def build_side_by_side_diff_html(
    left_text: str,
    right_text: str,
    palette=None,
) -> Tuple[str, str]:
    """
    Zwraca parę (left_html, right_html) z zakolorowanym diffem.
    Kolory dopasowane dynamicznie do motywu (jasny/ciemny).
    """

    import difflib
    from PySide6.QtGui import QColor, QPalette
    from PySide6.QtWidgets import QApplication

    if palette is None:
        palette = QApplication.palette()

    base = palette.color(QPalette.Base)

    def mix(c1: QColor, c2: QColor, ratio=0.16):
        return QColor(
            int(c1.red() * (1 - ratio) + c2.red() * ratio),
            int(c1.green() * (1 - ratio) + c2.green() * ratio),
            int(c1.blue() * (1 - ratio) + c2.blue() * ratio),
        )

    # Kolory semantyczne (jak w log viewerze)
    delete_color = mix(base, QColor(220, 50, 47))  # red
    insert_color = mix(base, QColor(133, 153, 0))  # green
    replace_color = mix(base, QColor(181, 137, 0))  # yellow

    def to_css(color: QColor) -> str:
        return f"rgb({color.red()}, {color.green()}, {color.blue()})"

    left_lines = left_text.splitlines()
    right_lines = right_text.splitlines()

    sm = difflib.SequenceMatcher(None, left_lines, right_lines)
    left_out: List[str] = []
    right_out: List[str] = []

    def fmt_line(num: str | int, line: str, bg: QColor | None) -> str:
        num_str = "" if num == "" else str(num)
        num_html = f"<span style='color:#888;'>{html.escape(num_str).rjust(4)} </span>"
        line_html = html.escape(line).replace(" ", "&nbsp;")

        style = "font-family: monospace; font-size: 11px;"
        if bg:
            style += f" background-color:{to_css(bg)};"

        return f"<div style='{style}'>{num_html}{line_html}</div>"

    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            for i in range(i1, i2):
                left_out.append(fmt_line(i + 1, left_lines[i], None))
            for j in range(j1, j2):
                right_out.append(fmt_line(j + 1, right_lines[j], None))

        elif tag == "replace":
            span = max(i2 - i1, j2 - j1)
            for k in range(span):
                left_bg = replace_color
                right_bg = replace_color

                if i1 + k < i2:
                    left_out.append(fmt_line(i1 + k + 1, left_lines[i1 + k], left_bg))
                else:
                    left_out.append(fmt_line("", "", left_bg))

                if j1 + k < j2:
                    right_out.append(
                        fmt_line(j1 + k + 1, right_lines[j1 + k], right_bg)
                    )
                else:
                    right_out.append(fmt_line("", "", right_bg))

        elif tag == "delete":
            for i in range(i1, i2):
                left_out.append(fmt_line(i + 1, left_lines[i], delete_color))
                right_out.append(fmt_line("", "", delete_color))

        elif tag == "insert":
            for j in range(j1, j2):
                right_out.append(fmt_line(j + 1, right_lines[j], insert_color))
                left_out.append(fmt_line("", "", insert_color))

    left_html = (
        "<html><body style='margin:4px;'>" + "".join(left_out) + "</body></html>"
    )
    right_html = (
        "<html><body style='margin:4px;'>" + "".join(right_out) + "</body></html>"
    )

    return left_html, right_html
