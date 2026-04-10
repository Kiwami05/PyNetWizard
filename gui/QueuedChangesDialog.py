from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPlainTextEdit, QPushButton


class QueuedChangesDialog(QDialog):
    def __init__(
        self,
        host: str,
        commands: list[str],
        operation_count: int,
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle(f"Zakolejkowane zmiany — {host}")
        self.resize(780, 520)

        layout = QVBoxLayout(self)

        summary = QLabel(
            f"<b>Urządzenie:</b> {host} | "
            f"<b>Operacje:</b> {operation_count} | "
            f"<b>Komendy CLI:</b> {len(commands)}"
        )
        layout.addWidget(summary)

        editor = QPlainTextEdit()
        editor.setReadOnly(True)
        editor.setPlaceholderText("Brak zakolejkowanych zmian.")
        editor.setStyleSheet(
            """
            QPlainTextEdit {
                background-color: #111;
                color: #0f0;
                font-family: monospace;
                font-size: 12px;
            }
            """
        )
        editor.setPlainText("\n".join(commands))
        layout.addWidget(editor, 1)

        btn_close = QPushButton("Zamknij")
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close)
