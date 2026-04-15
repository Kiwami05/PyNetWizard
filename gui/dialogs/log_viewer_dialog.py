from pathlib import Path
import re

from PySide6.QtCore import QTimer
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QPushButton,
    QCheckBox,
    QLineEdit,
    QTextEdit,
    QFileDialog,
)


class LogEntry:
    def __init__(self, level: str, lines: list[str]):
        self.level = level
        self.lines = lines


class LogViewerDialog(QDialog):
    """
    Viewer logów z grouping-iem multiline:
    - kolorowanie (ERROR/WARNING/INFO/DEBUG)
    - filtrowanie
    - wyszukiwanie
    - auto-refresh
    """

    LOG_DIR = Path("./logs")

    LEVEL_COLORS = {
        "ERROR": "#ffcccc",
        "WARNING": "#fff5cc",
        "INFO": "#f0f0f0",
        "DEBUG": "#e5e5e5",
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Przeglądarka logów")
        self.resize(1000, 700)

        main = QVBoxLayout(self)

        # flaga: czy użytkownik przewinął w górę (jeśli tak, pauzujemy auto-refresh)
        self._user_scrolled_up = False

        #  Górny pasek — wybór pliku logu
        top_bar = QHBoxLayout()
        main.addLayout(top_bar)

        top_bar.addWidget(QLabel("Plik:"))
        self.combo_files = QComboBox()
        top_bar.addWidget(self.combo_files, 1)

        self.btn_refresh_files = QPushButton("Odśwież listę")
        self.btn_refresh_files.clicked.connect(self._reload_file_list)
        top_bar.addWidget(self.btn_refresh_files)

        self.btn_open_folder = QPushButton("Otwórz folder")
        self.btn_open_folder.clicked.connect(self._open_log_folder)
        top_bar.addWidget(self.btn_open_folder)

        # Pasek filtrów
        filter_bar = QHBoxLayout()
        main.addLayout(filter_bar)

        self.chk_error = QCheckBox("ERROR")
        self.chk_warning = QCheckBox("WARNING")
        self.chk_info = QCheckBox("INFO")
        self.chk_debug = QCheckBox("DEBUG")

        # Domyślnie wszystko włączone
        for chk in (self.chk_error, self.chk_warning, self.chk_info, self.chk_debug):
            chk.setChecked(True)
            chk.stateChanged.connect(self._apply_filters)

        filter_bar.addWidget(self.chk_error)
        filter_bar.addWidget(self.chk_warning)
        filter_bar.addWidget(self.chk_info)
        filter_bar.addWidget(self.chk_debug)

        filter_bar.addSpacing(20)

        self.chk_show_only_matches = QCheckBox("Pokaż tylko dopasowane")
        self.chk_show_only_matches.stateChanged.connect(self._apply_filters)
        filter_bar.addWidget(self.chk_show_only_matches)

        #  Pasek wyszukiwania
        search_bar = QHBoxLayout()
        main.addLayout(search_bar)

        search_bar.addWidget(QLabel("Szukaj:"))
        self.input_search = QLineEdit()
        self.input_search.textChanged.connect(self._apply_filters)
        search_bar.addWidget(self.input_search, 1)

        self.btn_reload = QPushButton("Odśwież")
        self.btn_reload.clicked.connect(self._manual_reload)
        search_bar.addWidget(self.btn_reload)

        #  Pole logu
        self.text = QTextEdit()
        self.text.setReadOnly(True)
        self.text.setLineWrapMode(QTextEdit.NoWrap)
        self.text.setStyleSheet("font-family: monospace; font-size: 11px;")
        main.addWidget(self.text, 10)

        # Wykrywanie ręcznego scrollowania
        self.text.verticalScrollBar().valueChanged.connect(self._on_scroll)

        # Timer do auto-refresh
        self.timer = QTimer(self)
        self.timer.setInterval(1500)
        self.timer.timeout.connect(self._auto_refresh)

        # Inicjalizacja listy plików
        self._reload_file_list()
        self.combo_files.currentIndexChanged.connect(self._on_file_changed)

    def _on_scroll(self):
        bar = self.text.verticalScrollBar()
        self._user_scrolled_up = bar.value() < bar.maximum()

    def _reload_file_list(self):
        self.combo_files.blockSignals(True)
        self.combo_files.clear()

        if self.LOG_DIR.exists():
            for f in sorted(self.LOG_DIR.glob("*.log")):
                self.combo_files.addItem(f.name, f)

        self.combo_files.blockSignals(False)

        if self.combo_files.count() > 0:
            self.combo_files.setCurrentIndex(0)
            self._load_current_file()

    def _open_log_folder(self):
        QFileDialog.getOpenFileName(self, "Folder logów", str(self.LOG_DIR))

    def _on_file_changed(self, index: int):
        # zmiana pliku = reset pauzy i normalny tail-f
        self._user_scrolled_up = False
        self._load_current_file()

    def _load_current_file(self):
        file_path: Path = self.combo_files.currentData()
        if not file_path or not file_path.exists():
            self.text.setHtml("<b>Brak danych</b>")
            return

        try:
            raw = file_path.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            self.text.setHtml(f"<b>Błąd odczytu pliku:</b><br>{e}")
            return

        lines = raw.splitlines()

        self._entries = []
        current_entry = None

        for line in lines:
            lvl = self._extract_level(line)

            if lvl:
                # nowy blok logu
                current_entry = LogEntry(level=lvl, lines=[line])
                self._entries.append(current_entry)
            else:
                # kontynuacja poprzedniego wpisu
                if current_entry:
                    current_entry.lines.append(line)
                else:
                    # plik zaczyna się od linii bez poziomu
                    current_entry = LogEntry(level="INFO", lines=[line])
                    self._entries.append(current_entry)

        self._apply_filters()

    def _apply_filters(self):
        if not hasattr(self, "_entries"):
            return

        search_term = self.input_search.text().strip().lower()
        only_matches = self.chk_show_only_matches.isChecked()

        allowed = []
        if self.chk_error.isChecked():
            allowed.append("ERROR")
        if self.chk_warning.isChecked():
            allowed.append("WARNING")
        if self.chk_info.isChecked():
            allowed.append("INFO")
        if self.chk_debug.isChecked():
            allowed.append("DEBUG")

        html = ["<html><body style='font-family: monospace; white-space: pre;'>"]

        for entry in self._entries:
            # filtr poziomu
            if entry.level not in allowed:
                continue

            block_text = "\n".join(entry.lines)
            block_lower = block_text.lower()

            # filtr wyszukiwania
            if search_term:
                if search_term not in block_lower:
                    if only_matches:
                        continue

            # kolor tła
            bg = self._severity_background_color(entry.level)
            bg_css = f"rgb({bg.red()}, {bg.green()}, {bg.blue()})"

            # escape HTML
            escaped_lines = [
                line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                for line in entry.lines
            ]
            combined = "\n".join(escaped_lines)

            # highlight search
            if search_term:
                combined = re.sub(
                    re.escape(search_term),
                    lambda m: f"<span style='background:yellow'>{m.group(0)}</span>",
                    combined,
                    flags=re.IGNORECASE,
                )

            if bg:
                html.append(
                    f"<div style='"
                    f"background:{bg_css};"
                    f"border-left:4px solid {bg_css};"
                    f"padding:2px 6px;"
                    f"margin-bottom:2px;'>"
                    f"{combined}</div>"
                )
            else:
                html.append(f"<div>{combined}</div>")

        html.append("</body></html>")
        self.text.setHtml("\n".join(html))

        # auto-scroll tylko, gdy użytkownik NIE przewinął w górę
        bar = self.text.verticalScrollBar()
        if not self._user_scrolled_up:
            bar.setValue(bar.maximum())

    def _extract_level(self, line: str):
        """
        Przykładowy format Netmiko:
        2025-02-11 20:33:22 [INFO] Connecting...
        """
        m = re.search(r"\[(ERROR|WARNING|INFO|DEBUG)\]", line)
        return m.group(1) if m else None

    def _auto_refresh(self):
        # jeśli użytkownik przewinął w górę – pauzujemy auto-refresh
        if self._user_scrolled_up:
            return

        if self.combo_files.currentIndex() >= 0:
            self._load_current_file()

    def _manual_reload(self):
        # ręczne odświeżenie – trzymamy aktualną decyzję user_scrolled_up
        self._load_current_file()

    def showEvent(self, event):
        self.timer.start()
        super().showEvent(event)

    def hideEvent(self, event):
        self.timer.stop()
        super().hideEvent(event)

    def _severity_background_color(self, severity: str) -> QColor:
        pal = self.palette()
        base = pal.color(QPalette.Base)

        def mix(c1: QColor, c2: QColor, ratio=0.12):
            return QColor(
                int(c1.red() * (1 - ratio) + c2.red() * ratio),
                int(c1.green() * (1 - ratio) + c2.green() * ratio),
                int(c1.blue() * (1 - ratio) + c2.blue() * ratio),
            )

        if severity == "ERROR":
            return mix(base, QColor(220, 50, 47))  # solarized red
        if severity == "WARNING":
            return mix(base, QColor(181, 137, 0))  # solarized yellow
        if severity == "INFO":
            return mix(base, QColor(38, 139, 210))  # blue
        if severity == "DEBUG":
            return mix(base, QColor(88, 110, 117))  # subtle gray

        return base
