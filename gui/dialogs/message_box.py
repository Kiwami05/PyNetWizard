from PySide6.QtWidgets import QMessageBox


def ask_yes_no(parent, title: str, text: str) -> QMessageBox.StandardButton:
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Question)
    box.setWindowTitle(title)
    box.setText(text)
    box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
    box.setDefaultButton(QMessageBox.No)
    box.button(QMessageBox.Yes).setText("Tak")
    box.button(QMessageBox.No).setText("Nie")
    return QMessageBox.StandardButton(box.exec())
