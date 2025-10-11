button.setCheckable(True) - przycisk jest przełączalny
btn.clicked.connect(self.the_button_was_clicked) - event listener na przycisku
button.setChecked(self.button_is_checked) - w sumie to nwm sprawdź
self.button.released.connect(self.the_button_was_released)
QLabel() - do wyświetlania tekstu
QLineEdit() - do inputu

## Kontener

container = QWidget()
container.setLayout(layout)
self.setCentralWidget(container)