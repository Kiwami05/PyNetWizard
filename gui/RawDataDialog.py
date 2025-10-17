# gui/RawDataDialog.py
from PySide6.QtWidgets import QDialog, QVBoxLayout, QTextEdit, QDialogButtonBox
import json


class RawDataDialog(QDialog):
    def __init__(self, raw_info, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Surowe dane nmap")
        self.resize(700, 500)

        layout = QVBoxLayout(self)
        text = QTextEdit()
        text.setReadOnly(True)

        try:
            pretty = json.dumps(raw_info, indent=2, ensure_ascii=False)
        except Exception:
            pretty = str(raw_info)

        text.setText(pretty)
        layout.addWidget(text)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)
