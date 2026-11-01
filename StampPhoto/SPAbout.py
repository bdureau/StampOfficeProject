"""
SPAbout Dialog Module
---------------------
Displays information about the StampPhoto application, its features,
and author details in French or English (current language) with scrollable
HTML text. The dialog is rebuilt each time it is opened, ensuring it always
follows the active language chosen in the settings.

The logo (Images/StampPhoto.png) is found through SPAppPaths, so it is also
shown by the compiled version of StampPhoto.

Author: Boris du Reau
Date: 2026-11-01
"""

from pathlib import Path
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QTextBrowser, QDialogButtonBox, QPushButton
)
from PyQt6.QtGui import QPixmap, QFont

# Attempt to import centralized translation and path helpers if available;
# otherwise fallback to local defaults.
try:
    from SPAppLanguage import _, get_language
except ImportError:
    def _(text: str) -> str:
        return text

    def get_language() -> str:
        return "fr"

try:
    from SPAppPaths import find_resource
except ImportError:
    def find_resource(folder: str, filename: str):
        """Fallback: the folder next to the sources or in their parent folder."""
        base = Path(__file__).resolve().parent
        for path in (base / folder / filename, base.parent / folder / filename):
            if path.is_file():
                return path
        return None

# Logo files, by order of preference, in the Images folder
LOGO_FILES = ("StampPhoto.png", "app_icon.svg", "stamp_photo.png")


class SPAboutDlg(QDialog):
    """Scrollable 'About' dialog for StampPhoto following the SCAboutDlg model."""

    def __init__(self, parent=None, lang: str = None, tr_func=None):
        super().__init__(parent)
        self.tr_func = tr_func if tr_func is not None else _
        self.lang = lang if lang is not None else get_language()

        self.setWindowTitle(self.tr_func("About StampPhoto"))
        self.resize(580, 480)

        self.createDlg()

    def createDlg(self):
        """Build and arrange the dialog widgets."""
        main_layout = QVBoxLayout()

        # Header: Icon + Title
        header_layout = QHBoxLayout()

        logo = QLabel()
        logo_path = next((p for p in (find_resource("Images", f) for f in LOGO_FILES) if p is not None), None)

        pixmap = QPixmap(str(logo_path)) if logo_path is not None else QPixmap()
        if pixmap.isNull():
            # No logo file: icon embedded in the program
            try:
                from SPAppIcon import embedded_app_pixmap
                pixmap = embedded_app_pixmap(256)
            except ImportError:
                pass
        if not pixmap.isNull():
            logo.setPixmap(pixmap.scaledToWidth(72, Qt.TransformationMode.SmoothTransformation))
        header_layout.addWidget(logo)

        title_label = QLabel(self.tr_func("StampPhoto"))
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
        ok_button = QPushButton(self.tr_func("OK"))
        button_box.addButton(ok_button, QDialogButtonBox.ButtonRole.AcceptRole)
        button_box.accepted.connect(self.accept)
        main_layout.addWidget(button_box)

        self.setLayout(main_layout)

    def get_about_text_html(self) -> str:
        """Return the HTML-formatted description according to the active language."""
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
            <h2>À propos de StampPhoto</h2>
            <div class="author">
                <b>Auteur :</b> Boris du Reau<br>
                <b>Version :</b> 1.0 (2026)<br>
                <b>Fait partie de :</b> Suite stampOffice
            </div>

            <h3>Description de l'application</h3>
            <p>
                <b>StampPhoto</b> est une application dédiée à la visualisation, au tri et à la conversion 
                par lot des photographies et scans de timbres de collection.
            </p>

            <h3>Fonctionnalités principales</h3>
            <ul>
                <li><b>Visualisation dédiée :</b> Navigation fluide photo par photo au centre de la fenêtre avec ratios conservés.</li>
                <li><b>Conversions multi-résolutions :</b> Export en basse, moyenne ou haute définition avec suffixes explicites (<code>_low</code>, <code>_med</code>, <code>_high</code>).</li>
                <li><b>Traitement par lot :</b> Conversion en un clic de l'ensemble d'un répertoire avec suivi visuel de progression.</li>
                <li><b>Format optimisé :</b> Génération automatique de fichiers JPEG compressés de haute qualité.</li>
                <li><b>Interface multilingue :</b> Prise en charge intégrale du français et de l'anglais sans redémarrage.</li>
            </ul>
            """
        else:
            content = """
            <h2>About StampPhoto</h2>
            <div class="author">
                <b>Author:</b> Boris du Reau<br>
                <b>Version:</b> 1.0 (2026)<br>
                <b>Part of:</b> stampOffice Suite
            </div>

            <h3>Application Overview</h3>
            <p>
                <b>StampPhoto</b> is an image browser and batch processor tailored for collectors, 
                allowing fast inspection and automated resolution scaling of philatelic photographs.
            </p>

            <h3>Key Features</h3>
            <ul>
                <li><b>Centred Stamp Viewer:</b> Inspect photos one by one with sharp, aspect-ratio-safe rendering.</li>
                <li><b>Multi-Resolution Export:</b> Convert items into Low, Medium, or High definition with automatic naming suffixes (<code>_low</code>, <code>_med</code>, <code>_high</code>).</li>
                <li><b>Batch Conversion:</b> Process an entire folder at once with real-time progress feedback.</li>
                <li><b>Optimized Output:</b> Clean RGB conversion saved in standard JPEG format with customizable quality.</li>
                <li><b>Dynamic Localization:</b> Instant bilingual support (English / French) without restarting.</li>
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