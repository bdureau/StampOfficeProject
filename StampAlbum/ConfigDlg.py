from PageBorder import PageBorder
from PyQt6 import QtGui
from pathlib import Path
from PyQt6.QtWidgets import (
    QMessageBox, QGraphicsRectItem,
    QGraphicsScene, QComboBox, QRadioButton, QButtonGroup, QGroupBox, QListWidgetItem,
    QGraphicsView, QApplication, QLabel, QMainWindow, QMenuBar, QMenu, QHBoxLayout, QListView,
    QToolBar, QGraphicsTextItem, QGraphicsItemGroup, QDialog, QPushButton, QListWidget,
    QLineEdit, QFormLayout, QStatusBar, QTabWidget, QWidget, QVBoxLayout, QDialogButtonBox, QPlainTextEdit,
    QFontComboBox, QSpinBox
)
from PyQt6.QtGui import QFont
import configparser
import sys
import gettext
from AppLanguage import get_language
from SAAppPaths import get_app_dir, get_config_path, list_countries, read_config_into

gettext.find("ConfigDlg")
translate = gettext.translation('ConfigDlg', localedir='locale', languages=[get_language()], fallback=True)
translate.install()
_ = translate.gettext


class ConfigDlg(QDialog):
    PAPER_A4 = "A4"
    PAPER_LETTER = "Letter"

    def __init__(self, parent=None):
        super(ConfigDlg, self).__init__(parent)
        self.setWindowTitle(_("Application configuration"))
        self.configParser = configparser.RawConfigParser()

        self.base_dir = get_app_dir()
        self.images_dir = self._get_resource_dir("Images")

        icon_path = self.images_dir / "stamp_book.png"
        if icon_path.exists():
            self.setWindowIcon(QtGui.QIcon(str(icon_path)))
        else:
            self.setWindowIcon(QtGui.QIcon('stamp_book.png'))

        self.configFilePath = get_config_path()

        read_config_into(self.configParser, self.configFilePath)
        self.createDlg()

    def get_app_dir(self) -> Path:
        """Return the base directory path, compatible with PyInstaller frozen executables."""
        return get_app_dir()

    def _get_app_dir(self) -> Path:
        """
        Détermine le répertoire racine de l'application.

        - Si exécuté en EXE : renvoie le répertoire contenant l'exécutable.
        - Si exécuté depuis Python (.py dans un sous-dossier) : remonte au dossier parent
          si 'Databases', 'Images', 'Photos' ou 'docs' s'y trouve, sinon renvoie le dossier du script.
        """
        if getattr(sys, 'frozen', False):
            return Path(sys.executable).resolve().parent
        else:
            script_dir = Path(__file__).resolve().parent
            parent_dir = script_dir.parent

            if any((parent_dir / folder).exists() for folder in ["Databases", "Images", "Photos", "docs", "Help", "locale"]):
                return parent_dir

            return script_dir

    def _get_resource_dir(self, folder_name: str) -> Path:
        """Résout un dossier de ressources (Images, docs, etc.) depuis le dossier applicatif ou relatif."""
        res_dir = self.base_dir / folder_name
        if res_dir.exists():
            return res_dir
        return Path(__file__).resolve().parent / folder_name

    def createDlg(self):
        # Default Copyright
        self.eCopyRight = QLineEdit()
        self.eCopyRight.setFixedWidth(400)

        # Language Selection
        self.selectedLanguageCombo = QComboBox()
        self.selectedLanguageCombo.setMaximumWidth(200)
        self.selectedLanguageCombo.addItem("Français", "fr")
        self.selectedLanguageCombo.addItem("English", "en")

        # Default Paper Size
        self.selectedPaperCombo = QComboBox()
        self.selectedPaperCombo.setMaximumWidth(200)
        self.selectedPaperCombo.addItem("A4 (210 x 297 mm)", self.PAPER_A4)
        self.selectedPaperCombo.addItem("US Letter (215.9 x 279.4 mm)", self.PAPER_LETTER)

        # Default Border Type
        self.selectedBorderCombo = QComboBox()
        self.selectedBorderCombo.setMaximumWidth(200)
        self.selectedBorderCombo.addItem(_("Triple (Classic)"), PageBorder.STYLE_TRIPLE)
        self.selectedBorderCombo.addItem(_("Simple (Frame)"), PageBorder.STYLE_SIMPLE)
        self.selectedBorderCombo.addItem(_("Greek (Notched)"), PageBorder.STYLE_GREEK)
        self.selectedBorderCombo.addItem(_("Dentelle (Philately)"), PageBorder.STYLE_DENTELLE)

        # Binding Margin Size in mm
        self.marginSizeSpin = QSpinBox()
        self.marginSizeSpin.setRange(0, 100)
        self.marginSizeSpin.setValue(19)
        self.marginSizeSpin.setSuffix(" mm")
        self.marginSizeSpin.setMaximumWidth(100)

        # Binding Margin Position
        self.marginPositionCombo = QComboBox()
        self.marginPositionCombo.setMaximumWidth(200)
        self.marginPositionCombo.addItem(_("Left"), "left")
        self.marginPositionCombo.addItem(_("Right"), "right")

        # Default Font Selection
        self.selectedFontCombo = QFontComboBox()
        self.selectedFontCombo.setMaximumWidth(250)

        # Default Country
        self.selectedCountryCombo = QComboBox()
        self.selectedCountryCombo.setMaximumWidth(200)

        # Default Database
        self.selectedDatabaseCombo = QComboBox()
        self.selectedDatabaseCombo.setMaximumWidth(100)

        # OK / Cancel Buttons
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)

        ok_button = bb.button(QDialogButtonBox.StandardButton.Ok)
        if ok_button:
            ok_button.setText(_("OK"))

        cancel_button = bb.button(QDialogButtonBox.StandardButton.Cancel)
        if cancel_button:
            cancel_button.setText(_("Cancel"))

        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)

        flo = QFormLayout()
        flo.addRow(_("Default Copyright:"), self.eCopyRight)
        flo.addRow(_("Language:"), self.selectedLanguageCombo)
        flo.addRow(_("Paper format:"), self.selectedPaperCombo)
        flo.addRow(_("Border type:"), self.selectedBorderCombo)
        flo.addRow(_("Margin size:"), self.marginSizeSpin)
        flo.addRow(_("Margin position:"), self.marginPositionCombo)
        flo.addRow(_("Default Font:"), self.selectedFontCombo)
        flo.addRow(_("Default Country:"), self.selectedCountryCombo)
        flo.addRow(_("Default Database:"), self.selectedDatabaseCombo)
        flo.addRow(bb)

        self.setLayout(flo)
        self.readConfig()

    def readConfig(self):
        self.selectedDatabaseCombo.addItem("Access")
        self.selectedDatabaseCombo.addItem("sqlite")

        db_type = "sqlite"
        if self.configParser.has_option('CONF', 'database type'):
            db_type = self.configParser.get('CONF', 'database type')
        self.selectedDatabaseCombo.setCurrentText(db_type)

        self.selectedDatabaseCombo.currentTextChanged.connect(self.refreshCountries)
        self.refreshCountries(db_type)

        if self.configParser.has_section('CONF'):
            conf = self.configParser['CONF']
            if self.configParser.has_option('CONF', 'copyright'):
                self.eCopyRight.setText(conf['copyright'])
            if self.configParser.has_option('CONF', 'language'):
                lang = conf['language']
                idx = self.selectedLanguageCombo.findData(lang)
                if idx != -1:
                    self.selectedLanguageCombo.setCurrentIndex(idx)
            if self.configParser.has_option('CONF', 'paper format'):
                paper_fmt = conf['paper format']
                idx = self.selectedPaperCombo.findData(paper_fmt)
                if idx != -1:
                    self.selectedPaperCombo.setCurrentIndex(idx)
            if self.configParser.has_option('CONF', 'default country'):
                self.selectedCountryCombo.setCurrentText(str(conf['default country']))
            if self.configParser.has_option('CONF', 'type encadrement'):
                border_type = conf['type encadrement']
                index = self.selectedBorderCombo.findData(border_type)
                if index != -1:
                    self.selectedBorderCombo.setCurrentIndex(index)
                else:
                    self.selectedBorderCombo.setCurrentText(border_type)
            if self.configParser.has_option('CONF', 'margin size'):
                try:
                    self.marginSizeSpin.setValue(int(float(conf['margin size'])))
                except ValueError:
                    self.marginSizeSpin.setValue(19)
            if self.configParser.has_option('CONF', 'margin position'):
                pos = conf['margin position'].lower()
                idx = self.marginPositionCombo.findData(pos)
                if idx != -1:
                    self.marginPositionCombo.setCurrentIndex(idx)
            if self.configParser.has_option('CONF', 'default font'):
                font_name = conf['default font']
                self.selectedFontCombo.setCurrentFont(QFont(font_name))
            if self.configParser.has_option('CONF', 'database type'):
                self.selectedDatabaseCombo.setCurrentText(str(conf['database type']))
        else:
            self.configParser["CONF"] = {
                "copyright": "CopyRight © Boris du Reau 2003-2026",
                "language": "fr",
                "paper format": self.PAPER_A4,
                "default country": "France",
                "type encadrement": PageBorder.STYLE_TRIPLE,
                "margin size": "19",
                "margin position": "left",
                "default font": "Arial",
                "database type": "sqlite"
            }
            with open(self.configFilePath, 'w', encoding="utf-8") as config:
                self.configParser.write(config)

    def refreshCountries(self, db_type):
        """Reload the list of countries based on the selected database engine."""
        current = self.selectedCountryCombo.currentText()
        self.stampCountries = list_countries(db_type)
        self.selectedCountryCombo.clear()
        self.selectedCountryCombo.addItems(self.stampCountries)
        if current:
            self.selectedCountryCombo.setCurrentText(current)

    def saveConfig(self):
        selected_lang = self.selectedLanguageCombo.currentData() or "fr"
        selected_paper = self.selectedPaperCombo.currentData() or self.PAPER_A4
        selected_border = self.selectedBorderCombo.currentData() or self.selectedBorderCombo.currentText()
        selected_font = self.selectedFontCombo.currentText()
        selected_pos = self.marginPositionCombo.currentData() or "left"

        self.configParser["CONF"] = {
            "copyright": self.eCopyRight.text(),
            "language": selected_lang,
            "paper format": selected_paper,
            "default country": self.selectedCountryCombo.currentText(),
            "type encadrement": selected_border,
            "margin size": str(self.marginSizeSpin.value()),
            "margin position": selected_pos,
            "default font": selected_font,
            "database type": self.selectedDatabaseCombo.currentText()
        }
        with open(self.configFilePath, 'w', encoding="utf-8") as config:
            self.configParser.write(config)

    def accept(self):
        self.saveConfig()
        super().accept()