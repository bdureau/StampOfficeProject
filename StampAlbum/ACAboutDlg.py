"""
ACAboutDlg Dialog Module
------------------------
Displays information about the Album Converter application, its features,
supported formats, and author details in French or English with scrollable
HTML text. Visually and architecturally inspired by SAAboutDlg.py.

Author: Boris du Reau
Date: 2026-11-01
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

try:
    from AppLanguage import get_language
except ImportError:
    def get_language() -> str:
        return "en"


def _(text: str) -> str:
    try:
        lang = get_language()
        localedir = Path(__file__).resolve().parent / "locale"
        if not localedir.exists():
            localedir = Path(__file__).resolve().parent.parent / "locale"
        trans = gettext.translation('AlbumConverter', localedir=str(localedir), languages=[lang], fallback=True)
        return trans.gettext(text)
    except Exception:
        return text


class ACAboutDlg(QDialog):
    """Scrollable 'About' dialog displaying Album Converter overview in FR/EN."""

    def __init__(self, parent=None, lang: str = None):
        super(ACAboutDlg, self).__init__(parent)
        self.lang = lang if lang is not None else get_language()

        self.setWindowTitle(_("About the album converter"))
        self.resize(560, 480)

        # Dynamic resolution of application and resource directories
        self.base_dir = self._get_app_dir()
        self.images_dir = self._get_resource_dir("Images")

        self.createDlg()

    def _get_app_dir(self) -> Path:
        """Determine the root application directory."""
        if getattr(sys, 'frozen', False):
            if hasattr(sys, '_MEIPASS'):
                return Path(sys._MEIPASS)
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
        logo_path = self.images_dir / 'conv_app.png'
        if not logo_path.exists():
            logo_path = self.images_dir / 'stamp_book.png'
        if not logo_path.exists():
            logo_path = Path('conv_app.png')

        pixmap = QPixmap(str(logo_path))
        if not pixmap.isNull():
            logo.setPixmap(pixmap.scaledToWidth(64, Qt.TransformationMode.SmoothTransformation))
        header_layout.addWidget(logo)

        title_label = QLabel(_("Stamp Album - Album converter"))
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

        # OK / Close Button
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        ok_button = button_box.button(QDialogButtonBox.StandardButton.Ok)
        if ok_button:
            ok_button.setText(_("OK") if self.lang == "fr" else "OK")

        button_box.accepted.connect(self.accept)
        main_layout.addWidget(button_box)

        self.setLayout(main_layout)

    def get_about_text_html(self) -> str:
        """Return the description formatted in HTML depending on the selected language."""
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

        if self.lang == "fr":
            content = """
            <h2>À propos de l'Album Converter</h2>
            <div class="author">
                <b>Auteur :</b> Boris du Reau<br>
                <b>Version :</b> 1.0 (2026)<br>
                <b>Fait partie de :</b> Suite Stamp Album &amp; stampOffice
            </div>

            <h3>Description de l'application</h3>
            <p>
                <b>Album Converter</b> est un utilitaire de conversion par lot permettant de transformer 
                les albums de timbres créés avec d'autres logiciels en albums natifs Stamp Album (<code>.sta</code>), 
                qu'il s'agisse d'un seul fichier ou de centaines d'albums à la fois, sans devoir ouvrir l'éditeur.
            </p>

            <h3>Formats pris en charge</h3>
            <ul>
                <li><b>AlbumEasy :</b> Fichiers de description <code>.txt</code>, avec prise en charge complète des images de timbres associées.</li>
                <li><b>Feuille Album 4 :</b> Albums Excel au format <code>.xls</code> (Excel 97-2003), avec conversion feuille par feuille et extraction des images.</li>
            </ul>

            <h3>Fonctionnalités principales</h3>
            <ul>
                <li><b>Conversion autonome :</b> Réutilise les moteurs et importateurs officiels de Stamp Album sans lancer l'interface d'édition lourde.</li>
                <li><b>Sauvegarde incrémentale :</b> Chaque album est enregistré dès la fin de son traitement ; l'interruption préserve les albums déjà convertis.</li>
                <li><b>Gestion des conflits :</b> Options complètes en cas de fichier existant (demander, remplacer, ignorer ou renommer automatiquement).</li>
                <li><b>Rapports détaillés :</b> Suivi en direct du statut (pages, timbres, alertes) et exportation d'un rapport de conversion texte.</li>
            </ul>
            """
        else:
            content = """
            <h2>About Album Converter</h2>
            <div class="author">
                <b>Author:</b> Boris du Reau<br>
                <b>Version:</b> 1.0 (2026)<br>
                <b>Part of:</b> Stamp Album &amp; stampOffice Suite
            </div>

            <h3>Application Overview</h3>
            <p>
                <b>Album Converter</b> is a stand-alone batch utility designed to turn stamp albums 
                created with third-party software into native Stamp Album files (<code>.sta</code>). 
                It seamlessly converts single files or hundreds of albums at once without opening the visual editor.
            </p>

            <h3>Supported Formats</h3>
            <ul>
                <li><b>AlbumEasy:</b> Plain text layout files (<code>.txt</code>), including referenced stamp illustrations.</li>
                <li><b>Feuille Album 4:</b> Excel workbooks in <code>.xls</code> format (Excel 97-2003), with page-by-page mapping and embedded pictures.</li>
            </ul>

            <h3>Key Features</h3>
            <ul>
                <li><b>Engine Consistency:</b> Shares the core importers and models of Stamp Album for 100% faithful file rendering.</li>
                <li><b>Immediate Persistence:</b> Each album is written to disk as soon as it finishes; stopping the queue keeps finished projects intact.</li>
                <li><b>Conflict Management:</b> Flexible strategies for existing destination files (ask, replace, skip, or rename).</li>
                <li><b>Detailed Batch Reporting:</b> Live breakdown of pages, stamps, and format warnings with automated log generation.</li>
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