"""
Dialog Windows Module
---------------------
Contains auxiliary dialogs for application settings and collection creation.

Author: Boris du Reau
Year: 2026
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QComboBox,
    QLineEdit, QDialogButtonBox, QPushButton
)
import gettext
from SCAppLanguage import get_language

# Localization setup
gettext.find("StampCatalogue")
translate = gettext.translation(
    'StampCatalogue', localedir='locale', languages=[get_language()], fallback=True
)
translate.install()
_ = translate.gettext


class ConfigurationDialog(QDialog):
    """Dialog for modifying application settings."""

    def __init__(self, current_lang: str, current_db_type: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(_("Settings"))
        self.resize(320, 160)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.combo_lang = QComboBox()
        self.combo_lang.addItem(_("Français"), "fr")
        self.combo_lang.addItem(_("English"), "en")

        idx_lang = self.combo_lang.findData(current_lang)
        if idx_lang != -1:
            self.combo_lang.setCurrentIndex(idx_lang)
        form.addRow(_("Language:"), self.combo_lang)

        self.combo_db = QComboBox()
        self.combo_db.addItems(["SQLite", "Access"])
        idx_db = self.combo_db.findText(current_db_type)
        if idx_db != -1:
            self.combo_db.setCurrentIndex(idx_db)
        form.addRow(_("Database Type:"), self.combo_db)

        layout.addLayout(form)

        # Translatable button box
        buttons = QDialogButtonBox()
        btn_ok = QPushButton(_("OK"))
        btn_cancel = QPushButton(_("Cancel"))
        buttons.addButton(btn_ok, QDialogButtonBox.ButtonRole.AcceptRole)
        buttons.addButton(btn_cancel, QDialogButtonBox.ButtonRole.RejectRole)

        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_settings(self):
        """Return the selected language code and database engine."""
        return self.combo_lang.currentData(), self.combo_db.currentText()


class CreateCollectionDialog(QDialog):
    """Dialog for creating a new collection associated with a country."""

    def __init__(self, available_countries, parent=None):
        super().__init__(parent)
        self.setWindowTitle(_("Create New Collection"))
        self.resize(350, 150)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.edit_name = QLineEdit()
        self.edit_name.setPlaceholderText(_("e.g. France Mint 1900-1950"))
        form.addRow(_("Collection Name:"), self.edit_name)

        self.combo_country = QComboBox()
        self.combo_country.addItems(available_countries)
        form.addRow(_("Country:"), self.combo_country)

        layout.addLayout(form)

        # Translatable button box
        buttons = QDialogButtonBox()
        btn_ok = QPushButton(_("OK"))
        btn_cancel = QPushButton(_("Cancel"))
        buttons.addButton(btn_ok, QDialogButtonBox.ButtonRole.AcceptRole)
        buttons.addButton(btn_cancel, QDialogButtonBox.ButtonRole.RejectRole)

        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_data(self):
        """Return collection name and country string."""
        return self.edit_name.text().strip(), self.combo_country.currentText()