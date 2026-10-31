"""
Main Window Module
------------------
Contains the main application window ('Window') maddRichText(anaging menus, toolbars,
tabbed page displays, actions, and file I/O operations (XML/gzip).

Author: Boris du Reau
"""
import sys
import re
from pathlib import Path
from PyQt6 import sip
from ResizablePixmapItem import ResizablePixmapItem
from PageBorder import PageBorder
from SAAboutDlg import AboutDlg
from PyQt6.QtCore import Qt
from PyQt6 import QtCore, QtGui
from PyQt6.QtWidgets import (
    QGridLayout, QMessageBox, QFileDialog, QComboBox,
    QLabel, QMainWindow, QMenu,
    QToolBar, QGraphicsTextItem, QPushButton,
    QStatusBar, QTabWidget, QWidget, QApplication
)
from PyQt6.QtGui import QBrush, QPainter, QPixmap, QFont, QTextCursor, QTextBlockFormat
from PyQt6.QtPrintSupport import QPrintPreviewDialog, QPrinter
from Stamp import Stamp
from CustomStampDlg import CustomStampDlg
from AlbumEasyImporter import AlbumEasyImporter
from XlsAlbumImporter import XlsAlbumImporter

from Page import Page
from ConfigDlg import ConfigDlg
from CatalogRichTextStampDlg import CatalogRichTextStampDlg

import xml.etree.ElementTree as ET

from PageDlg import PageDlg

from GraphicsView import GraphicsView
import os, gzip
from TextDlg import TextDlg

import gettext
from AppLanguage import get_language
from PyQt6.QtGui import QAction, QIcon, QKeySequence, QDesktopServices
from PyQt6.QtCore import QUrl

import platform
from datetime import datetime
from AlbumInfoDlg import AlbumInfoDlg

from RichTextStampDlg import RichTextStampDlg

# Set up gettext localization
gettext.find("MainWindow")
translate = gettext.translation('MainWindow', localedir='locale', languages=[get_language()], fallback=True)

translate.install()
_ = translate.gettext

FILE_FORMAT_VERSION = "1.0"


