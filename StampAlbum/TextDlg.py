"""
Text Dialog Module
------------------
Provides a dialog window for adding and updating standard text labels on
stamp album pages, including typography controls (bold, italic, strikeout,
underline, font size) and paragraph alignments (left, center, right).

Author: Boris du Reau
"""
import sys
from PyQt6.QtCore import Qt
from pathlib import Path
from PyQt6.QtWidgets import (
    QComboBox, QHBoxLayout, QDialog, QPushButton, QTextEdit,
    QFormLayout, QDialogButtonBox
)
from PyQt6.QtGui import QIcon, QTextBlockFormat, QTextCursor

import gettext
from AppLanguage import get_language
from SAAppPaths import get_images_dir

gettext.find("TextDlg")
translate = gettext.translation('TextDlg', localedir='locale', languages=[get_language()], fallback=True)
translate.install()
_ = translate.gettext


class TextDlg(QDialog):
    """Dialog window allowing the creation or editing of text labels."""
    def __init__(self, txtObj=None, parent=None):
        super(TextDlg, self).__init__(parent)

        self.base_dir = self._get_app_dir()
        self.images_dir = self._get_resource_dir("Images")

        icon_path = self.images_dir / "stamp_book.png"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))
        else:
            self.setWindowIcon(QIcon('stamp_book.png'))

        # Determine whether this is an edit operation or a new text insertion
        is_editing = txtObj is not None and txtObj.toPlainText().strip() != ""

        if is_editing:
            self.setWindowTitle(_("Update text"))
        else:
            self.setWindowTitle(_("Add new text"))

        self.createDlg(txtObj)

    def _get_app_dir(self) -> Path:
        """
                Determine the root application directory.

                - If running as an EXE: returns the directory containing the executable.
                - If running from Python (.py in a subfolder): traverses to parent directory
                  if 'Databases', 'Images', 'Photos' or 'docs' is present, else returns script directory.
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
        """Resolve a resource directory (Images, docs, etc.) from application base or relative directory."""
        res_dir = self.base_dir / folder_name
        if res_dir.exists():
            return res_dir
        return Path(__file__).resolve().parent / folder_name
    def _get_icon(self, icon_name: str) -> QIcon:
        """
                Dynamically load icon from the images directory resolved by SAAppPaths.
                Falls back to standard relative path if needed.
        """
        images_dir = get_images_dir()
        icon_path = images_dir / icon_name

        if icon_path.exists():
            return QIcon(str(icon_path))

        # Relative fallback path if needed
        return QIcon(f"../Images/{icon_name}")

    def createDlg(self, txtObj=None):
        """Construct dialog widgets, formatting toolbar, and layouts."""
        hLayout1 = QHBoxLayout()

        boldButton = QPushButton()
        boldButton.setFixedWidth(30)
        boldButton.setIcon(self._get_icon("bold.png"))

        italicButton = QPushButton()
        italicButton.setIcon(self._get_icon("italic.png"))
        italicButton.setFixedWidth(30)

        strikeButton = QPushButton()
        strikeButton.setIcon(self._get_icon("strike.png"))
        strikeButton.setFixedWidth(30)

        underlineButton = QPushButton()
        underlineButton.setIcon(self._get_icon("underline.png"))
        underlineButton.setFixedWidth(30)

        justifyLeftButton = QPushButton()
        justifyLeftButton.setIcon(self._get_icon("justify left.png"))
        justifyLeftButton.setFixedWidth(30)

        centerButton = QPushButton()
        centerButton.setIcon(self._get_icon("justify center.png"))
        centerButton.setFixedWidth(30)

        justifyRightButton = QPushButton()
        justifyRightButton.setIcon(self._get_icon("justify right.png"))
        justifyRightButton.setFixedWidth(30)

        hLayout1.addWidget(boldButton)
        hLayout1.addWidget(italicButton)
        hLayout1.addWidget(strikeButton)
        hLayout1.addWidget(underlineButton)
        hLayout1.addWidget(justifyLeftButton)
        hLayout1.addWidget(centerButton)
        hLayout1.addWidget(justifyRightButton)

        self.fontSize = QComboBox()

        for x in range(100):
            self.fontSize.addItem(str(x))

        self.fontSize.setMaximumWidth(50)

        hLayout1.addWidget(self.fontSize)

        boldButton.clicked.connect(self.boldPushed)
        italicButton.clicked.connect(self.italicPushed)
        strikeButton.clicked.connect(self.strikePushed)
        underlineButton.clicked.connect(self.underlinePushed)

        justifyLeftButton.clicked.connect(self.justifyLeftPushed)
        centerButton.clicked.connect(self.centerPushed)
        justifyRightButton.clicked.connect(self.justifyRightPushed)

        self.eTXT = QTextEdit()
        self.eTXT.setFixedHeight(80)

        myFont = self.eTXT.font()

        self.fontSize.setCurrentText(str(myFont.pointSize()))

        self.fontSize.currentTextChanged.connect(self.fontSizeClicked)

        if txtObj is None:
            self.eTXT.setPlainText("")
        else:
            self.eTXT.setPlainText(txtObj.toPlainText())
            self.eTXT.setFont(txtObj.font())
            print(txtObj.font().pointSize())
            self.fontSize.setCurrentText(str(txtObj.font().pointSize()))

            cursor = txtObj.textCursor()
            cursor.select(QTextCursor.SelectionType.Document)

            format = QTextBlockFormat()
            cursor.mergeBlockFormat(format)
            cursor.clearSelection()

            # unfortunately does not get the alignment...
            align = format.alignment()

            print(align)
            self.eTXT.selectAll()
            self.eTXT.setAlignment(align)

        flo = QFormLayout()
        flo.addRow(hLayout1)
        flo.addRow("", self.eTXT)

        self.setLayout(flo)

        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)

        # --- Button localization ---
        ok_button = bb.button(QDialogButtonBox.StandardButton.Ok)
        if ok_button:
            ok_button.setText(_("OK"))

        cancel_button = bb.button(QDialogButtonBox.StandardButton.Cancel)
        if cancel_button:
            cancel_button.setText(_("Cancel"))

        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        flo.addWidget(bb)
        self.eTXT.setFocus()

    def boldPushed(self):
        """Toggle bold font style for the text editor."""
        if self.eTXT.font().bold() == True:
            myFont = self.eTXT.font()
            myFont.setBold(False)
            self.eTXT.setFont(myFont)
        else:
            myFont = self.eTXT.font()
            myFont.setBold(True)
            self.eTXT.setFont(myFont)

    def underlinePushed(self):
        """Toggle underline font style for the text editor."""
        if self.eTXT.font().underline() == True:
            myFont = self.eTXT.font()
            myFont.setUnderline(False)
            self.eTXT.setFont(myFont)
        else:
            myFont = self.eTXT.font()
            myFont.setUnderline(True)
            self.eTXT.setFont(myFont)

    def italicPushed(self):
        """Toggle italic font style for the text editor."""
        if self.eTXT.font().italic():
            myFont = self.eTXT.font()
            myFont.setItalic(False)
            self.eTXT.setFont(myFont)
        else:
            myFont = self.eTXT.font()
            myFont.setItalic(True)
            self.eTXT.setFont(myFont)

    def strikePushed(self):
        """Toggle strikeout font style for the text editor."""
        if self.eTXT.font().strikeOut() == True:
            myFont = self.eTXT.font()
            myFont.setStrikeOut(False)
            self.eTXT.setFont(myFont)
        else:
            myFont = self.eTXT.font()
            myFont.setStrikeOut(True)
            self.eTXT.setFont(myFont)

    def fontSizeClicked(self):
        """Update editor font size to the selected dropdown value."""
        myFont = self.eTXT.font()
        myFont.setPointSize(int(self.fontSize.currentText()))
        self.eTXT.setFont(myFont)

    def justifyLeftPushed(self):
        """Set text alignment to left."""
        self.eTXT.setAlignment(Qt.AlignmentFlag.AlignLeft)

    def centerPushed(self):
        """Set text alignment to center."""
        self.eTXT.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def justifyRightPushed(self):
        """Set text alignment to right."""
        self.eTXT.setAlignment(Qt.AlignmentFlag.AlignRight)