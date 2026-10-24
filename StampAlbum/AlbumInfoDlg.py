"""
Album Information Dialog Module
-------------------------------
Dialog window to inspect and edit album metadata (creation date, author, OS,
total page count, and stamp count).

Author: Boris du Reau
"""

import gettext
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QFormLayout, QVBoxLayout, QLineEdit,
    QLabel, QDialogButtonBox
)
from AppLanguage import get_language

# Setup gettext localization for album info dialog
gettext.find("AlbumInfoDlg")
translate = gettext.translation('AlbumInfoDlg', localedir='locale', languages=[get_language()], fallback=True)
translate.install()
_ = translate.gettext


class AlbumInfoDlg(QDialog):
    """Dialog allowing users to view and modify album metadata properties."""

    def __init__(self, metadata: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle(_("Current Album Info"))
        self.resize(360, 220)
        self.metadata = dict(metadata)

        self._create_ui()

    def _create_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()

        # Editable creation date field
        self.eCreationDate = QLineEdit(str(self.metadata.get("creation_date", "")))
        form.addRow(_("Creation date:"), self.eCreationDate)

        # Editable author field
        self.eAuthor = QLineEdit(str(self.metadata.get("author", "")))
        form.addRow(_("Author:"), self.eAuthor)

        # Read-only operating system field
        self.lblOS = QLabel(str(self.metadata.get("os", "")))
        form.addRow(_("Operating system:"), self.lblOS)

        # Read-only total page count field
        self.lblPages = QLabel(str(self.metadata.get("page_count", 0)))
        form.addRow(_("Total pages:"), self.lblPages)

        # Read-only total stamp count field
        self.lblStamps = QLabel(str(self.metadata.get("stamp_count", 0)))
        form.addRow(_("Total stamps:"), self.lblStamps)

        layout.addLayout(form)

        # Standard dialog action buttons with explicit translations
        self.buttonBox = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )

        ok_button = self.buttonBox.button(QDialogButtonBox.StandardButton.Ok)
        if ok_button:
            ok_button.setText(_("OK"))

        cancel_button = self.buttonBox.button(QDialogButtonBox.StandardButton.Cancel)
        if cancel_button:
            cancel_button.setText(_("Cancel"))

        self.buttonBox.accepted.connect(self._on_accept)
        self.buttonBox.rejected.connect(self.reject)
        layout.addWidget(self.buttonBox)

    def _on_accept(self):
        """Save user modifications back into metadata dictionary."""
        self.metadata["creation_date"] = self.eCreationDate.text().strip()
        self.metadata["author"] = self.eAuthor.text().strip()
        self.accept()

    def get_metadata(self) -> dict:
        """Return the updated album metadata."""
        return self.metadata