"""
Application Help Dialog Module
------------------------------
Displays local HTML help documentation adapted to the active locale language.
"""

import gettext
from pathlib import Path
from PyQt6.QtCore import QUrl, QLocale
from PyQt6.QtWidgets import (
    QDialog, QTextBrowser,
    QFormLayout, QDialogButtonBox
)

from AppLanguage import get_language
gettext.find("HelpDlg")
translate = gettext.translation('HelpDlg', localedir='locale', languages=[get_language()], fallback=True)
translate.install()
_ = translate.gettext

class HelpDlg(QDialog):
    def __init__(self, parent=None):
        super(HelpDlg, self).__init__(parent)
        self.setWindowTitle(_("Application Help"))
        self.createDlg()

    def createDlg(self):
        output = QTextBrowser()

        # Check language code ('fr', 'en', etc.)
        lang = QLocale.system().name()[:2]
        help_path = Path(f"Help/stamp_album_help_{lang}.html")

        # Fallback to default if language file does not exist
        if not help_path.exists():
            help_path = Path("../Help/stamp_album_help.html")

        output.setSource(QUrl.fromLocalFile(str(help_path)))

        # OK button with localized text
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        ok_btn = bb.button(QDialogButtonBox.StandardButton.Ok)
        if ok_btn:
            ok_btn.setText(_("OK"))

        bb.accepted.connect(self.accept)

        flo = QFormLayout()
        flo.addRow(output)
        flo.addRow(bb)

        self.setLayout(flo)