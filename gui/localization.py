from PySide6.QtWidgets import QDialogButtonBox, QFileDialog, QMessageBox


BUTTON_TEXTS = {
    QDialogButtonBox.StandardButton.Ok: "OK",
    QDialogButtonBox.StandardButton.Cancel: "Anuluj",
    QDialogButtonBox.StandardButton.Yes: "Tak",
    QDialogButtonBox.StandardButton.No: "Nie",
    QDialogButtonBox.StandardButton.Save: "Zapisz",
    QDialogButtonBox.StandardButton.Open: "Otwórz",
    QDialogButtonBox.StandardButton.Close: "Zamknij",
    QDialogButtonBox.StandardButton.Apply: "Zastosuj",
    QDialogButtonBox.StandardButton.Reset: "Przywróć",
}


def localize_button_box(buttons: QDialogButtonBox) -> None:
    for standard_button, text in BUTTON_TEXTS.items():
        button = buttons.button(standard_button)
        if button:
            button.setText(text)


def question_yes_no(
    parent,
    title: str,
    text: str,
    default_button=QMessageBox.StandardButton.No,
) -> QMessageBox.StandardButton:
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Question)
    box.setWindowTitle(title)
    box.setText(text)
    box.setStandardButtons(
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
    )
    box.setDefaultButton(default_button)
    box.setButtonText(QMessageBox.StandardButton.Yes, "Tak")
    box.setButtonText(QMessageBox.StandardButton.No, "Nie")
    return QMessageBox.StandardButton(box.exec())


def _localize_file_dialog(dialog: QFileDialog, accept_text: str) -> None:
    dialog.setOption(QFileDialog.Option.DontUseNativeDialog, True)
    dialog.setLabelText(QFileDialog.DialogLabel.Accept, accept_text)
    dialog.setLabelText(QFileDialog.DialogLabel.Reject, "Anuluj")


def get_save_file_name(parent, title: str, directory: str = "", file_filter: str = ""):
    dialog = QFileDialog(parent, title, directory, file_filter)
    dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
    dialog.setFileMode(QFileDialog.FileMode.AnyFile)
    _localize_file_dialog(dialog, "Zapisz")
    if dialog.exec() == QFileDialog.DialogCode.Accepted:
        return dialog.selectedFiles()[0], dialog.selectedNameFilter()
    return "", ""


def get_open_file_name(parent, title: str, directory: str = "", file_filter: str = ""):
    dialog = QFileDialog(parent, title, directory, file_filter)
    dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptOpen)
    dialog.setFileMode(QFileDialog.FileMode.ExistingFile)
    _localize_file_dialog(dialog, "Otwórz")
    if dialog.exec() == QFileDialog.DialogCode.Accepted:
        return dialog.selectedFiles()[0], dialog.selectedNameFilter()
    return "", ""


def get_existing_directory(parent, title: str, directory: str = "") -> str:
    dialog = QFileDialog(parent, title, directory)
    dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptOpen)
    dialog.setFileMode(QFileDialog.FileMode.Directory)
    dialog.setOption(QFileDialog.Option.ShowDirsOnly, True)
    _localize_file_dialog(dialog, "Wybierz")
    if dialog.exec() == QFileDialog.DialogCode.Accepted:
        return dialog.selectedFiles()[0]
    return ""
