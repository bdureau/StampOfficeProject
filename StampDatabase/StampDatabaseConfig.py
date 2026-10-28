"""
StampDatabaseConfig Module
--------------------------
Handles configuration file management and the configuration dialog
for the StampDatabase application.
"""

import configparser
from pathlib import Path
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QComboBox, QDialogButtonBox, QMessageBox
)

import gettext
from SDAppLanguage import get_language

gettext.find("StampDatabaseConfig")
translate = gettext.translation(
    'StampDatabaseConfig', localedir='locale', languages=[get_language()], fallback=True
)
translate.install()
_ = translate.gettext


class AppConfigManager:
    """Manages loading and persisting configuration settings in StampDatabase.cfg."""

    def __init__(self, config_path: Path):
        self.config_path = config_path
        self.config = configparser.ConfigParser()
        self.language = "fr"
        self.db_type = "sqlite"
        self.last_country = ""
        self.load_config()

    def load_config(self):
        if self.config_path.exists():
            self.config.read(self.config_path, encoding='utf-8')
            if 'General' in self.config:
                self.language = self.config['General'].get('language', 'fr')
                self.db_type = self.config['General'].get('db_type', 'sqlite')
                self.last_country = self.config['General'].get('last_country', '')

    def save_config(self, language=None, db_type=None, last_country=None):
        if language is not None:
            self.language = language
        if db_type is not None:
            self.db_type = db_type
        if last_country is not None:
            self.last_country = last_country

        if 'General' not in self.config:
            self.config['General'] = {}

        self.config['General']['language'] = self.language
        self.config['General']['db_type'] = self.db_type
        self.config['General']['last_country'] = self.last_country

        with open(self.config_path, 'w', encoding='utf-8') as f:
            self.config.write(f)

class ConfigDialog(QDialog):
    """Configuration dialog for language and database preferences."""

    def __init__(self, config_manager: AppConfigManager, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.setWindowTitle(_("Application Configuration"))
        self.resize(350, 150)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.combo_lang = QComboBox()
        self.combo_lang.addItem("English", "en")
        self.combo_lang.addItem("Français", "fr")

        idx_lang = self.combo_lang.findData(self.config_manager.language)
        if idx_lang != -1:
            self.combo_lang.setCurrentIndex(idx_lang)

        self.combo_db_type = QComboBox()
        self.combo_db_type.addItem("SQLite", "sqlite")
        self.combo_db_type.addItem("Microsoft Access", "access")

        idx_db = self.combo_db_type.findData(self.config_manager.db_type)
        if idx_db != -1:
            self.combo_db_type.setCurrentIndex(idx_db)

        form.addRow(_("Language:"), self.combo_lang)
        form.addRow(_("Database Type:"), self.combo_db_type)

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

    def get_selected_config(self):
        """Retourne les valeurs sélectionnées dans la boîte de dialogue."""
        return {
            "language": self.combo_lang.currentData(),
            "db_type": self.combo_db_type.currentData()
        }

def open_config(main_window):
    """Open Application Configuration Dialog and update StampDatabase.cfg upon acceptance."""
    dialog = ConfigDialog(main_window.config_manager, main_window)
    if dialog.exec() == QDialog.DialogCode.Accepted:
        new_settings = dialog.get_selected_config()
        selected_db_type = new_settings["db_type"]
        selected_language = new_settings["language"]

        # Importer le test MS Access localisé pour éviter les imports circulaires
        from StampDatabase import test_ms_access_support

        if selected_db_type == "access" and not test_ms_access_support():
            main_window.show_access_warning_popup()
            selected_db_type = "sqlite"

        main_window.config_manager.save_config(
            language=selected_language,
            db_type=selected_db_type,
            last_country=main_window.current_country or ""
        )

        import SDAppLanguage
        SDAppLanguage.get_language(force_reload=True)

        main_window.current_db_type = selected_db_type
        main_window._load_country_list()

        QMessageBox.information(
            main_window,
            _("Configuration"),
            _("Configuration updated successfully.\nPlease restart the application to apply language changes.")
        )