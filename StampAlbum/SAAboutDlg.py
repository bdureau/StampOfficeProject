"""
About Dialog Module
-------------------
Displays information about the Stamp Album application, its features,
and author details in both French and English with scrollable text.

Author: Boris du Reau
"""

import sys
from pathlib import Path
from PyQt6.QtCore import (Qt, QUrl)
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QTextBrowser, QDialogButtonBox
)
from PyQt6.QtGui import QPixmap, QFont

# Localization setup
import gettext
from AppLanguage import get_language
gettext.find("SAAboutDlg")
translate = gettext.translation('SAAboutDlg', localedir='locale', languages=[get_language()], fallback=True)
translate.install()
_ = translate.gettext

class AboutDlg(QDialog):
    """Scrollable 'About' dialog displaying application overview in FR/EN."""

    def __init__(self, parent=None):
        super(AboutDlg, self).__init__(parent)
        self.setWindowTitle(_("About Stamp Album"))
        self.resize(550, 450)

        # Dynamic resolution of the Images directory
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

        # Header layout (Icon + Title)
        header_layout = QHBoxLayout()

        logo = QLabel()
        logo_path = self.images_dir / 'stamp_book.png'
        if not logo_path.exists():
            logo_path = Path('stamp_book.png')

        pixmap = QPixmap(str(logo_path))
        if not pixmap.isNull():
            logo.setPixmap(pixmap.scaledToWidth(64, Qt.TransformationMode.SmoothTransformation))
        header_layout.addWidget(logo)

        title_label = QLabel(_("Stamp Album"))
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        header_layout.addWidget(title_label)
        header_layout.addStretch()

        main_layout.addLayout(header_layout)

        # Scrollable text browser with HTML content
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
        """Return the description formatted in HTML depending on the selected language."""
        lang = get_language()

        # Shared CSS styles across languages
        base_css = """
        <style>
            body { font-family: sans-serif; font-size: 11pt; line-height: 1.4; color: #222; }
            h2 { color: #1a365d; border-bottom: 1px solid #cbd5e0; padding-bottom: 4px; margin-top: 15px; }
            h3 { color: #2b6cb0; margin-bottom: 5px; }
            ul { margin-left: -15px; }
            li { margin-bottom: 4px; }
            .author { font-style: italic; color: #4a5568; margin-bottom: 15px; }
        </style>
        """

        if lang == "fr":
            content = """
            <h2>À propos de Stamp Album</h2>
            <div class="author">
                <b>Auteur :</b> Boris du Reau<br>
                <b>Version :</b> 5.0.3 (2003-2026)
            </div>

            <h3>Description de l'application</h3>
            <p>
                <b>Stamp Album</b> est une application de création et de mise en page de pages 
                d'albums de timbres personnalisées. Initialement développée en VBA au début des 
                années 2000, elle a été entièrement réécrite en Python 3 et PyQt6.
            </p>

            <h3>Fonctionnalités principales</h3>
            <ul>
                <li><b>Gestion de catalogues :</b> Connexion à des bases de données de timbres (SQLite / Access) classées par pays, types et années.</li>
                <li><b>Mise en page graphique :</b> Positionnement précis des timbres, pochettes, titres, valeurs nominales et illustrations.</li>
                <li><b>Outils d'alignement :</b> Alignement automatique (gauche, droite, haut, bas) et distribution uniforme horizontale ou verticale.</li>
                <li><b>Personnalisation :</b> Ajout de bordures de pages de haute précision, numéros de pages, copyrights et années.</li>
                <li><b>Impression et Export :</b> Aperçu avant impression haute résolution et exportation d'albums complets ou de pages individuelles au format PDF.</li>
            </ul>
            """
        else:
            content = """
            <h2>About Stamp Album</h2>
            <div class="author">
                <b>Author:</b> Boris du Reau<br>
                <b>Version:</b> 5.0.3 (2003-2026)
            </div>

            <h3>Application Overview</h3>
            <p>
                <b>Stamp Album</b> is a desktop application designed to create and assemble custom 
                stamp album pages. Originally written in VBA in the early 2000s, it has been 
                fully modernized and re-engineered using Python 3 and PyQt6.
            </p>

            <h3>Key Features</h3>
            <ul>
                <li><b>Catalogue Management:</b> Connects to country-specific stamp Databases (SQLite / Access) organized by category, year, and catalogue numbers.</li>
                <li><b>Graphic Layout:</b> Precise placement of stamp mounts, illustrations, titles, nominal values, and descriptors.</li>
                <li><b>Alignment Tools:</b> Automatic item alignment (left, right, top, bottom) and equal horizontal/vertical distribution.</li>
                <li><b>Page Customization:</b> Insert decorative page borders, page numbers, copyright notices, and header years.</li>
                <li><b>Printing & Export:</b> High-resolution print preview and single/multi-page PDF export capabilities.</li>
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