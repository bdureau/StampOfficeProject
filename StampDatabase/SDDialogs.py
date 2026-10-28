"""
SDDialogs Module
----------------
Contains auxiliary dialogs for Database Information and New Database Creation.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLabel, QLineEdit,
    QTextEdit, QComboBox, QDialogButtonBox
)

import gettext
from SDAppLanguage import get_language

gettext.find("SDDialogs")
translate = gettext.translation(
    'SDDialogs', localedir='locale', languages=[get_language()], fallback=True
)
translate.install()
_ = translate.gettext


class DatabaseInfoDialog(QDialog):
    """Dialog displaying and editing db_info database metadata."""

    def __init__(self, db_adapter, country_name, parent=None):
        super().__init__(parent)
        self.db_adapter = db_adapter
        self.setWindowTitle(_("Database Information") + f" - {country_name}")
        self.resize(450, 320)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.info_data, self.missing_cols = db_adapter.get_db_info()

        form.addRow(_("Database Name:"), QLabel(f"<b>{country_name}</b>"))
        form.addRow(_("Database Type:"), QLabel(db_adapter.db_type.upper()))

        self.fields = {}

        self.fields["Author"] = QLineEdit(self.info_data.get("Author", ""))
        form.addRow(_("Author:"), self.fields["Author"])

        self.fields["Country"] = QLineEdit(self.info_data.get("Country", country_name))
        form.addRow(_("Country:"), self.fields["Country"])

        self.fields["Description"] = QTextEdit()
        self.fields["Description"].setPlainText(self.info_data.get("Description", ""))
        self.fields["Description"].setMaximumHeight(60)
        form.addRow(_("Description:"), self.fields["Description"])

        self.fields["Version"] = QLineEdit(self.info_data.get("Version", "1.0"))
        form.addRow(_("Version:"), self.fields["Version"])

        self.combo_catalogue = QComboBox()
        self.combo_catalogue.setEditable(True)
        self.combo_catalogue.addItems(["Yvert", "Philatelix", "Scott", "Michel", "Stanley Gibbons", "Custom"])
        self.combo_catalogue.setCurrentText(self.info_data.get("catalogue", "Yvert"))
        form.addRow(_("Catalogue System:"), self.combo_catalogue)

        self.combo_language = QComboBox()
        self.combo_language.addItem(_("French"), "fr")
        self.combo_language.addItem(_("English"), "en")
        lang_val = self.info_data.get("Language", "fr")
        idx = self.combo_language.findData(lang_val)
        if idx != -1:
            self.combo_language.setCurrentIndex(idx)
        else:
            self.combo_language.setCurrentText(lang_val)
        form.addRow(_("Data Language:"), self.combo_language)

        for col in self.missing_cols:
            if col in self.fields:
                self.fields[col].setEnabled(False)
                self.fields[col].setToolTip(_("Column missing in database db_info table."))
            elif col == "Catalogue":
                self.combo_catalogue.setEnabled(False)
            elif col == "Language":
                self.combo_language.setEnabled(False)

        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        ok_btn = buttons.button(QDialogButtonBox.StandardButton.Ok)
        if ok_btn:
            ok_btn.setText(_("OK"))
        cancel_btn = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        if cancel_btn:
            cancel_btn.setText(_("Cancel"))
        buttons.accepted.connect(self.save_info)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def save_info(self):
        """Save form modifications back to db_info table."""
        updated_dict = {
            "Author": self.fields["Author"].text().strip(),
            "Country": self.fields["Country"].text().strip(),
            "Description": self.fields["Description"].toPlainText().strip(),
            "Version": self.fields["Version"].text().strip(),
            "Catalogue": self.combo_catalogue.currentText().strip(),
            "Language": self.combo_language.currentData() or self.combo_language.currentText().strip()
        }
        self.db_adapter.update_db_info(updated_dict)
        self.accept()


class CreateDatabaseDialog(QDialog):
    """Dialog to create a new empty SQLite database."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(_("Create New Empty SQLite Database"))
        self.resize(380, 220)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.edit_country = QLineEdit()
        self.edit_country.setPlaceholderText(_("e.g. Monaco, Belgium..."))

        self.edit_author = QLineEdit("Boris du Reau")
        self.edit_desc = QLineEdit()
        self.combo_catalogue = QComboBox()
        self.combo_catalogue.setEditable(True)
        self.combo_catalogue.addItems(["Yvert", "Philatelix", "Scott", "Michel", "Stanley Gibbons"])

        self.combo_language = QComboBox()
        self.combo_language.addItem("Français", "fr")
        self.combo_language.addItem("English", "en")

        form.addRow(_("Country / DB Name:"), self.edit_country)
        form.addRow(_("Author:"), self.edit_author)
        form.addRow(_("Description:"), self.edit_desc)
        form.addRow(_("Catalogue System:"), self.combo_catalogue)
        form.addRow(_("Data Language:"), self.combo_language)

        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        ok_btn = buttons.button(QDialogButtonBox.StandardButton.Ok)
        if ok_btn:
            ok_btn.setText(_("OK"))
        cancel_btn = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        if cancel_btn:
            cancel_btn.setText(_("Cancel"))
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_data(self):
        return {
            "country": self.edit_country.text().strip(),
            "author": self.edit_author.text().strip(),
            "description": self.edit_desc.text().strip(),
            "catalogue": self.combo_catalogue.currentText().strip(),
            "language": self.combo_language.currentData()
        }