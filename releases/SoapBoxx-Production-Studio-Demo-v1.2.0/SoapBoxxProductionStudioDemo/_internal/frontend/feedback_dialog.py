from PyQt6.QtWidgets import QDialog, QPushButton, QTextEdit, QVBoxLayout


class FeedbackDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Report Issue / Feedback")
        self.setMinimumSize(400, 200)

        layout = QVBoxLayout()

        self.text_edit = QTextEdit()
        self.text_edit.setPlaceholderText("Describe the issue or feedback...")
        layout.addWidget(self.text_edit)

        submit_btn = QPushButton("Submit")
        submit_btn.clicked.connect(self.submit_feedback)
        layout.addWidget(submit_btn)

        self.setLayout(layout)

    def submit_feedback(self):
        feedback = self.text_edit.toPlainText()
        with open("log.txt", "a") as f:
            f.write(f"Feedback: {feedback}\n")
        self.accept()
