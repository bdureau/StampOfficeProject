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
    QStatusBar, QTabWidget, QWidget
)
from PyQt6.QtGui import QBrush, QPainter, QPixmap, QFont, QTextCursor, QTextBlockFormat
from PyQt6.QtPrintSupport import QPrintPreviewDialog, QPrinter
from Stamp import Stamp
from CustomStampDlg import CustomStampDlg

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
        # On connecte le déplacement d'onglet pour renommer "Page 1, Page 2..." correctement
        self.tabs.tabBar().tabMoved.connect(self.renameTabs)
        self.setCentralWidget(self.tabs)

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

    def _get_icon(self, icon_filename: str) -> QIcon:
        """Utilitaire pour charger une icône depuis le répertoire 'Images' de façon robuste."""
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
            #scene.changePageSetup(dlg.pageType, dlg.paperFormat, dlg.borderStyle)
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
        """Sélectionne tous les éléments mobiles de la page active."""
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
        # Vérification si le QLabel C++ est toujours vivant
        if hasattr(self, 'statusZoomLabel') and self.statusZoomLabel is not None:
            if not sip.isdeleted(self.statusZoomLabel):
                self.statusZoomLabel.setText(f"Zoom: {percent_val}%")

        # Vérification si le QComboBox C++ est toujours vivant
        if hasattr(self, 'zoomCombo') and self.zoomCombo is not None:
            if not sip.isdeleted(self.zoomCombo):
                self.zoomCombo.blockSignals(True)
                self.zoomCombo.setCurrentText(f"{percent_val}%")
                self.zoomCombo.blockSignals(False)

    def onTabChanged(self, index: int):
        """Synchronize status bar and combo box display when switching tabs."""
        # QTimer.singleShot diffère la mise à jour pour laisser Qt stabiliser l'IHM
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
        # Dans _createToolBars (sous pageToolBar) :
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

    def closeEvent(self, event):
        """Prompt user confirmation before closing the application window."""
        qm = QMessageBox(self)
        qm.setIcon(QMessageBox.Icon.Question)
        qm.setWindowTitle(_('Exit'))
        qm.setText(_("Are you sure you want to exit the application?"))
        qm.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)

        # Récupération des boutons QPushButton pour changer leur texte
        yes_btn = qm.button(QMessageBox.StandardButton.Yes)
        if yes_btn:
            yes_btn.setText(_("&Yes"))

        no_btn = qm.button(QMessageBox.StandardButton.No)
        if no_btn:
            no_btn.setText(_("&No"))

        ret = qm.exec()

        if ret == QMessageBox.StandardButton.Yes:
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
        # Refresh dynamic counters and active OS
        self.album_metadata["page_count"] = self.tabs.count()
        self.album_metadata["stamp_count"] = self.countTotalStamps()
        self.album_metadata["os"] = f"{platform.system()} {platform.release()}"

        dlg = AlbumInfoDlg(self.album_metadata, self)
        if dlg.exec() == 1:
            self.album_metadata = dlg.get_metadata()

    def undo(self):
        """Annule la dernière action sur la page active."""
        scene = self.getCurrentPageScene()
        if scene and hasattr(scene, "undoStack"):
            scene.undoStack.undo()

    def redo(self):
        """Rétablit la dernière action annulée sur la page active."""
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

        # Instanciation sécurisée avec valeurs de secours
        page = Page(
            self.pageType,
            border=border,
            paper_format=paper_format,
            border_style=border_style,
            margin_size_mm=margin_size,
            margin_position=margin_position
        )

        page.undoStack.cleanChanged.connect(self.renameTabs)
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

        return page

    def clearPageObjects(self):
        """Clear all graphic items on the current active page."""
        qm = QMessageBox(self)
        qm.setIcon(QMessageBox.Icon.Question)
        qm.setWindowTitle(_('Delete all objects'))
        qm.setText(_("Are you sure you want clear the current page?"))
        qm.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)

        # Traduction des boutons
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

        # Traduction des boutons
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

        # Traduction des boutons
        yes_btn = qm.button(QMessageBox.StandardButton.Yes)
        if yes_btn:
            yes_btn.setText(_("&Yes"))

        no_btn = qm.button(QMessageBox.StandardButton.No)
        if no_btn:
            no_btn.setText(_("&No"))

    def newFile(self):
        """Clear existing pages and start a fresh album file."""
        self.album_metadata = {
            "creation_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "author": "",
            "os": f"{platform.system()} {platform.release()}",
            "page_count": 0,
            "stamp_count": 0
        }

        qm = QMessageBox(self)
        qm.setIcon(QMessageBox.Icon.Question)
        qm.setWindowTitle(_('Delete all pages'))
        qm.setText(_("Are you sure you want to delete all the pages?"))
        qm.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)

        # Traduction des boutons
        yes_btn = qm.button(QMessageBox.StandardButton.Yes)
        if yes_btn:
            yes_btn.setText(_("&Yes"))

        no_btn = qm.button(QMessageBox.StandardButton.No)
        if no_btn:
            no_btn.setText(_("&No"))

        ret = qm.exec()

        if ret == QMessageBox.StandardButton.No:
            return

        self.deleteAllPages()
        self.newPage(None, True)

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
        """Open and deserialize a compressed (.sta) album XML file."""
        qm = QMessageBox(self)
        qm.setIcon(QMessageBox.Icon.Question)
        qm.setWindowTitle(_("Delete all pages"))
        qm.setText(_("Are you sure you want to delete all the pages?"))
        qm.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)

        # Traduction des boutons
        yes_btn = qm.button(QMessageBox.StandardButton.Yes)
        if yes_btn:
            yes_btn.setText(_("&Yes"))

        no_btn = qm.button(QMessageBox.StandardButton.No)
        if no_btn:
            no_btn.setText(_("&No"))

        ret = qm.exec()

        if ret == QMessageBox.StandardButton.No:
            return

        options = QFileDialog.Option.DontUseNativeDialog

        # Choisir le fichier AVANT d'effacer l'album : un "Annuler" ne doit rien perdre
        fileName, _filter = QFileDialog.getOpenFileName(
            self, _("Open Album file"), "", _("Album Files (*.sta)"), options=options
        )
        if not fileName:
            return

        self.deleteAllPages()

        fileNameArray = fileName.split(".")
        if fileNameArray[len(fileNameArray) - 1] == "sta":
            f = gzip.open(fileName, 'r')
        else:
            f = open(fileName, 'r')

        self.currentAlbumName = fileName
        self.updateStatusFile(fileName)

        mytree = ET.parse(f)
        f.close()
        myroot = mytree.getroot()

        # Read album metadata if present; otherwise initialize default values
        meta_node = myroot.find('metadata')
        if meta_node is not None:
            self.album_metadata = {
                "creation_date": meta_node.findtext("creation_date", ""),
                "author": meta_node.findtext("author", ""),
                "os": meta_node.findtext("os", f"{platform.system()} {platform.release()}"),
                "page_count": int(meta_node.findtext("page_count", str(self.tabs.count()))),
                "stamp_count": int(meta_node.findtext("stamp_count", "0"))
            }
        else:
            self.album_metadata = {
                "creation_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "author": "",
                "os": f"{platform.system()} {platform.release()}",
                "page_count": 0,
                "stamp_count": 0
            }

        file_version = myroot.attrib.get("version", "0.9")
        print(file_version)
        self.openNewAlbumFileVersion(myroot)
        # self.openOldAlbumFileVersion(myroot)

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
                item.setTextWidth(200)
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

            # --- Restore Stamp Groups (INDENTÉ AU NIVEAU DE LA PAGE) ---
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

    def saveAlbumToFile(self):
        """Serialize album structure into a gzip-compressed XML file (.sta)."""
        options = QFileDialog.Option.DontUseNativeDialog
        fileName, _filter = QFileDialog.getSaveFileName(
            self, _("Save Album"), "", _("Album Files (*.sta)"), options=options
        )
        if fileName:
            if fileName.find(".") != -1:
                fileNameArray = fileName.split(".")
                if fileNameArray[len(fileNameArray) - 1] == "sta":
                    fileName = fileName.rsplit('.', maxsplit=1)[0]
        else:
            return

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

        # --- NOUVEAU : Marquer toutes les pages comme "propres" (sauvegardées) ---
        for x in range(self.tabs.count()):
            widget = self.tabs.widget(x)
            if hasattr(widget, 'view') and widget.view and widget.view.scene():
                widget.view.scene().undoStack.setClean()

        self.renameTabs()

    def printAllPagesPDF(self):
        """Export all album pages into a single PDF document."""
        scenes = self._allScenes()
        if not scenes:
            return

        # Sans nom d'album, demander où enregistrer (sinon le PDF s'appelait ".pdf")
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
        """Liste des scènes de toutes les pages, sans changer l'onglet affiché."""
        scenes = []
        for i in range(self.tabs.count()):
            widget = self.tabs.widget(i)
            if hasattr(widget, 'view') and widget.view and widget.view.scene():
                scenes.append(widget.view.scene())
        return scenes

    def _renderScenes(self, printer, scenes):
        """
        Rend plusieurs pages dans un même document : chaque page reçoit son propre
        format (A4/Letter) et sa propre orientation AVANT d'être dessinée.
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
        """Ouvre le dialogue de création d'un timbre libre et l'ajoute sur la page active."""
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
        # Ouvre le PDF avec le lecteur par défaut (Windows, macOS et Linux)
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
                # Restaure le fond blanc de la page lorsque l'on désactive la grille
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
        # Une image vide (photo introuvable) ne doit pas faire planter la sauvegarde
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
        """Déclenche la mise en page harmonieuse sur la page courante."""
        scene = self.getCurrentPageScene()
        if scene and hasattr(scene, "autoArrangeStamps"):
            scene.autoArrangeStamps()

    def openThumbnails(self):
        """Ouvre la planche contact pour réorganiser visuellement les pages."""
        from ThumbnailsDlg import ThumbnailsDlg
        dlg = ThumbnailsDlg(self.tabs, self)

        if dlg.exec() == 1:
            new_order = dlg.get_new_order()

            # Vérifier si l'ordre a vraiment changé pour éviter de tout recharger inutilement
            if new_order == list(range(self.tabs.count())):
                return

            # Mettre en cache tous les widgets (pages) existants
            widgets = [self.tabs.widget(i) for i in range(self.tabs.count())]

            # On efface les onglets et on les recrée dans le nouvel ordre
            self.tabs.blockSignals(True)
            self.tabs.clear()

            for original_index in new_order:
                self.tabs.addTab(widgets[original_index], "")  # Le nom sera mis par renameTabs

            self.tabs.blockSignals(False)

            # Renommer "Page 1", "Page 2" proprement
            self.renameTabs()

            # Afficher la première page par défaut après la réorganisation
            if self.tabs.count() > 0:
                self.tabs.setCurrentIndex(0)

    def changeBorderCurrentPage(self):
        """Ouvre le dialogue et modifie la bordure de la page courante."""
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
        """Ouvre le dialogue et modifie la bordure de TOUTES les pages de l'album."""
        if self.tabs.count() == 0: return

        # On repère le style de la page actuelle par défaut
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

            # Retenir l'index de la page actuellement affichée pour y revenir
            current_index = self.tabs.currentIndex()

            # On applique à chaque onglet
            for i in range(self.tabs.count()):
                self.tabs.setCurrentIndex(i)
                scene = self.getCurrentPageScene()
                if scene:
                    scene.replaceBorder(new_style)

            # Restaurer l'affichage de l'onglet de départ
            self.tabs.setCurrentIndex(current_index)

    def importAlbumEasy(self):
        """Lit un fichier texte AlbumEasy et génère les pages correspondantes."""
        options = QFileDialog.Option.DontUseNativeDialog
        fileName, _filter = QFileDialog.getOpenFileName(
            self, _("Import from AlbumEasy"), "", "AlbumEasy Files (*.txt);;All Files (*)", options=options
        )
        if not fileName:
            return

        # Demander s'il faut nettoyer l'album existant
        qm = QMessageBox()
        ret = qm.question(self, _('Import AlbumEasy'),
                          _("Do you want to replace the actual album ?\n(Choose 'No' to append it)"),
                          qm.StandardButton.Yes | qm.StandardButton.No)
        if ret == qm.StandardButton.Yes:
            self.deleteAllPages()

        # --- Variables d'état pour simuler le comportement d'AlbumEasy ---
        current_page = None

        page_width_mm = 210.0  # Par défaut A4, sera mis à jour par ALBUM_PAGES_SIZE
        page_margin_top = 15.0

        current_row_y_mm = page_margin_top
        current_x_mm = 20.0
        row_spacing_mm = 5.0

        global_page_title = ""

        def mm_to_px(mm):
            """Convertit les millimètres d'AlbumEasy en pixels d'écran pour PyQt."""
            return float(mm) / (25.4 / 96.0)

        # Expression régulière pour extraire le texte entre guillemets OU les mots sans espace
        arg_pattern = re.compile(r'"([^"]*)"|(\S+)')

        # Expression régulière pour extraire uniquement les nombres flottants/entiers d'une chaîne
        def extract_floats(args_list):
            floats = []
            for arg in args_list:
                # Cherche les motifs qui ressemblent à des nombres (ex: 25.0, 15, -6.0)
                matches = re.findall(r'-?\d+\.?\d*', str(arg))
                for m in matches:
                    try:
                        floats.append(float(m))
                    except ValueError:
                        pass
            return floats

        multiline_buffer = ""

        try:
            with open(fileName, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    line = line.strip()

                    # Ignorer les commentaires complets ou les parties après le '#'
                    if '#' in line:
                        line = line.split('#')[0].strip()

                    if not line:
                        continue

                    # Gestion des lignes qui se terminent par \ (multilignes)
                    if line.endswith('\\'):
                        multiline_buffer += line[:-1]
                        continue
                    else:
                        line = multiline_buffer + line
                        multiline_buffer = ""

                    # Extraction de la commande principale ex: PAGE_START () ou COLOUR_PAGE_TEXT(red)
                    match = re.match(r'^([A-Z_0-9]+)\s*(?:\((.*)\))?', line)
                    if match:
                        cmd = match.group(1)
                        args_str = match.group(2) if match.group(2) else ""

                        # Extraction des arguments via regex
                        args = []
                        for arg_match in arg_pattern.finditer(args_str):
                            val = arg_match.group(1) if arg_match.group(1) is not None else arg_match.group(2)
                            val = val.replace('\\n', '\n')
                            args.append(val)

                        # --- TRAITEMENT DES COMMANDES ---

                        # 1. PARAMÈTRES GLOBAUX
                        if cmd == "ALBUM_PAGES_SIZE":
                            nums = extract_floats(args)
                            if len(nums) >= 1:
                                page_width_mm = nums[0]

                        elif cmd == "ALBUM_PAGES_TITLE":
                            # Le dernier argument texte est généralement le titre
                            text_args = [a for a in args if not re.match(r'^-?\d+\.?\d*$', a)]
                            if text_args:
                                global_page_title = text_args[-1]

                        # 2. NOUVELLE PAGE
                        elif cmd == "PAGE_START":
                            self.newPage("portrait", True)
                            current_page = self.getCurrentPageScene()
                            current_row_y_mm = page_margin_top

                            if global_page_title and current_page:
                                font = QFont("Arial", 16, QFont.Weight.Bold)
                                x_px = mm_to_px(page_width_mm / 2.0)
                                current_page.addTextLabel(global_page_title, x_px - 50, mm_to_px(current_row_y_mm),
                                                          font, Qt.AlignmentFlag.AlignCenter)
                                current_row_y_mm += 15.0

                        # 3. TEXTES FLOTTANTS
                        elif cmd in ["PAGE_TEXT", "PAGE_TEXT_CENTRE"] and current_page:
                            nums = extract_floats(args)
                            font_size = int(nums[0]) if nums else 10

                            # Le texte est généralement le seul argument non-numérique ou le dernier
                            text = ""
                            for a in reversed(args):
                                if not re.match(r'^[A-Z0-9_\.]+$', a):
                                    text = a
                                    break

                            if text:
                                font = QFont("Arial", font_size)
                                x_px = mm_to_px(page_width_mm / 2.0)
                                y_px = mm_to_px(current_row_y_mm)

                                current_page.addTextLabel(text, x_px - 50, y_px, font, Qt.AlignmentFlag.AlignCenter)
                                text_lines = text.count('\n') + 1
                                current_row_y_mm += (font_size * 0.35 * text_lines) + 5.0

                        # 3b. ESPACEMENT VERTICAL EXPLICITE
                        elif cmd == "PAGE_VSPACE" and current_page:
                            nums = extract_floats(args)
                            if nums:
                                current_row_y_mm += nums[0]

                        # 4. PRÉPARATION D'UNE RANGÉE DE TIMBRES
                        elif cmd in ["ROW_START_FS", "ROW_START_JS", "ROW_START"] and current_page:
                            nums = extract_floats(args)
                            if len(nums) >= 3:
                                espacement_y = nums[-3]
                                row_spacing_mm = nums[-2]
                                current_x_mm = nums[-1]
                                current_row_y_mm += espacement_y
                            elif len(nums) == 2:
                                row_spacing_mm = nums[0]
                                current_x_mm = nums[1]

                        # 5. AJOUT D'UN TIMBRE OU IMAGE
                        elif cmd in ["STAMP_ADD", "STAMP_ADD_IMG"] and current_page:
                            nums = extract_floats(args)
                            if len(nums) >= 2:
                                w_mm = nums[0]
                                h_mm = nums[1]

                                # Filtrer les arguments purement textuels pour remplir les cases
                                text_args = [a for a in args[2:] if not a.replace('.', '', 1).isdigit()]

                                text_center = text_args[0] if len(text_args) > 0 else ""
                                text_top = text_args[1] if len(text_args) > 1 else ""
                                text_bot = text_args[2] if len(text_args) > 2 else ""
                                value = text_args[3] if len(text_args) > 3 else ""

                                if not text_top:
                                    text_top = text_center

                                pixmap = QPixmap(int(mm_to_px(w_mm)), int(mm_to_px(h_mm)))
                                pixmap.fill(Qt.GlobalColor.transparent)

                                stamp_obj = Stamp()
                                stamp_obj.createStampPix(
                                    current_page,
                                    text_top,
                                    value,
                                    text_bot,
                                    mm_to_px(w_mm),
                                    mm_to_px(h_mm),
                                    mm_to_px(current_x_mm),
                                    mm_to_px(current_row_y_mm),
                                    pixmap
                                )

                                current_x_mm += w_mm + row_spacing_mm

        except Exception as e:
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, _("Import Error"), f"An error just happened :\n{str(e)}")

    def renameTabs(self, *args):
        """Renomme séquentiellement tous les onglets, avec une étoile si modifiés."""
        self.tabs.blockSignals(True)
        for i in range(self.tabs.count()):
            widget = self.tabs.widget(i)
            prefix = ""

            # Vérifier si la page a des modifications non sauvegardées
            if hasattr(widget, 'view') and widget.view and widget.view.scene():
                if not widget.view.scene().undoStack.isClean():
                    prefix = "*"

            self.tabs.setTabText(i, f"{prefix}Page {i + 1}")
        self.tabs.blockSignals(False)