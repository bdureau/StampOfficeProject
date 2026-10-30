"""
SCAbout Dialog Module
---------------------
Displays information about the StampCatalogue application, its features,
and author details in both French and English with scrollable HTML text.

Author: Boris du Reau
Year: 2026
"""

import sys
from pathlib import Path
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QTextBrowser, QDialogButtonBox, QPushButton
)
from PyQt6.QtGui import QPixmap, QFont

# Localization setup
import gettext
from SCAppLanguage import get_language

gettext.find("StampCatalogue")
translate = gettext.translation('StampCatalogue', localedir='locale', languages=[get_language()], fallback=True)
translate.install()
_ = translate.gettext


class SCAboutDlg(QDialog):
    """Scrollable 'About' dialog for StampCatalogue."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(_("About StampCatalogue"))
        self.resize(580, 480)

        # Dynamically resolve images directory
        self.base_dir = self._get_app_dir()
        self.images_dir = self._get_resource_dir("Images")

        self.createDlg()

    def _get_app_dir(self) -> Path:
        """Determine the root application directory."""
        if getattr(sys, 'frozen', False):
            return Path(sys.executable).resolve().parent
        else:
            script_dir = Path(__file__).resolve().parent
            parent_dir = script_dir.parent

            if any((parent_dir / folder).exists() for folder in ["Databases", "Images", "Photos", "docs", "Help", "locale"]):
                return parent_dir

            return script_dir

    def _get_resource_dir(self, folder_name: str) -> Path:
        """Resolve the specified resource directory."""
        res_dir = self.base_dir / folder_name
        if res_dir.exists():
            return res_dir
        return Path(__file__).resolve().parent / folder_name

    def createDlg(self):
        main_layout = QVBoxLayout()

        # Header: Icon + Title
        header_layout = QHBoxLayout()

        logo = QLabel()
        logo_path = self.images_dir / 'StampCatalogue.png'
        if not logo_path.exists():
            logo_path = Path('../Images/StampCatalogue.png')

        pixmap = QPixmap(str(logo_path))
        if not pixmap.isNull():
            logo.setPixmap(pixmap.scaledToWidth(72, Qt.TransformationMode.SmoothTransformation))
        header_layout.addWidget(logo)

        title_label = QLabel(_("StampCatalogue"))
        title_font = QFont()
        title_font.setPointSize(18)
        title_font.setBold(True)
        title_label.setFont(title_font)
        header_layout.addWidget(title_label)
        header_layout.addStretch()

        main_layout.addLayout(header_layout)

        # Scrollable HTML text area
        text_browser = QTextBrowser()
        text_browser.setOpenExternalLinks(True)
        text_browser.setHtml(self.get_about_text_html())
        main_layout.addWidget(text_browser)

        # Translatable OK button
        button_box = QDialogButtonBox()
        ok_button = QPushButton(_("OK"))
        button_box.addButton(ok_button, QDialogButtonBox.ButtonRole.AcceptRole)
        button_box.accepted.connect(self.accept)
        main_layout.addWidget(button_box)

        self.setLayout(main_layout)

    def get_about_text_html(self) -> str:
        """Return the HTML-formatted description according to the selected language."""
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
            <h2>À propos de StampCatalogue</h2>
            <div class="author">
                <b>Auteur :</b> Boris du Reau<br>
                <b>Version :</b> 1.2 (2026)
            </div>

            <h3>Description de l'application</h3>
            <p>
                <b>StampCatalogue</b> est une application autonome conçue pour les philatélistes 
                souhaitant gérer leurs collections de timbres, rechercher dans les catalogues 
                de différents pays et suivre l'état de possession de leurs pièces.
            </p>

            <h3>Fonctionnalités principales</h3>
            <ul>
                <li><b>Multi-collections :</b> Création et gestion de plusieurs collections personnelles associées à divers pays.</li>
                <li><b>Consultation de catalogues :</b> Recherche intuitive par catégorie, année et numéro de catalogue (Yvert).</li>
                <li><b>Gestion des états :</b> Suivi précis (Possédé, Manco, Commandé), état de conservation, prix d'achat et notes.</li>
                <li><b>Visualisation des visuels :</b> Chargement automatique des photos des timbres.</li>
                <li><b>Export Mancoliste :</b> Génération dynamique de fichiers Excel (*.xlsx) récapitulant les timbres manquants.</li>
            </ul>
            """
        else:
            content = """
            <h2>About StampCatalogue</h2>
            <div class="author">
                <b>Author:</b> Boris du Reau<br>
                <b>Version:</b> 1.2 (2026)
            </div>

            <h3>Application Overview</h3>
            <p>
                <b>StampCatalogue</b> is a standalone desktop application tailored for philatelists 
                to track multiple stamp collections, browse country catalogues, and manage 
                ownership status.
            </p>

            <h3>Key Features</h3>
            <ul>
                <li><b>Multi-Collection Management:</b> Create and manage distinct collections linked to various countries.</li>
                <li><b>Catalogue Browser:</b> Filter stamps easily by type, issue year, or catalogue number.</li>
                <li><b>Ownership Tracking:</b> Record status (Owned, Missing, Ordered), condition, purchase price, and personal notes.</li>
                <li><b>Photo Viewer:</b> Automatic resolution and display of stamp images.</li>
                <li><b>Mancolist Export:</b> Directly export missing stamp reports into formatted Excel (.xlsx) spreadsheets.</li>
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