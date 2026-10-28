"""
SDAbout Dialog Module
---------------------
Displays information about the StampDatabase application, its features,
and author details in both French and English with scrollable HTML text.

Author: Boris du Reau
Year: 2026
"""

import sys
from pathlib import Path
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QTextBrowser, QDialogButtonBox
)
from PyQt6.QtGui import QPixmap, QFont

# Localization setup
import gettext
from SDAppLanguage import get_language

gettext.find("SDAboutDlg")
translate = gettext.translation('SDAboutDlg', localedir='locale', languages=[get_language()], fallback=True)
translate.install()
_ = translate.gettext


class SDAboutDlg(QDialog):
    """Scrollable 'About' dialog for StampDatabase."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(_("About StampDatabase"))
        self.resize(580, 480)

        # Résolution dynamique du dossier d'Images
        self.base_dir = self._get_app_dir()
        self.images_dir = self._get_resource_dir("Images")

        self.createDlg()

    def _get_app_dir(self) -> Path:
        """Détermine le répertoire racine de l'application."""
        if getattr(sys, 'frozen', False):
            return Path(sys.executable).resolve().parent
        else:
            script_dir = Path(__file__).resolve().parent
            parent_dir = script_dir.parent

            if any((parent_dir / folder).exists() for folder in ["Databases", "Images", "Photos", "docs", "Help", "locale"]):
                return parent_dir

            return script_dir

    def _get_resource_dir(self, folder_name: str) -> Path:
        """Résout le dossier de ressources spécifié."""
        res_dir = self.base_dir / folder_name
        if res_dir.exists():
            return res_dir
        return Path(__file__).resolve().parent / folder_name

    def createDlg(self):
        main_layout = QVBoxLayout()

        # En-tête : Icône + Titre
        header_layout = QHBoxLayout()

        logo = QLabel()
        logo_path = self.images_dir / 'StampDB.png'
        if not logo_path.exists():
            logo_path = Path('../Images/StampDB.png')

        pixmap = QPixmap(str(logo_path))
        if not pixmap.isNull():
            logo.setPixmap(pixmap.scaledToWidth(72, Qt.TransformationMode.SmoothTransformation))
        header_layout.addWidget(logo)

        title_label = QLabel(_("StampDatabase"))
        title_font = QFont()
        title_font.setPointSize(18)
        title_font.setBold(True)
        title_label.setFont(title_font)
        header_layout.addWidget(title_label)
        header_layout.addStretch()

        main_layout.addLayout(header_layout)

        # Zone de texte HTML défilante
        text_browser = QTextBrowser()
        text_browser.setOpenExternalLinks(True)
        text_browser.setHtml(self.get_about_text_html())
        main_layout.addWidget(text_browser)

        # OK Button
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)

        # --- Traduction du bouton OK ---
        ok_button = button_box.button(QDialogButtonBox.StandardButton.Ok)
        if ok_button:
            ok_button.setText(_("OK"))

        button_box.accepted.connect(self.accept)
        main_layout.addWidget(button_box)

        self.setLayout(main_layout)

    def get_about_text_html(self) -> str:
        """Retourne la description formatée en HTML selon la langue sélectionnée."""
        lang = get_language()

        base_css = """
        <style>
            body { font-family: sans-serif; font-size: 10.5pt; line-height: 1.4; color: #222; }
            h2 { color: #1a365d; border-bottom: 1px solid #cbd5e0; padding-bottom: 4px; margin-top: 15px; }
            h3 { color: #2b6cb0; margin-bottom: 5px; }
            ul { margin-left: -15px; }
            li { margin-bottom: 4px; }
            .author { font-style: italic; color: #4a5568; margin-bottom: 15px; }
        </style>
        """

        if lang == "fr":
            content = """
            <h2>À propos de StampDatabase</h2>
            <div class="author">
                <b>Auteur :</b> Boris du Reau<br>
                <b>Version :</b> 1.0.0 (2002-2026)
            </div>

            <h3>Description de l'application</h3>
            <p>
                <b>StampDatabase</b> est l'outil d'administration et de gestion des catalogues 
                de timbres par pays pour les applications de la suite <b>StampAlbum</b> et <b>StampCatalogue</b>.
            </p>

            <h3>Fonctionnalités principales</h3>
            <ul>
                <li><b>Support Multi-moteurs :</b> Prise en charge transparente des bases de données SQLite (.db) et Microsoft Access (.mdb).</li>
                <li><b>Édition complète :</b> Ajout, modification, suppression et annulation/Rétablissement (Undo/Redo) d'enregistrements de timbres.</li>
                <li><b>Import / Export CSV :</b> Échanges de données faciles avec personnalisation des séparateurs (virgule ou point-virgule).</li>
                <li><b>Conversion Access vers SQLite :</b> Migration rapide de vos anciennes bases Access vers le format SQLite.</li>
                <li><b>Gestion des métadonnées :</b> Consultation et édition de la table d'informations (db_info : auteur, version, pays, système de catalogue).</li>
            </ul>
            """
        else:
            content = """
            <h2>About StampDatabase</h2>
            <div class="author">
                <b>Author:</b> Boris du Reau<br>
                <b>Version:</b> 1.0.0 (2002-2026)
            </div>

            <h3>Application Overview</h3>
            <p>
                <b>StampDatabase</b> is the catalogue administration tool for managing country-specific 
                stamp databases used by <b>StampAlbum</b> and <b>StampCatalogue</b>.
            </p>

            <h3>Key Features</h3>
            <ul>
                <li><b>Multi-Engine Support:</b> Seamless handling of SQLite (.db) and Microsoft Access (.mdb) databases.</li>
                <li><b>Full Record Editing:</b> Add, modify, delete, and full Undo/Redo support for catalogue entries.</li>
                <li><b>CSV Import / Export:</b> Easy data migration supporting custom delimiters (comma or semicolon).</li>
                <li><b>Access to SQLite Conversion:</b> Quickly convert legacy MS Access catalogues into SQLite format.</li>
                <li><b>Metadata Management:</b> Inspect and update database information (db_info: author, version, country, catalogue system).</li>
            </ul>
            """

        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            {base_css}
        </head>
        <body>
            {content}
        </body>
        </html>
        """