class Window(QMainWindow):
    """Main application window managing UI layout, actions, and user interactions."""

    def __init__(self, parent=None):
        """Initialize the main window and UI components."""
        super().__init__(parent)
        self.setWindowTitle("Stamp album")

        # Album metadata storage
        self.album_metadata = {
            "creation_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "author": "",
            "language": "fr",
            "os": f"{platform.system()} {platform.release()}",
            "page_count": 0,
            "stamp_count": 0
        }

        self.base_dir = self._get_app_dir()
        self.images_dir = self._get_resource_dir("Images")

        icon_path = self.images_dir / "stamp_book.png"
        if icon_path.exists():
            self.setWindowIcon(QtGui.QIcon(str(icon_path)))
        else:
            self.setWindowIcon(QtGui.QIcon('stamp_book.png'))

        # Set initial main window dimensions
        self.resize(900, 850)

        # Track page count and recent stamp dialog selections
        self.pageCount = 0
        self.lastStampObj = {}
        self.lastStampObj['country'] = None
        self.lastStampObj['type'] = None
        self.lastStampObj['nbr'] = None
        self.lastStampObj['year'] = None

        # Central tab widget containing album pages
        self.tabs = QTabWidget()
        palette = self.tabs.palette()
        palette.setColor(self.tabs.backgroundRole(), Qt.GlobalColor.lightGray)
        self.tabs.setPalette(palette)
        self.tabs.resize(300, 200)

        # Connect tab switching to update zoom display
        self.tabs.currentChanged.connect(self.onTabChanged)

        self.currentAlbumName = ""

        # Initialize UI elements and action bindings
        self._createActions()
        self._createMenuBar()
        self._createToolBars()
        self._connectActions()

        # Create an initial default page
        self.newPage(None, True)

        self.tabs.setMovable(True)
        # Connect tab moving signal to properly rename "Page 1, Page 2..."
        self.tabs.tabBar().tabMoved.connect(self.renameTabs)
        self.setCentralWidget(self.tabs)

    def is_modified(self) -> bool:
        """
        Check if the currently active album has unsaved changes.
        Iterates over all tab scenes and checks if any QUndoStack is dirty.
        """
        for i in range(self.tabs.count()):
            widget = self.tabs.widget(i)
            if hasattr(widget, 'view') and widget.view and widget.view.scene():
                scene = widget.view.scene()
                if hasattr(scene, 'undoStack') and not scene.undoStack.isClean():
                    return True
        return False

    def update_window_title(self):
        """
        Update the main window title using the Qt standard [*] placeholder
        to display the modified state indicator.
        """
        album_name = Path(self.currentAlbumName).name if self.currentAlbumName else _("Untitled Album")
        # The [*] marker is required by Qt to display the modification indicator
        self.setWindowTitle(f"Stamp Album - {album_name}[*]")
        self.setWindowModified(self.is_modified())

    def on_modification_changed(self, clean: bool = False):
        """Slot invoked whenever any page's undo stack cleanliness changes."""
        self.renameTabs()
        self.update_window_title()

    def maybe_save(self) -> bool:
        """
        Prompt the user to save unsaved modifications before proceeding.
        Returns:
            bool: True if it is safe to proceed (saved or discarded),
                  False if the user cancelled the action.
        """
        if not self.is_modified():
            return True

        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle(_("Unsaved Changes"))
        album_label = Path(self.currentAlbumName).name if self.currentAlbumName else _("this album")

        box.setText(
            _("The album '{album}' has been modified.\nDo you want to save your changes before proceeding?").format(
                album=album_label
            )
        )
        box.setStandardButtons(
            QMessageBox.StandardButton.Save |
            QMessageBox.StandardButton.Discard |
            QMessageBox.StandardButton.Cancel
        )
        box.setDefaultButton(QMessageBox.StandardButton.Save)

        # Set localized button labels
        save_btn = box.button(QMessageBox.StandardButton.Save)
        if save_btn:
            save_btn.setText(_("&Save"))
        discard_btn = box.button(QMessageBox.StandardButton.Discard)
        if discard_btn:
            discard_btn.setText(_("&Don't Save"))
        cancel_btn = box.button(QMessageBox.StandardButton.Cancel)
        if cancel_btn:
            cancel_btn.setText(_("&Cancel"))

        choice = box.exec()

        if choice == QMessageBox.StandardButton.Save:
            # Perform save operation and check if the user completed it
            saved = self.saveAlbumToFile()
            # If the user clicks 'Cancel' in the file save dialog
            return saved is not False and not self.is_modified()

        elif choice == QMessageBox.StandardButton.Discard:
            return True

        # User clicked Cancel or closed the message box
        return False

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

    def _get_icon(self, icon_filename: str) -> QIcon:
        """Utility to load an icon robustly from the 'Images' directory."""
        path = self.images_dir / icon_filename
        if path.exists():
            return QIcon(str(path))
        return QIcon(f"../Images/{icon_filename}")

    def _createMenuBar(self):
        """Construct the main menu bar."""
        menuBar = self.menuBar()

        # File Menu
        fileMenu = QMenu(_("&File"), self)
        menuBar.addMenu(fileMenu)
        fileMenu.addAction(self.newAction)
        fileMenu.addAction(self.openAction)
        fileMenu.addAction(self.importAlbumEasyAction)
        fileMenu.addAction(self.importExcelAlbumAction)
        fileMenu.addAction(self.saveAction)
        fileMenu.addAction(self.printAction)
        fileMenu.addAction(self.printPreviewCurrentPageAction)
        fileMenu.addAction(self.printPreviewAllPagesAction)
        fileMenu.addAction(self.printPDFAction)
        fileMenu.addAction(self.exitAction)

        # Edit Menu
        editMenu = menuBar.addMenu(_("&Edit"))
        editMenu.addAction(self.undoAction)
        editMenu.addAction(self.redoAction)
        editMenu.addSeparator()
        editMenu.addAction(self.selectAllAction)
        editMenu.addAction(self.copyAction)
        editMenu.addAction(self.pasteAction)
        editMenu.addAction(self.cutAction)

        # Stamp Menu
        stampMenu = menuBar.addMenu(_("&Stamp"))
        stampMenu.addAction(self.newStampAction)
        stampMenu.addAction(self.newCatalogRichTextStampAction)
        stampMenu.addAction(self.newRichTextStampAction)
        stampMenu.addAction(self.newCustomStampAction)
        stampMenu.addAction(self.editStampAction)

        # Alignment Menu
        alignMenu = menuBar.addMenu(_("Align"))
        alignMenu.addAction(self.alignLeftAction)
        alignMenu.addAction(self.alignRightAction)
        alignMenu.addAction(self.alignTopAction)
        alignMenu.addAction(self.alignBottomAction)
        alignMenu.addAction(self.centerHorizontallyAction)
        alignMenu.addAction(self.centerVerticallyAction)
        alignMenu.addAction(self.distributeVerticallyAction)
        alignMenu.addAction(self.distributeHorizontallyAction)
        alignMenu.addSeparator()
        alignMenu.addAction(self.autoArrangeAction)

        # Page Menu
        pageMenu = menuBar.addMenu(_("Pages"))
        pageMenu.addAction(self.newPageAction)
        pageMenu.addAction(self.changePageSetupAction)
        pageMenu.addAction(self.albumInfoAction)
        pageMenu.addAction(self.deletePageAction)
        pageMenu.addAction(self.deletePageObjectsAction)
        pageMenu.addAction(self.drawGridAction)
        pageMenu.addAction(self.deleteAlbumAction)
        pageMenu.addAction(self.changeBorderCurrentAction)
        pageMenu.addAction(self.changeBorderAllAction)
        pageMenu.addSeparator()
        pageMenu.addAction(self.reorderPagesAction)

        # Objects Menu
        objectMenu = menuBar.addMenu(_("Objects"))
        objectMenu.addAction(self.newTextAction)
        objectMenu.addAction(self.newRichTextAction)
        objectMenu.addAction(self.newImageAction)
        #objectMenu.addAction(self.newBorderAction)
        objectMenu.addAction(self.newCopyRightAction)
        objectMenu.addAction(self.newCopyRightAllPagesAction)
        objectMenu.addAction(self.newPageNbrAction)
        objectMenu.addAction(self.newPageNbrAllPagesAction)
        objectMenu.addAction(self.newYearToPageAction)
        objectMenu.addAction(self.newYearToAllPagesAction)

        # Config Menu
        configMenu = menuBar.addMenu(_("&Config"))
        configMenu.addAction(self.setupAppAction)

        # Help Menu
        helpMenu = menuBar.addMenu(_("&Help"))
        helpMenu.addAction(self.helpContentAction)
        helpMenu.addAction(self.aboutAction)

        # Zoom selector combo box in menu bar
        self.zoomCombo = QComboBox(self)
        self.zoomCombo.addItems(["25%", "50%", "75%", "100%", "125%", "150%", "200%"])
        self.zoomCombo.setCurrentText("100%")
        self.zoomCombo.currentTextChanged.connect(self.onZoomComboChanged)

        # Status bar zoom display widget
        self.statusFileLabel = QLabel(_("No album loaded"), self)
        self.statusPageFormatLabel = QLabel("", self)
        self.statusZoomLabel = QLabel("Zoom: 100%", self)

        # Bottom Left: addWidget() places items on the left side
        self.statusBar().addWidget(self.statusFileLabel, 1)

        # Bottom Right: addPermanentWidget() places items on the far right
        self.statusBar().addPermanentWidget(self.statusPageFormatLabel)
        self.statusBar().addPermanentWidget(self.statusZoomLabel)

    def updatePageFormatStatus(self):
        """Update the status bar label displaying the current page format and orientation."""
        scene = self.getCurrentPageScene()
        if hasattr(self, 'statusPageFormatLabel') and self.statusPageFormatLabel and not sip.isdeleted(
                self.statusPageFormatLabel):
            if scene:
                fmt = getattr(scene, 'paper_format', 'A4')
                orient = _("Portrait") if scene.pageType == "portrait" else _("Landscape")
                self.statusPageFormatLabel.setText(f"{fmt} - {orient}")
            else:
                self.statusPageFormatLabel.setText("")

    def changeCurrentPageSetup(self):
        """Open the setup dialog to modify orientation, paper size, and border of the active page."""
        scene = self.getCurrentPageScene()
        if not scene:
            return

        current_border_style = None
        for it in scene.items():
            if it.data(0) == "borderGroup":
                current_border_style = it.data(4)
                break

        dlg = PageDlg(
            pageType=scene.pageType,
            paperFormat=getattr(scene, 'paper_format', 'A4'),
            borderStyle=current_border_style,
            marginSize=getattr(scene, 'margin_size_mm', 19.0),
            marginPosition=getattr(scene, 'margin_position', 'left'),
            is_edit=True,
            parent=self
        )

        if dlg.exec() == 1:
            scene.changePageSetup(
                dlg.pageType, dlg.paperFormat, dlg.borderStyle,
                margin_size_mm=dlg.marginSize, margin_position=dlg.marginPosition
            )
            self.updatePageFormatStatus()

            # Refresh view rulers and viewport
            view = self.getCurrentPage()
            if view:
                view.viewport().update()

    def selectAll(self):
        """Select all movable elements on the active page."""
        scene = self.getCurrentPageScene()
        if scene:
            for item in scene.items():
                if item.parentItem() is None and str(item.data(0)) != "borderGroup":
                    item.setSelected(True)

    def onZoomComboChanged(self, text: str):
        """Handle zoom dropdown selection change and apply to active viewport."""
        if not text:
            return
        view = self.getCurrentPage()
        if view and not sip.isdeleted(view):
            val = int(text.replace("%", ""))
            factor = val / 100.0
            if abs(view.getZoomFactor() - factor) > 0.001:
                if hasattr(self, 'zoomCombo') and not sip.isdeleted(self.zoomCombo):
                    self.zoomCombo.blockSignals(True)
                view.setZoomFactor(factor)
                if hasattr(self, 'zoomCombo') and not sip.isdeleted(self.zoomCombo):
                    self.zoomCombo.blockSignals(False)

    def updateZoomStatus(self, percent_val: int):
        """Update status bar label and align zoom combo box text safely."""
        # Check if the C++ QLabel is still alive
        if hasattr(self, 'statusZoomLabel') and self.statusZoomLabel is not None:
            if not sip.isdeleted(self.statusZoomLabel):
                self.statusZoomLabel.setText(f"Zoom: {percent_val}%")

        # Check if the C++ QComboBox is still alive
        if hasattr(self, 'zoomCombo') and self.zoomCombo is not None:
            if not sip.isdeleted(self.zoomCombo):
                self.zoomCombo.blockSignals(True)
                self.zoomCombo.setCurrentText(f"{percent_val}%")
                self.zoomCombo.blockSignals(False)

    def onTabChanged(self, index: int):
        """Synchronize status bar and combo box display when switching tabs."""
        # QTimer.singleShot defers update to allow Qt to stabilize the UI
        QtCore.QTimer.singleShot(10, self._syncZoomUI)
        self.updatePageFormatStatus()

    def _syncZoomUI(self):
        """Helper to synchronize zoom UI after layout is stabilized."""
        view = self.getCurrentPage()
        if view:
            current_pct = int(view.getZoomFactor() * 100)
            self.updateZoomStatus(current_pct)

    def _createActions(self):
        """Define QAction instances for menus and toolbars."""
        self.newAction = QAction(self)
        self.newAction.setText(_("&New"))
        self.newAction.setIcon(self._get_icon("new.png"))

        self.openAction = QAction(_("&Open..."), self)
        self.openAction.setIcon(self._get_icon("open.png"))
        self.openAction.setObjectName("actionOpen")

        self.saveAction = QAction(_("&Save"), self)
        self.saveAction.setIcon(self._get_icon("save.png"))
        self.saveAction.setObjectName("actionSave")

        self.printAction = QAction(_("&Print all pages..."), self)
        self.printAction.setIcon(self._get_icon("print.png"))
        self.printAction.setObjectName("printAction")

        self.printPreviewAllPagesAction = QAction(_("&Print preview all pages..."), self)
        self.printPreviewAllPagesAction.setIcon(self._get_icon("printprev.png"))
        self.printPreviewAllPagesAction.setObjectName("printPreviewAllPagesAction")

        self.printPreviewCurrentPageAction = QAction(_("&Print preview current page..."), self)
        self.printPreviewCurrentPageAction.setIcon(self._get_icon("printprev.png"))
        self.printPreviewCurrentPageAction.setObjectName("printPreviewCurrentPageAction")

        self.printPDFAction = QAction(_("&Print current to PDF..."), self)
        self.printPDFAction.setIcon(self._get_icon("pdf.png"))
        self.printPDFAction.setObjectName("printPDFAction")

        self.exitAction = QAction(_("&Exit"), self)
        self.exitAction.setIcon(self._get_icon("exit.png"))
        self.exitAction.setObjectName("exitAction")

        self.copyAction = QAction(_("&Copy"), self)
        self.copyAction.setIcon(self._get_icon("copy.png"))

        self.pasteAction = QAction(_("&Paste"), self)
        self.pasteAction.setIcon(self._get_icon("paste.png"))

        self.cutAction = QAction(_("C&ut"), self)
        self.cutAction.setIcon(self._get_icon("cut.png"))

        self.newStampAction = QAction(_("New Stamp ..."), self)
        self.newCustomStampAction = QAction(_("New Custom Stamp ..."), self)
        self.newCustomStampAction.setIcon(self._get_icon("stamp_custom.png"))
        self.editStampAction = QAction(_("Edit Current Stamp ..."), self)
        self.newStampAction.setIcon(self._get_icon("stamp.png"))

        self.newRichTextStampAction = QAction(_("New Rich Text Stamp ..."), self)
        self.newRichTextStampAction.setIcon(self._get_icon("stamp_custom.png"))
        self.newRichTextStampAction.triggered.connect(self.createNewRichTextStamp)

        self.newCatalogRichTextStampAction = QAction(_("New Catalog Rich Text Stamp..."), self)
        self.newCatalogRichTextStampAction.setIcon(self._get_icon("stamp.png"))
        self.newCatalogRichTextStampAction.triggered.connect(self.createNewCatalogRichTextStamp)

        self.newPageAction = QAction(_("New Page ..."), self)
        self.newPageAction.setIcon(self._get_icon("page.png"))

        self.deletePageAction = QAction(_("Delete Page ..."), self)
        self.deletePageAction.setIcon(self._get_icon("delete_page.png"))

        self.deletePageObjectsAction = QAction(_("Delete Page Objects..."), self)
        self.deletePageObjectsAction.setIcon(self._get_icon("clear_page.png"))

        self.drawGridAction = QAction(_("Grid on/off"), self)
        self.drawGridAction.setIcon(self._get_icon("grid.png"))

        self.deleteAlbumAction = QAction(_("Delete Album ..."), self)
        self.deleteAlbumAction.setIcon(self._get_icon("trash.png"))

        self.newTextAction = QAction(_("New text ..."), self)
        self.newTextAction.setIcon(self._get_icon("text.png"))

        self.newRichTextAction = QAction(_("New Rich Text ..."), self)
        self.newRichTextAction.setIcon(self._get_icon("rich_text.png"))

        self.newImageAction = QAction(_("New Image ..."), self)
        self.newImageAction.setIcon(self._get_icon("image.png"))

        self.newCopyRightAction = QAction(_("New copyright"), self)
        self.newCopyRightAction.setIcon(self._get_icon("copyright.png"))

        self.newCopyRightAllPagesAction = QAction(_("New copyright all pages"), self)
        self.newCopyRightAllPagesAction.setIcon(self._get_icon("page_copyright.png"))

        self.albumInfoAction = QAction(_("Current album info..."), self)
        self.albumInfoAction.setIcon(self._get_icon("about.png"))
        self.albumInfoAction.triggered.connect(self.showAlbumInfo)

        self.newPageNbrAction = QAction(_("New page nbr"), self)
        self.newPageNbrAction.setIcon(self._get_icon("number.png"))

        self.newPageNbrAllPagesAction = QAction(_("New page nbr all pages"), self)
        self.newPageNbrAllPagesAction.setIcon(self._get_icon("number.png"))

        self.newYearToPageAction = QAction(_("Add year to page"), self)
        self.newYearToPageAction.setIcon(self._get_icon("add_year.png"))

        self.newYearToAllPagesAction = QAction(_("Add year to all pages"), self)

        self.alignLeftAction = QAction(_("Align Left"), self)
        self.alignLeftAction.setIcon(self._get_icon("align_left.png"))

        self.alignRightAction = QAction(_("Align Right"), self)
        self.alignRightAction.setIcon(self._get_icon("align_right.png"))

        self.alignTopAction = QAction(_("Align Top"), self)
        self.alignTopAction.setIcon(self._get_icon("align_top.png"))

        self.alignBottomAction = QAction(_("Align Bottom"), self)
        self.alignBottomAction.setIcon(self._get_icon("align_bottom.png"))

        self.distributeVerticallyAction = QAction(_("Distribute Vertically"), self)
        self.distributeVerticallyAction.setIcon(self._get_icon("distribute_vertical.png"))

        self.distributeHorizontallyAction = QAction(_("Distribute Horizontally"), self)
        self.distributeHorizontallyAction.setIcon(self._get_icon("distribute_horiz.png"))

        self.centerHorizontallyAction = QAction(_("Center Horizontally"), self)
        self.centerHorizontallyAction.setIcon(self._get_icon("center_horizontal.png"))

        self.centerVerticallyAction = QAction(_("Center Vertically"), self)
        self.centerVerticallyAction.setIcon(self._get_icon("center_vertical.png"))

        self.setupAppAction = QAction(_("Setup application"), self)
        self.setupAppAction.setIcon(self._get_icon("config.png"))

        self.helpContentAction = QAction(_("&Help Content"), self)
        self.helpContentAction.setIcon(self._get_icon("help.png"))

        self.aboutAction = QAction(_("&About"), self)
        self.aboutAction.setIcon(self._get_icon("about.png"))

        self.undoAction = QAction(_("&Undo"), self)
        self.undoAction.setShortcut(QKeySequence.StandardKey.Undo)
        self.undoAction.setIcon(self._get_icon("undo.png"))
        self.undoAction.triggered.connect(self.undo)

        self.redoAction = QAction(_("&Redo"), self)
        self.redoAction.setShortcut(QKeySequence.StandardKey.Redo)
        self.redoAction.setIcon(self._get_icon("redo.png"))
        self.redoAction.triggered.connect(self.redo)

        self.autoArrangeAction = QAction(_("Auto-arrange Stamps"), self)
        self.autoArrangeAction.setIcon(self._get_icon("auto_arrange.png"))

        self.selectAllAction = QAction(_("Select &All"), self)
        self.selectAllAction.setShortcut(QKeySequence.StandardKey.SelectAll)
        self.selectAllAction.triggered.connect(self.selectAll)

        self.reorderPagesAction = QAction(_("Thundnails..."), self)
        self.reorderPagesAction.setIcon(self._get_icon("thumbnails.png"))
        self.reorderPagesAction.triggered.connect(self.openThumbnails)

        self.changeBorderCurrentAction = QAction(_("Change current page border"), self)
        self.changeBorderCurrentAction.setIcon(self._get_icon("border.png"))

        self.changeBorderAllAction = QAction(_("Change page bordure (all pages)"), self)
        self.changeBorderAllAction.setIcon(self._get_icon("border_all.png"))

        self.importAlbumEasyAction = QAction(_("Import AlbumEasy..."), self)
        self.importAlbumEasyAction.setIcon(self._get_icon("open.png"))

        self.importExcelAlbumAction = QAction(_("Import Excel album (.xls)..."), self)
        self.importExcelAlbumAction.setIcon(self._get_icon("open.png"))

        self.changePageSetupAction = QAction(_("Current page setup..."), self)
        self.changePageSetupAction.setIcon(self._get_icon("page.png"))
        self.changePageSetupAction.triggered.connect(self.changeCurrentPageSetup)



    def _createToolBars(self):
        """Construct application toolbars."""
        fileToolBar = self.addToolBar("File")
        fileToolBar.addAction(self.newAction)
        fileToolBar.addAction(self.openAction)
        fileToolBar.addAction(self.saveAction)
        fileToolBar.addAction(self.printPDFAction)
        fileToolBar.addAction(self.printPreviewAllPagesAction)
        fileToolBar.addAction(self.printPreviewCurrentPageAction)
        fileToolBar.addAction(self.exitAction)

        editToolBar = QToolBar("Edit", self)
        editToolBar.addAction(self.copyAction)
        editToolBar.addAction(self.pasteAction)
        editToolBar.addAction(self.cutAction)
        self.addToolBar(editToolBar)

        pageToolBar = QToolBar("Page", self)
        pageToolBar.addAction(self.newPageAction)
        pageToolBar.addAction(self.deletePageAction)
        pageToolBar.addAction(self.deletePageObjectsAction)
        pageToolBar.addAction(self.drawGridAction)
        pageToolBar.addAction(self.deleteAlbumAction)
        # Inside _createToolBars (under pageToolBar) :
        pageToolBar.addAction(self.reorderPagesAction)
        pageToolBar.addAction(self.changeBorderCurrentAction)
        pageToolBar.addAction(self.changeBorderAllAction)
        self.addToolBar(pageToolBar)

        alignToolBar = QToolBar("Align", self)
        alignToolBar.addAction(self.alignLeftAction)
        alignToolBar.addAction(self.alignRightAction)
        alignToolBar.addAction(self.alignTopAction)
        alignToolBar.addAction(self.alignBottomAction)
        alignToolBar.addAction(self.distributeVerticallyAction)
        alignToolBar.addAction(self.distributeHorizontallyAction)
        alignToolBar.addAction(self.centerHorizontallyAction)
        alignToolBar.addAction(self.centerVerticallyAction)
        alignToolBar.addAction(self.autoArrangeAction)
        self.addToolBar(alignToolBar)
        self.addToolBarBreak()

        stampToolBar = QToolBar("Stamp", self)
        stampToolBar.addAction(self.newStampAction)
        stampToolBar.addAction(self.newCatalogRichTextStampAction)
        stampToolBar.addAction(self.newCustomStampAction)
        stampToolBar.addAction(self.newRichTextStampAction)
        self.addToolBar(stampToolBar)

        objectToolBar = QToolBar("Objects", self)
        objectToolBar.addAction(self.newTextAction)
        objectToolBar.addAction(self.newRichTextAction)
        self.addToolBar(objectToolBar)

        helpToolBar = QToolBar("Help", self)
        helpToolBar.addAction(self.helpContentAction)
        helpToolBar.addAction(self.aboutAction)
        helpToolBar.addAction(self.setupAppAction)
        self.addToolBar(helpToolBar)

        zoomToolBar = QToolBar("Zoom", self)
        zoomToolBar.addWidget(self.zoomCombo)
        self.addToolBar(zoomToolBar)

    def _connectActions(self):
        """Connect UI actions to their respective handler functions."""
        self.newAction.triggered.connect(self.newFile)
        self.openAction.triggered.connect(self.openAlbumFile)
        self.saveAction.triggered.connect(self.saveAlbumToFile)
        self.printAction.triggered.connect(self.printAllPagesPDF)
        self.printPDFAction.triggered.connect(self.printPagePDF)
        self.printPreviewAllPagesAction.triggered.connect(self.printPreviewAllPages)
        self.printPreviewCurrentPageAction.triggered.connect(self.printPreviewCurrentPage)
        self.exitAction.triggered.connect(self.exitApp)

        self.copyAction.triggered.connect(self.copy)
        self.cutAction.triggered.connect(self.cut)
        self.pasteAction.triggered.connect(self.paste)

        self.alignBottomAction.triggered.connect(self.alignBottom)
        self.alignTopAction.triggered.connect(self.alignTop)
        self.alignLeftAction.triggered.connect(self.alignLeft)
        self.alignRightAction.triggered.connect(self.alignRight)
        self.distributeHorizontallyAction.triggered.connect(self.distributeHorizontally)
        self.distributeVerticallyAction.triggered.connect(self.distributeVertically)
        self.centerVerticallyAction.triggered.connect(self.centerVertically)
        self.centerHorizontallyAction.triggered.connect(self.centerHorizontally)

        self.setupAppAction.triggered.connect(self.configApp)

        self.newStampAction.triggered.connect(self.createNewStamp)
        self.newCustomStampAction.triggered.connect(self.createNewCustomStamp)
        self.editStampAction.triggered.connect(self.editStamp)

        self.newPageAction.triggered.connect(self.newPage)
        self.deletePageAction.triggered.connect(self.deleteCurrentPage)
        self.deletePageObjectsAction.triggered.connect(self.clearPageObjects)
        self.drawGridAction.triggered.connect(self.gridOnOff)
        self.deleteAlbumAction.triggered.connect(self.deleteAlbum)

        self.newTextAction.triggered.connect(self.createText)
        self.newRichTextAction.triggered.connect(self.createRichText)
        self.newCopyRightAction.triggered.connect(self.newCopyRight)
        self.newCopyRightAllPagesAction.triggered.connect(self.newCopyRightAllPages)
        self.newImageAction.triggered.connect(self.newImage)
        #self.newBorderAction.triggered.connect(self.newBorder)
        self.newPageNbrAction.triggered.connect(self.newPageNbr)
        self.newPageNbrAllPagesAction.triggered.connect(self.newPageNbrAllPages)
        self.newYearToPageAction.triggered.connect(self.addYearToPage)
        self.newYearToAllPagesAction.triggered.connect(self.addYearToAllPages)

        self.aboutAction.triggered.connect(self.about)
        self.helpContentAction.triggered.connect(self.help)
        self.autoArrangeAction.triggered.connect(self.autoArrangeStamps)

        self.changeBorderCurrentAction.triggered.connect(self.changeBorderCurrentPage)
        self.changeBorderAllAction.triggered.connect(self.changeBorderAllPages)
        self.importAlbumEasyAction.triggered.connect(self.importAlbumEasy)
        self.importExcelAlbumAction.triggered.connect(self.importExcelAlbum)


    def closeEvent(self, event: QtGui.QCloseEvent):
        """
        Intercept application close events.
        If dirty: prompt the user to Save, Discard, or Cancel.
        If clean: close immediately without prompting.
        """
        if self.maybe_save():
            event.accept()
        else:
            event.ignore()

    def updateStatusFile(self, file_path: str = ""):
        """Update the bottom-left status bar label with the active album file name."""
        if hasattr(self, 'statusFileLabel') and self.statusFileLabel and not sip.isdeleted(self.statusFileLabel):
            if file_path:
                display_name = Path(file_path).name
                self.statusFileLabel.setText(f"{_('Album:')} {display_name}")
                self.statusFileLabel.setToolTip(str(file_path))
            else:
                self.statusFileLabel.setText(_("No album loaded"))
                self.statusFileLabel.setToolTip("")

    def countTotalStamps(self) -> int:
        """Count the total number of stamps across all album pages."""
        total = 0
        for x in range(self.tabs.count()):
            widget = self.tabs.widget(x)
            if hasattr(widget, 'view') and widget.view and widget.view.scene():
                scene = widget.view.scene()
                for item in scene.items():
                    if item.parentItem() is None and item.data(0) == "stampGroup":
                        total += 1
        return total

    def showAlbumInfo(self):
        """Open the Album Info dialog to display and edit metadata."""
        self.album_metadata["page_count"] = self.tabs.count()
        self.album_metadata["stamp_count"] = self.countTotalStamps()
        self.album_metadata["os"] = f"{platform.system()} {platform.release()}"

        dlg = AlbumInfoDlg(self.album_metadata, self)
        if dlg.exec() == 1:
            self.album_metadata = dlg.get_metadata()
            new_lang = self.album_metadata.get("language", "fr")

            # Répercuter la langue sur toutes les scènes de l'album
            for i in range(self.tabs.count()):
                widget = self.tabs.widget(i)
                if hasattr(widget, 'view') and widget.view and widget.view.scene():
                    widget.view.scene().album_language = new_lang

    def undo(self):
        """Undo the last action on the active page."""
        scene = self.getCurrentPageScene()
        if scene and hasattr(scene, "undoStack"):
            scene.undoStack.undo()

    def redo(self):
        """Redo the last undone action on the active page."""
        scene = self.getCurrentPageScene()
        if scene and hasattr(scene, "undoStack"):
            scene.undoStack.redo()

    def exitApp(self):
        """Close the main window."""
        self.close()

    def newPage(self, _pageType=None, border=None, paper_format=None, margin_size=None, margin_position=None):
        """Create and append a new album page tab."""
        border_style = None

        if _pageType is not None and (_pageType == 'portrait' or _pageType == 'landscape'):
            self.pageType = _pageType
        else:
            self.pageType = "portrait"
            pDlg = PageDlg(parent=self)
            res = pDlg.exec()
            if res == 1:
                if pDlg.pageType == "portrait":
                    self.pageType = "portrait"
                    border = True
                else:
                    self.pageType = "landscape"
                    border = True
                border_style = pDlg.borderStyle
                paper_format = pDlg.paperFormat
                margin_size = pDlg.marginSize
                margin_position = pDlg.marginPosition
            else:
                return None

        # Safe instantiation with fallback default values
        page = Page(
            self.pageType,
            border=border,
            paper_format=paper_format,
            border_style=border_style,
            margin_size_mm=margin_size,
            margin_position=margin_position
        )
        page.album_language = self.album_metadata.get("language", "fr")

        # Track modifications whenever any command is pushed, undone, or redone
        page.undoStack.cleanChanged.connect(self.on_modification_changed)

        view = GraphicsView(page)
        view.scrollContentsBy(0, 0)
        view.zoomChanged.connect(self.updateZoomStatus)

        tab1 = QWidget()
        tab1.view = view

        layout = QGridLayout(tab1)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        from GraphicsView import RulerWidget
        h_ruler = RulerWidget(view, Qt.Orientation.Horizontal)
        v_ruler = RulerWidget(view, Qt.Orientation.Vertical)

        view.zoomChanged.connect(lambda x: h_ruler.update())
        view.zoomChanged.connect(lambda x: v_ruler.update())

        btn_clear = QPushButton("×")
        btn_clear.setFixedSize(20, 20)
        btn_clear.setToolTip(_("Clear guides"))
        btn_clear.setStyleSheet("border: 1px solid #ccc; background: #e0e0e0; font-weight: bold; color: #555;")
        btn_clear.clicked.connect(page.clearGuides)

        layout.addWidget(btn_clear, 0, 0)
        layout.addWidget(h_ruler, 0, 1)
        layout.addWidget(v_ruler, 1, 0)
        layout.addWidget(view, 1, 1)

        tab1.setLayout(layout)
        palette = tab1.palette()
        palette.setColor(tab1.backgroundRole(), Qt.GlobalColor.lightGray)
        tab1.setPalette(palette)

        self.pageCount = self.pageCount + 1

        self.tabs.blockSignals(True)
        tab_title = f"Page {self.tabs.count() + 1}"
        currentPage = self.tabs.addTab(tab1, tab_title)
        self.tabs.setCurrentIndex(currentPage)
        self.tabs.blockSignals(False)

        self.zoomCombo.blockSignals(True)
        view.setZoomFactor(1.0)
        self.zoomCombo.setCurrentText("100%")
        self.zoomCombo.blockSignals(False)

        # Refresh the window title and dirty indicator for the new layout
        self.update_window_title()
        return page

    def clearPageObjects(self):
        """Clear all graphic items on the current active page."""
        qm = QMessageBox(self)
        qm.setIcon(QMessageBox.Icon.Question)
        qm.setWindowTitle(_('Delete all objects'))
        qm.setText(_("Are you sure you want clear the current page?"))
        qm.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)

        # Translate buttons
        yes_btn = qm.button(QMessageBox.StandardButton.Yes)
        if yes_btn:
            yes_btn.setText(_("&Yes"))

        no_btn = qm.button(QMessageBox.StandardButton.No)
        if no_btn:
            no_btn.setText(_("&No"))

        ret = qm.exec()

        if ret == QMessageBox.StandardButton.Yes:
            scene = self.getCurrentPageScene()
            if scene:
                scene.clearPage()

    def deleteCurrentPage(self):
        """Remove the active page tab from the album."""
        qm = QMessageBox(self)
        qm.setIcon(QMessageBox.Icon.Question)
        qm.setWindowTitle(_('Delete current page'))
        qm.setText(_("Are you sure you want to delete the current page?"))
        qm.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)

        # Translate buttons
        yes_btn = qm.button(QMessageBox.StandardButton.Yes)
        if yes_btn:
            yes_btn.setText(_("&Yes"))

        no_btn = qm.button(QMessageBox.StandardButton.No)
        if no_btn:
            no_btn.setText(_("&No"))

        ret = qm.exec()

        if ret == QMessageBox.StandardButton.No:
            return
        if self.tabs.count().real > 0:
            self.tabs.removeTab(self.tabs.currentIndex())

            for x in range(0, self.tabs.count().real):
                self.tabs.setCurrentIndex(x)
                self.tabs.setTabText(self.tabs.currentIndex(), "Page " + str(x + 1))

    def deleteAllPages(self):
        """Remove all pages from the tab widget."""
        for x in range(self.tabs.count()):
            self.tabs.removeTab(self.tabs.currentIndex())
        self.pageCount = 0
        self.currentAlbumName = ""
        self.updateStatusFile("")

    def deleteAlbum(self):
        """Delete the entire album and reset state."""
        qm = QMessageBox(self)
        qm.setIcon(QMessageBox.Icon.Question)
        qm.setWindowTitle(_('Delete album'))
        qm.setText(_("Are you sure you want to delete the entire album?"))
        qm.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)

        # Translate buttons
        yes_btn = qm.button(QMessageBox.StandardButton.Yes)
        if yes_btn:
            yes_btn.setText(_("&Yes"))

        no_btn = qm.button(QMessageBox.StandardButton.No)
        if no_btn:
            no_btn.setText(_("&No"))


    def newFile(self):
        """Clear existing pages and start a fresh album file after confirming unsaved changes."""
        # Ensure unsaved modifications are resolved first
        if not self.maybe_save():
            return

        self.deleteAllPages()
        self.newPage(None, True)
        self.currentAlbumName = ""
        self.updateStatusFile("")
        self.setWindowModified(False)
        self.update_window_title()

    def createRichText(self):
        """Create a new rich text block on the current active page."""
        scene = self.getCurrentPageScene()
        if scene and hasattr(scene, "addRichText"):
            scene.addRichText()

    def createNewRichTextStamp(self):
        """Open the Rich Text Stamp dialog to insert a custom-styled stamp item."""
        scene = self.getCurrentPageScene()
        if scene:
            dlg = RichTextStampDlg(scene=scene, parent=self)
            dlg.exec()

    def createNewCatalogRichTextStamp(self):
        """Open catalog rich text stamp dialog to create formatted stamps from database."""
        scene = self.getCurrentPageScene()
        if scene:
            dlg = CatalogRichTextStampDlg(self.lastStampObj, scene, self)
            if dlg.exec() == 1:
                # Update lastStampObj for convenience on next insertion
                if dlg.yearsList.currentItem():
                    self.lastStampObj['year'] = dlg.yearsList.currentItem().text()
                self.lastStampObj['type'] = dlg.stampTypeCombo.currentText()
                self.lastStampObj['country'] = dlg.currentCountry
                self.lastStampObj['nbr'] = dlg.currentStampNbr

    def newPageNbr(self):
        """Add a page number to the current page."""
        scene = self.getCurrentPageScene()
        if scene:
            scene.newPageNbr()

    def newPageNbrAllPages(self):
        """Prompt user and apply page numbers across all album pages."""
        textLabel = QGraphicsTextItem("")
        textLabelFont = textLabel.font()
        textLabelFont.setPointSize(8)
        textLabel.setFont(textLabelFont)

        dlg = TextDlg(textLabel)
        res = dlg.exec()
        if res == 1:
            text = dlg.eTXT.toPlainText()
            font = dlg.eTXT.font()
            align = dlg.eTXT.alignment()

            for x in range(0, self.tabs.count().real):
                self.tabs.setCurrentIndex(x)
                scene = self.getCurrentPageScene()
                if scene:
                    scene.addPageNbr(text + " " + str(self.tabs.currentIndex() + 1), font, align)

    def addYearToPage(self):
        """Add a year header to the active page."""
        scene = self.getCurrentPageScene()
        if scene:
            scene.addPageYear()

    def addYearToAllPages(self):
        """Prompt user and apply a year header across all album pages."""
        textLabel = QGraphicsTextItem("")
        textLabelFont = textLabel.font()
        textLabelFont.setPointSize(10)
        textLabelFont.setBold(True)
        textLabel.setFont(textLabelFont)

        dlg = TextDlg(textLabel)
        res = dlg.exec()
        if res == 1:
            text = dlg.eTXT.toPlainText()
            font = dlg.eTXT.font()
            align = dlg.eTXT.alignment()

            for x in range(0, self.tabs.count().real):
                self.tabs.setCurrentIndex(x)
                scene = self.getCurrentPageScene()
                if scene:
                    scene.addYear(text, font, align)

    def openAlbumFile(self):
        """
        Open and deserialize a compressed (.sta) or plain XML album file.
        Safely prompts to save unsaved modifications first, clears the workspace,
        loads pages and metadata, and resets the dirty state across all undo stacks.
        """
        # 1. Prompt user to save current changes if any unsaved work exists
        if not self.maybe_save():
            return

        # 2. Select file before touching any existing album data
        options = QFileDialog.Option.DontUseNativeDialog
        fileName, _filter = QFileDialog.getOpenFileName(
            self, _("Open Album file"), "", _("Album Files (*.sta)"), options=options
        )
        if not fileName:
            return

        # 3. Read and parse XML document using safe context management
        try:
            if fileName.lower().endswith(".sta"):
                with gzip.open(fileName, "rb") as f:
                    mytree = ET.parse(f)
            else:
                with open(fileName, "r", encoding="utf-8") as f:
                    mytree = ET.parse(f)
            myroot = mytree.getroot()
        except Exception as e:
            QMessageBox.critical(
                self,
                _("Error Opening File"),
                "{msg}\n{error}".format(
                    msg=_("Failed to open or parse album file:"),
                    error=str(e)
                )
            )
            return

        # 4. Clear current workspace now that reading has succeeded
        self.deleteAllPages()
        self.currentAlbumName = fileName
        self.updateStatusFile(fileName)

        # 5. Extract metadata block if present, otherwise set defaults
        meta_node = myroot.find("metadata")
        if meta_node is not None:
            self.album_metadata = {
                "creation_date": meta_node.findtext("creation_date", ""),
                "author": meta_node.findtext("author", ""),
                "language": meta_node.findtext("language", "fr"),
                "os": meta_node.findtext("os", f"{platform.system()} {platform.release()}"),
                "page_count": int(meta_node.findtext("page_count", "0")),
                "stamp_count": int(meta_node.findtext("stamp_count", "0"))
            }
        else:
            self.album_metadata = {
                "creation_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "author": "",
                "language": "fr",
                "os": f"{platform.system()} {platform.release()}",
                "page_count": 0,
                "stamp_count": 0
            }

        # 6. Reconstruct pages and graphic items based on file version
        file_version = myroot.attrib.get("version", "0.9")
        if file_version == "0.9":
            self.openOldAlbumFileVersion(myroot)
        else:
            self.openNewAlbumFileVersion(myroot)

        # 7. Apply album language to all newly created scenes
        album_lang = self.album_metadata.get("language", "fr")
        for i in range(self.tabs.count()):
            widget = self.tabs.widget(i)
            if hasattr(widget, "view") and widget.view and widget.view.scene():
                widget.view.scene().album_language = album_lang

        # 8. Mark all newly created pages as clean and synchronized with disk
        for x in range(self.tabs.count()):
            widget = self.tabs.widget(x)
            if hasattr(widget, "view") and widget.view and widget.view.scene():
                scene = widget.view.scene()
                if hasattr(scene, "undoStack"):
                    scene.undoStack.setClean()

        # 9. Update UI titles, tab labels, and dirty flag indicators
        self.setWindowModified(False)
        self.update_window_title()
        self.renameTabs()

        # 10. Display the first page if pages were loaded
        if self.tabs.count() > 0:
            self.tabs.setCurrentIndex(0)

    def openOldAlbumFileVersion(self, myroot):
        for it in myroot.findall('page'):
            self.newPage(str(it.attrib.get("type")), False)
            currentPage = self.getCurrentPageScene()
            if not currentPage:
                continue

            textLabelsItems = it.findall('textLabel')
            for textLabel in textLabelsItems:
                label = textLabel.find('label').text
                font = textLabel.find('font')
                bold = font.find('bold').text
                underline = font.find('underline').text
                italic = font.find('italic').text
                strikeOut = font.find('strikeOut').text
                pointSize = font.find('pointSize').text

                myFont = QFont()
                myFont.setBold(self.str_to_bool(bold))
                myFont.setUnderline(self.str_to_bool(underline))
                myFont.setItalic(self.str_to_bool(italic))
                myFont.setStrikeOut(self.str_to_bool(strikeOut))
                myFont.setPointSize(int(pointSize))

                pos = textLabel.find('labelPos')
                x = pos.find('x').text
                y = pos.find('y').text

                currentPage.addTextLabel(label, float(x), float(y), myFont)

            richTextLabelsItems = it.findall('richTextLabel')
            for richLabel in richTextLabelsItems:
                html_element = richLabel.find('html_label')
                html_content = html_element.text if html_element is not None else ""

                pos = richLabel.find('labelPos')
                x = pos.find('x').text if pos is not None and pos.find('x') is not None else 50.0
                y = pos.find('y').text if pos is not None and pos.find('y') is not None else 50.0

                currentPage.addRichText(html_content, float(x), float(y))

            imageItems = it.findall('imageItem')
            for img_node in imageItems:
                pixmap_data = img_node.find('pixmapData')
                if pixmap_data is not None and pixmap_data.text:
                    pixmap = self.bytesToPixmap(pixmap_data.text)

                    if not pixmap.isNull():
                        pos = img_node.find('imagePos')
                        x = float(pos.find('x').text) if pos is not None and pos.find('x') is not None else 50.0
                        y = float(pos.find('y').text) if pos is not None and pos.find('y') is not None else 50.0
                        scale_val = float(img_node.find('scale').text) if img_node.find('scale') is not None else 1.0

                        pixmap_item = ResizablePixmapItem(pixmap)
                        pixmap_item.setPos(x, y)
                        pixmap_item.setScale(scale_val)

                        currentPage.addItem(pixmap_item)

            copyrightLabelsItems = it.findall('labelCopyRight')
            for copyrightLabel in copyrightLabelsItems:
                label = copyrightLabel.find('label').text
                font = copyrightLabel.find('font')
                myFont = QFont()
                myFont.setBold(self.str_to_bool(font.find('bold').text))
                myFont.setUnderline(self.str_to_bool(font.find('underline').text))
                myFont.setItalic(self.str_to_bool(font.find('italic').text))
                myFont.setStrikeOut(self.str_to_bool(font.find('strikeOut').text))
                myFont.setPointSize(int(font.find('pointSize').text))

                pos = copyrightLabel.find('labelPos')
                currentPage.addTextLabel(
                    label, float(pos.find('x').text), float(pos.find('y').text),
                    myFont, Qt.AlignmentFlag.AlignLeft, "labelCopyRight"
                )

            pageNbrLabelsItems = it.findall('labelPageNbr')
            for pageNbrLabel in pageNbrLabelsItems:
                label = pageNbrLabel.find('label').text
                font = pageNbrLabel.find('font')
                myFont = QFont()
                myFont.setBold(self.str_to_bool(font.find('bold').text))
                myFont.setUnderline(self.str_to_bool(font.find('underline').text))
                myFont.setItalic(self.str_to_bool(font.find('italic').text))
                myFont.setStrikeOut(self.str_to_bool(font.find('strikeOut').text))
                myFont.setPointSize(int(font.find('pointSize').text))

                pos = pageNbrLabel.find('labelPos')
                currentPage.addTextLabel(
                    label, float(pos.find('x').text), float(pos.find('y').text),
                    myFont, Qt.AlignmentFlag.AlignLeft, "labelPageNbr"
                )

            yearLabelsItems = it.findall('labelYear')
            for yearLabel in yearLabelsItems:
                label = yearLabel.find('label').text
                font = yearLabel.find('font')
                myFont = QFont()
                myFont.setBold(self.str_to_bool(font.find('bold').text))
                myFont.setUnderline(self.str_to_bool(font.find('underline').text))
                myFont.setItalic(self.str_to_bool(font.find('italic').text))
                myFont.setStrikeOut(self.str_to_bool(font.find('strikeOut').text))
                myFont.setPointSize(int(font.find('pointSize').text))

                pos = yearLabel.find('labelPos')
                currentPage.addTextLabel(
                    label, float(pos.find('x').text), float(pos.find('y').text),
                    myFont, Qt.AlignmentFlag.AlignCenter, "labelYear"
                )

            pageBorderItem = it.findall('borderGroup')
            for border in pageBorderItem:
                pos = border.find('borderPos')
                x = pos.find('x').text
                y = pos.find('y').text
                width1 = border.find('width1').text
                height1 = border.find('height1').text
                border_style = border.attrib.get("style", PageBorder.STYLE_TRIPLE)

                currentPage.addBorder(
                    float(width1), float(height1),
                    float(x), float(y), 0, 0, style=border_style
                )

            stampItems = it.findall('stampGroup')
            for stamp in stampItems:
                pos = stamp.find('stampPos')
                x = pos.find('x').text
                y = pos.find('y').text

                sizeBox = stamp.find('stampBox')
                width = sizeBox.find('width').text
                height = sizeBox.find('height').text
                try:
                    stampBox_width = sizeBox.find('stampBox_width').text
                    stampBox_height = sizeBox.find('stampBox_height').text
                    use_new = 1
                except:
                    use_new = 0

                stampDesc = stamp.find('stampDesc').text or ""
                stampNbr = stamp.find('stampNbr').text
                stampValue = stamp.find('stampValue').text
                pixmapItem = stamp.find('pixmapItem').text

                stamp_obj = Stamp()
                pixmap = self.bytesToPixmap(pixmapItem)

                if use_new == 1:
                    stamp_obj.createStampPixOldVersion(
                        currentPage, str(stampNbr), str(stampValue), str(stampDesc),
                        float(stampBox_width), float(stampBox_height),
                        float(x), float(y), pixmap
                    )
                else:
                    stamp_obj.createStampPixOldVersion(
                        currentPage, str(stampNbr), str(stampValue), str(stampDesc),
                        float(width) * (25.4 / 96.0), float(height) * (25.4 / 96.0),
                        float(x), float(y), pixmap
                    )

    def openNewAlbumFileVersion(self, myroot):
        """Deserialize and reconstruct a complete album structure from XML root element."""
        for it in myroot.findall('page'):
            page_type = str(it.attrib.get("type", "portrait"))
            paper_format = str(it.attrib.get("paper_format", "A4"))

            # Create new page tab without initial default border
            self.newPage(page_type, False, paper_format=paper_format)
            currentPage = self.getCurrentPageScene()
            if not currentPage:
                continue

            # --- Internal helper to restore standard text items ---
            def restore_text_item(label_nodes, label_type, default_x, default_y, default_align, default_pt=10):
                for node in label_nodes:
                    text_str = node.find('label').text or ""
                    font_node = node.find('font')

                    myFont = QFont()
                    if font_node is not None:
                        myFont.setBold(self.str_to_bool(font_node.find('bold').text))
                        myFont.setUnderline(self.str_to_bool(font_node.find('underline').text))
                        myFont.setItalic(self.str_to_bool(font_node.find('italic').text))
                        myFont.setStrikeOut(self.str_to_bool(font_node.find('strikeOut').text))
                        myFont.setPointSize(int(font_node.find('pointSize').text))
                    else:
                        myFont.setPointSize(default_pt)

                    pos_node = node.find('labelPos')
                    x = float(pos_node.find('x').text) if pos_node is not None and pos_node.find(
                        'x') is not None and pos_node.find('x').text else default_x
                    y = float(pos_node.find('y').text) if pos_node is not None and pos_node.find(
                        'y') is not None and pos_node.find('y').text else default_y

                    item = QGraphicsTextItem(text_str)
                    item.setFont(myFont)
                    item.setData(0, label_type)

                    item.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
                    item.setFlags(
                        QGraphicsTextItem.GraphicsItemFlag.ItemIsMovable |
                        QGraphicsTextItem.GraphicsItemFlag.ItemIsSelectable
                    )

                    item.setTextWidth(item.boundingRect().size().width())

                    cursor = item.textCursor()
                    cursor.select(QTextCursor.SelectionType.Document)
                    format = QTextBlockFormat()
                    format.setAlignment(default_align)
                    cursor.mergeBlockFormat(format)
                    cursor.clearSelection()
                    item.setTextCursor(cursor)

                    item.setPos(x, y)
                    currentPage.addItem(item)

            # --- Restore all text categories ---
            restore_text_item(it.findall('textLabel'), "textLabel", 20.0, 20.0, Qt.AlignmentFlag.AlignCenter)
            restore_text_item(it.findall('labelCopyRight'), "labelCopyRight", 80.0, 1045.0, Qt.AlignmentFlag.AlignLeft,
                              6)
            restore_text_item(it.findall('labelPageNbr'), "labelPageNbr", 600.0, 1045.0, Qt.AlignmentFlag.AlignLeft, 8)
            restore_text_item(it.findall('labelYear'), "labelYear", 350.0, 80.0, Qt.AlignmentFlag.AlignCenter, 10)

            # --- Restore Rich Text Labels ---
            for richLabel in it.findall('richTextLabel'):
                html_element = richLabel.find('html_label')
                html_content = html_element.text if html_element is not None and html_element.text else ""

                pos = richLabel.find('labelPos')
                x = float(pos.find('x').text) if pos is not None and pos.find('x') is not None and pos.find(
                    'x').text else 50.0
                y = float(pos.find('y').text) if pos is not None and pos.find('y') is not None and pos.find(
                    'y').text else 50.0

                item = QGraphicsTextItem()
                item.setHtml(html_content)

                item.setTextWidth(-1)
                item.setPos(x, y)
                item.setData(0, "richTextLabel")
                item.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
                item.setFlags(
                    QGraphicsTextItem.GraphicsItemFlag.ItemIsMovable |
                    QGraphicsTextItem.GraphicsItemFlag.ItemIsSelectable
                )
                currentPage.addItem(item)

            # --- Restore Standalone Images ---
            for img_node in it.findall('imageItem'):
                pixmap_data = img_node.find('pixmapData')
                if pixmap_data is not None and pixmap_data.text:
                    pixmap = self.bytesToPixmap(pixmap_data.text)
                    if not pixmap.isNull():
                        pos = img_node.find('imagePos')
                        x = float(pos.find('x').text) if pos is not None and pos.find('x') is not None and pos.find(
                            'x').text else 50.0
                        y = float(pos.find('y').text) if pos is not None and pos.find('y') is not None and pos.find(
                            'y').text else 50.0
                        scale_node = img_node.find('scale')
                        scale_val = float(scale_node.text) if scale_node is not None and scale_node.text else 1.0

                        pixmap_item = ResizablePixmapItem(pixmap)
                        pixmap_item.setPos(x, y)
                        pixmap_item.setScale(scale_val)
                        currentPage.addItem(pixmap_item)

            # --- Restore Page Borders ---
            for border in it.findall('borderGroup'):
                pos = border.find('borderPos')
                x = float(pos.find('x').text) if pos is not None and pos.find('x') is not None and pos.find(
                    'x').text else 0.0
                y = float(pos.find('y').text) if pos is not None and pos.find('y') is not None and pos.find(
                    'y').text else 0.0

                width_node = border.find('width1')
                height_node = border.find('height1')
                width1 = float(width_node.text) if width_node is not None and width_node.text else 0.0
                height1 = float(height_node.text) if height_node is not None and height_node.text else 0.0

                border_style = border.attrib.get("style", PageBorder.STYLE_TRIPLE)

                # Direct instantiation to preserve exact saved (x, y) coordinates
                border_item = PageBorder(width1, height1, style=border_style)
                border_item.setPos(x, y)
                currentPage.addItem(border_item)

            # --- Restore Stamp Groups (INDENTED AT THE PAGE LEVEL) ---
            for stamp in it.findall('stampGroup'):
                pos = stamp.find('stampPos')
                x = float(pos.find('x').text) if pos is not None and pos.find('x') is not None and pos.find(
                    'x').text else 0.0
                y = float(pos.find('y').text) if pos is not None and pos.find('y') is not None and pos.find(
                    'y').text else 0.0

                sizeBox = stamp.find('stampBox')
                width = float(sizeBox.find('width').text) if sizeBox is not None and sizeBox.find(
                    'width') is not None and sizeBox.find('width').text else 0.0
                height = float(sizeBox.find('height').text) if sizeBox is not None and sizeBox.find(
                    'height') is not None and sizeBox.find('height').text else 0.0
                try:
                    stampBox_width = float(sizeBox.find('stampBox_width').text)
                    stampBox_height = float(sizeBox.find('stampBox_height').text)
                    use_new = 1
                except Exception:
                    use_new = 0

                desc_node = stamp.find('stampDesc')
                stampDesc = desc_node.text if desc_node is not None and desc_node.text else ""

                nbr_node = stamp.find('stampNbr')
                stampNbr = nbr_node.text if nbr_node is not None and nbr_node.text else ""

                val_node = stamp.find('stampValue')
                stampValue = val_node.text if val_node is not None and val_node.text else ""

                pix_node = stamp.find('pixmapItem')
                pixmapItem = pix_node.text if pix_node is not None and pix_node.text else ""

                stamp_obj = Stamp()
                pixmap = self.bytesToPixmap(pixmapItem)

                if use_new == 1:
                    stamp_obj.createStampPix(
                        currentPage, str(stampNbr), str(stampValue), str(stampDesc),
                        stampBox_width, stampBox_height,
                        x, y, pixmap
                    )
                else:
                    stamp_obj.createStampPix(
                        currentPage, str(stampNbr), str(stampValue), str(stampDesc),
                        float(width) * (25.4 / 96.0), float(height) * (25.4 / 96.0),
                        x, y, pixmap
                    )

            # --- Restore Rich Text Stamp Groups ---
            for r_stamp in it.findall('richTextStampGroup'):
                pos = r_stamp.find('stampPos')
                x = float(pos.find('x').text) if pos is not None and pos.find('x') is not None and pos.find(
                    'x').text else 50.0
                y = float(pos.find('y').text) if pos is not None and pos.find('y') is not None and pos.find(
                    'y').text else 50.0

                desc_node = r_stamp.find('stampDesc')
                desc_html = desc_node.findtext('html', '') if desc_node is not None else ""

                nbr_node = r_stamp.find('stampNbr')
                nbr_html = nbr_node.findtext('html', '') if nbr_node is not None else ""

                val_node = r_stamp.find('stampValue')
                val_html = val_node.findtext('html', '') if val_node is not None else ""

                box_node = r_stamp.find('stampBox')
                width_mm = float(box_node.findtext('width_mm', '25.0')) if box_node is not None else 25.0
                height_mm = float(box_node.findtext('height_mm', '30.0')) if box_node is not None else 30.0

                pix_data = r_stamp.findtext('pixmapData', '')
                pixmap = self.bytesToPixmap(pix_data)

                from Stamp import RichTextStamp
                stamp_helper = RichTextStamp()
                stamp_helper.createRichStampPix(
                    currentPage,
                    nbr_html=nbr_html,
                    value_html=val_html,
                    desc_html=desc_html,
                    boxWidth=width_mm,
                    boxHeight=height_mm,
                    x=x,
                    y=y,
                    pixmap=pixmap
                )

    def saveAlbumToFile(self) -> bool:
        """
        Serialize album structure into a gzip-compressed XML file (.sta).
        Returns:
            bool: True if the file was saved successfully, False if cancelled or failed.
        """
        options = QFileDialog.Option.DontUseNativeDialog
        fileName, _filter = QFileDialog.getSaveFileName(
            self, _("Save Album"), "", _("Album Files (*.sta)"), options=options
        )
        if not fileName:
            return False # User cancelled the file save dialog

        if fileName.find(".") != -1:
            fileNameArray = fileName.split(".")
            if fileNameArray[len(fileNameArray) - 1] == "sta":
                fileName = fileName.rsplit('.', maxsplit=1)[0]


        self.currentAlbumName = fileName
        self.updateStatusFile(fileName + '.sta')
        root = ET.Element("album", version=FILE_FORMAT_VERSION)

        # Calculate current counts and update active environment
        total_pages = self.tabs.count()
        total_stamps = self.countTotalStamps()
        current_os = f"{platform.system()} {platform.release()}"
        creation_date = self.album_metadata.get("creation_date") or datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        self.album_metadata["page_count"] = total_pages
        self.album_metadata["stamp_count"] = total_stamps
        self.album_metadata["os"] = current_os
        self.album_metadata["creation_date"] = creation_date

        # Write metadata block to XML root
        meta_elem = ET.SubElement(root, "metadata")
        ET.SubElement(meta_elem, "creation_date").text = str(creation_date)
        ET.SubElement(meta_elem, "author").text = str(self.album_metadata.get("author", ""))
        ET.SubElement(meta_elem, "os").text = str(current_os)
        ET.SubElement(meta_elem, "page_count").text = str(total_pages)
        ET.SubElement(meta_elem, "stamp_count").text = str(total_stamps)
        ET.SubElement(meta_elem, "language").text = str(self.album_metadata.get("language", "fr"))

        for x in range(self.tabs.count()):
            self.tabs.setCurrentIndex(x)

            currentScene = self.getCurrentPageScene()
            if not currentScene:
                continue

            # Save pageType and paper_format on page element
            paper_fmt = getattr(currentScene, "paper_format", "A4")
            page = ET.SubElement(
                root, "page", name="%s" % x, type="%s" % currentScene.pageType, paper_format="%s" % paper_fmt
            )
            items = currentScene.items()

            for item in items:
                if item.type().real == 8:
                    par = item.parentItem()
                    if par is None:
                        item_type = item.data(0) or "textLabel"
                        textLbl = ET.SubElement(page, item_type)

                        if item_type == "richTextLabel":
                            ET.SubElement(textLbl, "html_label").text = item.toHtml()
                        else:
                            ET.SubElement(textLbl, "label").text = item.toPlainText()

                            font = ET.SubElement(textLbl, "font")
                            ET.SubElement(font, "bold").text = str(item.font().bold())
                            ET.SubElement(font, "underline").text = str(item.font().underline())
                            ET.SubElement(font, "italic").text = str(item.font().italic())
                            ET.SubElement(font, "strikeOut").text = str(item.font().strikeOut())
                            ET.SubElement(font, "pointSize").text = str(item.font().pointSize())

                        pos = ET.SubElement(textLbl, "labelPos")
                        ET.SubElement(pos, "x").text = str(item.x())
                        ET.SubElement(pos, "y").text = str(item.y())

                elif item.type().real == 7:
                    par = item.parentItem()
                    if par is None:
                        img_node = ET.SubElement(page, "imageItem")

                        pix = item.pixmap()
                        ET.SubElement(img_node, "pixmapData").text = str(self.pixmapToBytes(pix))

                        pos = ET.SubElement(img_node, "imagePos")
                        ET.SubElement(pos, "x").text = str(item.x())
                        ET.SubElement(pos, "y").text = str(item.y())
                        ET.SubElement(img_node, "scale").text = str(item.scale())

                elif item.type().real == 10 and item.data(0) == "borderGroup":
                    border = ET.SubElement(page, item.data(0))
                    border_style = item.data(4) or PageBorder.STYLE_TRIPLE
                    border.set("style", str(border_style))

                    borderItems = item.childItems()
                    pos = ET.SubElement(border, "borderPos")
                    ET.SubElement(pos, "x").text = str(item.x())
                    ET.SubElement(pos, "y").text = str(item.y())
                    i = 0
                    for borderItem in borderItems:
                        if borderItem.type().real == 3:
                            i += 1
                            ET.SubElement(border, "width" + str(i)).text = str(borderItem.data(1))
                            ET.SubElement(border, "height" + str(i)).text = str(borderItem.data(2))

                elif item.type().real == 10 and item.data(0) == "stampGroup":
                    stamp = ET.SubElement(page, item.data(0))
                    stampItems = item.childItems()

                    pos = ET.SubElement(stamp, "stampPos")
                    ET.SubElement(pos, "x").text = str(item.x())
                    ET.SubElement(pos, "y").text = str(item.y())
                    for stampItem in stampItems:
                        if stampItem.type().real == 8:
                            ET.SubElement(stamp, stampItem.data(0)).text = stampItem.toPlainText()
                        elif stampItem.type().real == 7:
                            pix = stampItem.pixmap()
                            ET.SubElement(stamp, stampItem.data(0)).text = str(self.pixmapToBytes(pix))
                        elif stampItem.type().real == 3:
                            size = ET.SubElement(stamp, stampItem.data(0))
                            ET.SubElement(size, "width").text = str(stampItem.boundingRect().width())
                            ET.SubElement(size, "height").text = str(stampItem.boundingRect().height())
                            ET.SubElement(size, "stampBox_width").text = str(int(stampItem.data(1)))
                            ET.SubElement(size, "stampBox_height").text = str(int(stampItem.data(2)))

                elif item.type().real == 10 and item.data(0) == "richTextStampGroup":
                    r_stamp = ET.SubElement(page, "richTextStampGroup")
                    pos = ET.SubElement(r_stamp, "stampPos")
                    ET.SubElement(pos, "x").text = str(item.x())
                    ET.SubElement(pos, "y").text = str(item.y())

                    for child in item.childItems():
                        child_key = str(child.data(0))
                        if child_key in ["stampDesc", "stampNbr", "stampValue"]:
                            node = ET.SubElement(r_stamp, child_key)
                            ET.SubElement(node, "html").text = child.toHtml()
                        elif child_key == "pixmapItem":
                            pix = child.pixmap()
                            ET.SubElement(r_stamp, "pixmapData").text = str(self.pixmapToBytes(pix))
                        elif child_key == "stampBox":
                            box_elem = ET.SubElement(r_stamp, "stampBox")
                            ET.SubElement(box_elem, "width_mm").text = str(child.data(1))
                            ET.SubElement(box_elem, "height_mm").text = str(child.data(2))

        tree = ET.ElementTree(root)
        tree.write(fileName)

        f = gzip.open(fileName + '.sta', 'wb')
        ET.ElementTree(root).write(f)
        f.close()

        if os.path.isfile(fileName):
            os.remove(fileName)

        # 1. Mark every page's undo stack as clean and synchronized with disk
        for x in range(self.tabs.count()):
            widget = self.tabs.widget(x)
            if hasattr(widget, 'view') and widget.view and widget.view.scene():
                widget.view.scene().undoStack.setClean()

        # 2. Reset the window dirty flag and update UI indicators
        self.setWindowModified(False)
        self.update_window_title()
        self.renameTabs()
        return True

    def printAllPagesPDF(self):
        """Export all album pages into a single PDF document."""
        scenes = self._allScenes()
        if not scenes:
            return

        # Prompt for save path if album has no filename
        pdf_name = (self.currentAlbumName + ".pdf") if self.currentAlbumName else ""
        if not pdf_name:
            options = QFileDialog.Option.DontUseNativeDialog
            pdf_name, _filter = QFileDialog.getSaveFileName(self, _("Save album as PDF"), "album.pdf",
                                                            "(*.pdf)", options=options)
            if not pdf_name:
                return

        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
        printer.setOutputFileName(pdf_name)
        self._renderScenes(printer, scenes)

    def printPreviewAllPages(self):
        """Open print preview dialog for all pages."""
        previewDialog = QPrintPreviewDialog()
        previewDialog.printer().setResolution(QPrinter.PrinterMode.HighResolution.value)
        previewDialog.printer().setOutputFormat(QPrinter.OutputFormat.PdfFormat)
        previewDialog.paintRequested.connect(self.createPreview)
        previewDialog.exec()

    def createPreview(self, printer):
        """Paint target pages into the QPrintPreviewDialog context."""
        scenes = self._allScenes()
        if scenes:
            self._renderScenes(printer, scenes)

    def _allScenes(self):
        """List scenes of all album pages without changing active displayed tab."""
        scenes = []
        for i in range(self.tabs.count()):
            widget = self.tabs.widget(i)
            if hasattr(widget, 'view') and widget.view and widget.view.scene():
                scenes.append(widget.view.scene())
        return scenes

    def _renderScenes(self, printer, scenes):
        """
        Render multiple pages into a single document: each page receives its own
        format (A4/Letter) and orientation BEFORE being painted.
        """
        scenes[0].apply_page_layout(printer)
        p = QPainter(printer)
        for x, scene in enumerate(scenes):
            if x > 0:
                scene.apply_page_layout(printer)  # mise en page de la page suivante
                printer.newPage()
            scene.renderToPrinter(p, printer)
        p.end()

    def printPagePDF(self):
        """Export active page to a PDF file."""
        options = QFileDialog.Option.DontUseNativeDialog
        fileName2, _filter = QFileDialog.getSaveFileName(self, _("Save current page"), "album.pdf",
                                                         "(*.pdf)", options=options)
        if not fileName2:
            return
        scene = self.getCurrentPageScene()
        if scene:
            scene.printPagePDF(fileName2)

    def printPreviewCurrentPage(self):
        """Display print preview for the active page."""
        scene = self.getCurrentPageScene()
        if scene:
            scene.printPreview()

    def importFileFromExcel(self):
        pass

    def copy(self):
        """Copy selected scene items to clipboard."""
        view = self.getCurrentPage()
        if view:
            view.copy_items()

    def cut(self):
        """Cut selected scene items to clipboard."""
        view = self.getCurrentPage()
        scene = self.getCurrentPageScene()
        if view:
            view.copy_items()
        if scene:
            scene.removeItems()

    def paste(self):
        """Paste scene items from clipboard."""
        view = self.getCurrentPage()
        if view:
            view.paste_items()

    def createNewStamp(self):
        """Open creation dialog to insert a new stamp item."""
        scene = self.getCurrentPageScene()
        if scene:
            stamp = scene.newStamp(self.lastStampObj)
            if stamp is not None:
                self.lastStampObj['year'] = stamp['year']
                self.lastStampObj['type'] = stamp['type']
                self.lastStampObj['country'] = stamp['country']
                self.lastStampObj['nbr'] = stamp['nbr']

    def createNewCustomStamp(self):
        """Open custom stamp creation dialog and place item onto the active scene."""
        scene = self.getCurrentPageScene()
        if scene:
            dlg = CustomStampDlg(scene=scene, parent=self)
            dlg.exec()

    def editStamp(self):
        """Edit currently selected stamp item."""
        scene = self.getCurrentPageScene()
        if scene:
            scene.editObject()

    def about(self):
        """Display custom scrollable 'About' dialog."""
        dlg = AboutDlg(self)
        dlg.exec()

    def help(self):
        """Open user help PDF document in default system viewer."""
        lang = get_language()
        docs_dir = self._get_resource_dir("Help")

        if lang == "fr":
            help_file = docs_dir / "StampAlbum Manuel utilisateur 18-10-2026.pdf"
        else:
            help_file = docs_dir / "Stamp Album user Manual 18-10-2026.pdf"

        if not help_file.is_file():
            QMessageBox.warning(self, _("Help"), _("Help file not found:") + f"\n{help_file}")
            return
        # Open PDF using default system viewer across Windows, macOS, and Linux
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(help_file)))

    def alignBottom(self):
        scene = self.getCurrentPageScene()
        if scene:
            scene.alignBottom()

    def alignTop(self):
        scene = self.getCurrentPageScene()
        if scene:
            scene.alignTop()

    def alignLeft(self):
        scene = self.getCurrentPageScene()
        if scene:
            scene.alignLeft()

    def alignRight(self):
        scene = self.getCurrentPageScene()
        if scene:
            scene.alignRight()

    def distributeHorizontally(self):
        scene = self.getCurrentPageScene()
        if scene:
            scene.distributeHorizontally()

    def distributeVertically(self):
        scene = self.getCurrentPageScene()
        if scene:
            scene.distributeVertically()

    def centerHorizontally(self):
        scene = self.getCurrentPageScene()
        if scene:
            scene.centerHorizontally()

    def centerVertically(self):
        scene = self.getCurrentPageScene()
        if scene:
            scene.centerVertically()

    def createText(self):
        """Create a new floating text label."""
        scene = self.getCurrentPageScene()
        if scene:
            scene.newLabel()

    def gridOnOff(self):
        """Toggle grid pattern background in active scene."""
        print("gridOnOff")
        child = self.getCurrentPageScene()
        if child:
            if child.gridOn:
                # Restore plain white background when disabling grid
                child.setBackgroundBrush(QBrush(Qt.GlobalColor.white))
                child.gridOn = False
            else:
                print("drawGrid")
                child.setBackgroundBrush(QBrush(self.drawGrid()))
                child.gridOn = True

    def drawGrid(self):
        """Generate grid texture pixmap."""
        self.pixmap = QPixmap(10, 10)
        pixmapWidth = self.pixmap.width() - 1
        painter = QPainter()
        self.pixmap.fill(Qt.GlobalColor.white)

        painter.begin(self.pixmap)
        painter.setPen(Qt.GlobalColor.gray)
        painter.drawLine(0, 0, pixmapWidth, 0)
        painter.drawLine(0, 0, 0, pixmapWidth)
        painter.end()
        return self.pixmap

    def deleteGrid(self):
        """Generate transparent texture pixmap to disable grid."""
        pixmap = QPixmap(10, 10)
        pixmap.fill(Qt.GlobalColor.transparent)
        return pixmap

    def pixmapToBytes(self, pixmap):
        """Encode QPixmap to Base64 PNG string."""
        # Empty pixmap (missing picture) must not cause serialization to fail
        if pixmap is None or pixmap.isNull():
            return ""
        ba = QtCore.QByteArray()
        buff = QtCore.QBuffer(ba)
        buff.open(QtCore.QIODevice.OpenModeFlag.WriteOnly)
        if not pixmap.save(buff, "PNG"):
            return ""
        return bytes(ba.toBase64()).decode()

    def bytesToPixmap(self, pixmap_bytes):
        """Decode Base64 PNG string back to QPixmap (QPixmap vide si absent ou illisible)."""
        pixmap = QtGui.QPixmap()
        if not pixmap_bytes:
            return pixmap
        ba = QtCore.QByteArray().fromBase64(pixmap_bytes.encode())
        if not pixmap.loadFromData(ba, "PNG"):
            print("Warning: unreadable image data in album file")
        return pixmap

    def getCurrentPageScene(self):
        """Return QGraphicsScene instance from the active tab widget safely."""
        view = self.getCurrentPage()
        if view:
            return view.scene()
        return None

    def getCurrentPage(self):
        """Return GraphicsView instance from the active tab widget safely."""
        curr_widget = self.tabs.currentWidget()
        if curr_widget and hasattr(curr_widget, "view"):
            return curr_widget.view
        return None

    def mousePressEvent(self, event):
        self._drawing = True
        self.last_point = event.pos()

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton:
            self.last_point = event.pos()

    def mouseDoubleClickEvent(self, event):
        scene = self.getCurrentPageScene()
        if scene:
            scene.editObject()

    def keyPressEvent(self, event):
        """Handle main keyboard shortcuts for deleting or editing items."""
        scene = self.getCurrentPageScene()
        if not scene:
            return

        if event.key() == Qt.Key.Key_Escape:
            scene.printObjectDebugInfo()
        elif event.key() == Qt.Key.Key_Delete:
            qm = QMessageBox()
            ret = qm.question(self, _('Delete Object'), _("Are you sure you want to delete those objects?"),
                              qm.StandardButton.Yes | qm.StandardButton.No)

            if ret == qm.StandardButton.No:
                return
            scene.removeItems()
        elif event.key() == Qt.Key.Key_E:
            scene.editObject()

    def newCopyRight(self):
        """Add copyright text label to current page."""
        scene = self.getCurrentPageScene()
        if scene:
            scene.newCopyRight()

    def newCopyRightAllPages(self):
        """Add copyright text label across all pages."""
        for x in range(0, self.tabs.count().real):
            self.tabs.setCurrentIndex(x)
            scene = self.getCurrentPageScene()
            if scene:
                scene.newCopyRight()

    def newImage(self):
        """Prompt user for image file and add it to the scene."""
        options = QFileDialog.Option.DontUseNativeDialog
        fileName, _filter = QFileDialog.getOpenFileName(self, _("Select picture"), "",
                                                        ("all pictures (*.jpg *.jpeg *.png);;PNG (*.png)"),
                                                        options=options)
        if not fileName:
            return
        scene = self.getCurrentPageScene()
        if scene:
            scene.addImage(fileName)

    def str_to_bool(self, s):
        """Convert string boolean representations to Python bool."""
        if s == 'True':
            return True
        elif s == 'False':
            return False
        else:
            raise ValueError

    def configApp(self):
        """Open application configuration dialog."""
        dlg = ConfigDlg()
        res = dlg.exec()

    def autoArrangeStamps(self):
        """Trigger harmonious stamp layout distribution on the active page."""
        scene = self.getCurrentPageScene()
        if scene and hasattr(scene, "autoArrangeStamps"):
            scene.autoArrangeStamps()

    def openThumbnails(self):
        """Open contact sheet dialog to visually reorder album pages."""
        from ThumbnailsDlg import ThumbnailsDlg
        dlg = ThumbnailsDlg(self.tabs, self)

        if dlg.exec() == 1:
            new_order = dlg.get_new_order()

            # Check if order actually changed before rebuilding tabs
            if new_order == list(range(self.tabs.count())):
                return

            # Cache existing tab page widgets
            widgets = [self.tabs.widget(i) for i in range(self.tabs.count())]

            # Clear tabs and recreate them in the selected sequence
            self.tabs.blockSignals(True)
            self.tabs.clear()

            for original_index in new_order:
                self.tabs.addTab(widgets[original_index], "")  # Tab text set by renameTabs

            self.tabs.blockSignals(False)

            # Sequentially rename tabs cleanly
            self.renameTabs()

            # Display the first tab page after reordering
            if self.tabs.count() > 0:
                self.tabs.setCurrentIndex(0)

    def changeBorderCurrentPage(self):
        """Open border dialog and update border on the active page."""
        scene = self.getCurrentPageScene()
        if not scene: return

        current_style = None
        for item in scene.items():
            if item.data(0) == "borderGroup":
                current_style = item.data(4)
                break

        from BorderDlg import BorderDlg
        dlg = BorderDlg(current_style, self)
        if dlg.exec() == 1:
            new_style = dlg.get_style()
            scene.replaceBorder(new_style)

    def changeBorderAllPages(self):
        """Open border dialog and apply border across ALL pages in the album."""
        if self.tabs.count() == 0: return

        # Read style of active page by default
        current_scene = self.getCurrentPageScene()
        current_style = None
        if current_scene:
            for item in current_scene.items():
                if item.data(0) == "borderGroup":
                    current_style = item.data(4)
                    break

        from BorderDlg import BorderDlg
        dlg = BorderDlg(current_style, self)
        if dlg.exec() == 1:
            new_style = dlg.get_style()

            # Remember the currently displayed tab index to restore it afterwards
            current_index = self.tabs.currentIndex()

            # Apply change to each tab page
            for i in range(self.tabs.count()):
                self.tabs.setCurrentIndex(i)
                scene = self.getCurrentPageScene()
                if scene:
                    scene.replaceBorder(new_style)

            # Restore initially active tab page
            self.tabs.setCurrentIndex(current_index)

    def importAlbumEasy(self):
        """Import an AlbumEasy (.txt) description file, either replacing or appending to the album."""
        options = QFileDialog.Option.DontUseNativeDialog
        fileName, _filter = QFileDialog.getOpenFileName(
            self, _("Import from AlbumEasy"), "", _("AlbumEasy Files (*.txt);;All Files (*)"), options=options
        )
        if not fileName:
            return

        qm = QMessageBox(self)
        qm.setIcon(QMessageBox.Icon.Question)
        qm.setWindowTitle(_("Import AlbumEasy"))
        qm.setText(_("Do you want to replace the actual album ?\n(Choose 'No' to append it)"))
        qm.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No |
                              QMessageBox.StandardButton.Cancel)
        for btn, label in ((QMessageBox.StandardButton.Yes, _("&Yes")),
                           (QMessageBox.StandardButton.No, _("&No")),
                           (QMessageBox.StandardButton.Cancel, _("&Cancel"))):
            b = qm.button(btn)
            if b:
                b.setText(label)
        ret = qm.exec()
        if ret == QMessageBox.StandardButton.Cancel:
            return

        replace = ret == QMessageBox.StandardButton.Yes
        if replace:
            if not self.maybe_save():
                return
            self.deleteAllPages()
        first_new_index = self.tabs.count()

        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            report = AlbumEasyImporter(self, fileName).run()
        except Exception as e:
            import traceback
            traceback.print_exc()
            QApplication.restoreOverrideCursor()
            QMessageBox.critical(self, _("Import Error"),
                                 "{msg}\n{error}".format(msg=_("An error occurred:"), error=str(e)))
            if self.tabs.count() == 0:
                self.newPage("portrait", True)
            return
        finally:
            if QApplication.overrideCursor() is not None:
                QApplication.restoreOverrideCursor()

        if self.tabs.count() == 0:
            self.newPage("portrait", True)

        # Apply album language to the new scenes
        album_lang = self.album_metadata.get("language", "fr")
        for i in range(self.tabs.count()):
            widget = self.tabs.widget(i)
            if hasattr(widget, "view") and widget.view and widget.view.scene():
                widget.view.scene().album_language = album_lang

        self.renameTabs()
        self.update_window_title()
        self.tabs.setCurrentIndex(min(first_new_index, self.tabs.count() - 1))

        # Import report
        lines = [_("{pages} page(s) and {stamps} stamp(s) imported.").format(
            pages=report["pages"], stamps=report["stamps"])]
        if report["missing_images"]:
            lines.append("")
            lines.append(_("Images not found:"))
            lines += ["  • " + p for p in report["missing_images"][:10]]
            if len(report["missing_images"]) > 10:
                lines.append("  …")
        if report["unsupported"]:
            lines.append("")
            lines.append(_("Ignored commands:"))
            lines += ["  • {0} ({1}x)".format(c, n) for c, n in sorted(report["unsupported"].items())]
        if report["notes"]:
            lines.append("")
            lines += ["  • " + n for n in report["notes"]]
        QMessageBox.information(self, _("Import AlbumEasy"), "\n".join(lines))

    def importExcelAlbum(self):
        """Convert an old Excel/VBA stamp album (.xls, one chart sheet per page) into album pages."""
        options = QFileDialog.Option.DontUseNativeDialog
        fileName, _filter = QFileDialog.getOpenFileName(
            self, _("Import Excel album"), "", _("Excel albums (*.xls);;All Files (*)"), options=options
        )
        if not fileName:
            return

        qm = QMessageBox(self)
        qm.setIcon(QMessageBox.Icon.Question)
        qm.setWindowTitle(_("Import Excel album"))
        qm.setText(_("Do you want to replace the actual album ?\n(Choose 'No' to append it)"))
        qm.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No |
                              QMessageBox.StandardButton.Cancel)
        for btn, label in ((QMessageBox.StandardButton.Yes, _("&Yes")),
                           (QMessageBox.StandardButton.No, _("&No")),
                           (QMessageBox.StandardButton.Cancel, _("&Cancel"))):
            b = qm.button(btn)
            if b:
                b.setText(label)
        ret = qm.exec()
        if ret == QMessageBox.StandardButton.Cancel:
            return

        replace = ret == QMessageBox.StandardButton.Yes
        if replace:
            if not self.maybe_save():
                return
            self.deleteAllPages()
        first_new_index = self.tabs.count()

        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            report = XlsAlbumImporter(self, fileName).run()
        except ImportError:
            QApplication.restoreOverrideCursor()
            QMessageBox.critical(self, _("Import Error"),
                                 _("The 'olefile' module is required:\npip install olefile"))
            if self.tabs.count() == 0:
                self.newPage("portrait", True)
            return
        except Exception as e:
            import traceback
            traceback.print_exc()
            QApplication.restoreOverrideCursor()
            QMessageBox.critical(self, _("Import Error"),
                                 "{msg}\n{error}".format(msg=_("An error occurred:"), error=str(e)))
            if self.tabs.count() == 0:
                self.newPage("portrait", True)
            return
        finally:
            if QApplication.overrideCursor() is not None:
                QApplication.restoreOverrideCursor()

        if self.tabs.count() == 0:
            self.newPage("portrait", True)

        album_lang = self.album_metadata.get("language", "fr")
        for i in range(self.tabs.count()):
            widget = self.tabs.widget(i)
            if hasattr(widget, "view") and widget.view and widget.view.scene():
                widget.view.scene().album_language = album_lang

        self.renameTabs()
        self.update_window_title()
        self.tabs.setCurrentIndex(min(first_new_index, self.tabs.count() - 1))

        lines = [_("{pages} page(s) and {stamps} stamp(s) imported.").format(
            pages=report["pages"], stamps=report["stamps"])]
        if report["no_image"]:
            lines.append(_("{n} stamp(s) without image.").format(n=report["no_image"]))
        if report["warnings"]:
            lines.append("")
            lines += ["  • " + w.replace("\n", " ") for w in report["warnings"]]
        lines.append("")
        lines.append(_("Use File > Save to store the converted album as a .sta file."))
        QMessageBox.information(self, _("Import Excel album"), "\n".join(lines))

    def renameTabs(self, *args):
        """Sequentially rename all tabs, appending an asterisk indicator if modified."""
        self.tabs.blockSignals(True)
        for i in range(self.tabs.count()):
            widget = self.tabs.widget(i)
            prefix = ""

            # Check if the page has unsaved modifications
            if hasattr(widget, 'view') and widget.view and widget.view.scene():
                if not widget.view.scene().undoStack.isClean():
                    prefix = "*"

            self.tabs.setTabText(i, f"{prefix}Page {i + 1}")
        self.tabs.blockSignals(False)