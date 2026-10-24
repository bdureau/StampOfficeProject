"""
Custom Stamp Dialog Module
--------------------------
Dialog window allowing the creation of custom stamps without database lookup,
with support for database mount box sizes, drag-and-drop, and custom image loading.

Author: Boris du Reau
"""

import sys
from pathlib import Path
import gettext
from pathlib import Path
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon, QPixmap, QDragEnterEvent, QDropEvent
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel,
    QLineEdit, QPlainTextEdit, QListWidget, QPushButton,
    QDialogButtonBox, QFileDialog, QMessageBox
)

from Databases import DB
from SAAppPaths import get_images_dir, list_countries
from Stamp import Stamp
from AppLanguage import get_language

gettext.find("CustomStampDlg")
translate = gettext.translation('CustomStampDlg', localedir='locale', languages=[get_language()], fallback=True)
translate.install()
_ = translate.gettext


class DropImageLabel(QLabel):
    """Custom QLabel that supports image file drag and drop operations."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.parent_dialog = parent

    def dragEnterEvent(self, event: QDragEnterEvent):
        """Accept drag event if it contains local image file URLs."""
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                ext = Path(url.toLocalFile()).suffix.lower()
                if ext in [".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp"]:
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dropEvent(self, event: QDropEvent):
        """Handle dropped image file and pass it to the dialog."""
        for url in event.mimeData().urls():
            file_path = url.toLocalFile()
            if file_path and self.parent_dialog is not None:
                self.parent_dialog.set_image_from_path(file_path)
                event.acceptProposedAction()
                return
        event.ignore()

class CustomStampDlg(QDialog):
    """Dialog allowing custom stamp creation independent of catalog databases."""

    def __init__(self, scene=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(_("Create Custom Stamp"))

        #self.setWindowIcon(QIcon(str(get_images_dir() / "stamp_book.png")))

        self.base_dir = self._get_app_dir()
        self.images_dir = self._get_resource_dir("Images")

        icon_path = self.images_dir / "stamp_book.png"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))
        else:
            self.setWindowIcon(QIcon('stamp_book.png'))

        self.scene = scene
        self.db = None
        self.customPixmap = QPixmap()
        self.fullPhotoPath = None

        self._init_db()
        self._create_ui()

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

    def _init_db(self):
        """Initialize connection to master database to load stamp mount box list."""
        countries = list_countries()
        if countries:
            try:
                self.db = DB(countries[0])
            except Exception as e:
                print(f"Database error loading mount boxes: {e}")
                self.db = None

    def _create_ui(self):
        # 1. Left column: Mount box size list loaded from database
        vbox_pochettes = QVBoxLayout()
        vbox_pochettes.addWidget(QLabel(_("Pochette type:")))
        self.pochetteList = QListWidget()
        self.pochetteList.setMaximumWidth(160)
        self.pochetteList.itemClicked.connect(self._on_pochette_selected)
        vbox_pochettes.addWidget(self.pochetteList)

        if self.db is not None:
            boxes = self.db.loadBoxList()
            self.pochetteList.addItems(boxes)
            if self.pochetteList.count() > 0:
                self.pochetteList.setCurrentRow(0)

        # 2. Center column: Image preview with drag-and-drop capability and browse button
        vbox_image = QVBoxLayout()
        vbox_image.addWidget(QLabel(_("Picture:")))

        self.photoLabel = DropImageLabel(self)
        self.photoLabel.setFixedSize(200, 200)
        self.photoLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.photoLabel.setText(_("Drop image here"))
        self.photoLabel.setWordWrap(True)
        self.photoLabel.setStyleSheet(
            "border: 2px dashed #888; background: #fafafa; color: #666; font-size: 11px;"
        )
        vbox_image.addWidget(self.photoLabel)

        btn_load_img = QPushButton(_("&Browse picture..."))
        btn_load_img.clicked.connect(self._load_image)
        vbox_image.addWidget(btn_load_img)
        vbox_image.addStretch()

        # 3. Right column: Stamp attributes form
        form = QFormLayout()

        self.eTitle = QPlainTextEdit()
        self.eTitle.setFixedHeight(50)
        form.addRow(_("Description (Title):"), self.eTitle)

        self.eNbr = QLineEdit()
        form.addRow(_("Stamp nbr:"), self.eNbr)

        self.eValue = QLineEdit()
        form.addRow(_("Value:"), self.eValue)

        self.eWidth = QLineEdit()
        self.eWidth.setMaximumWidth(100)
        form.addRow(_("Width (mm):"), self.eWidth)

        self.eHeight = QLineEdit()
        self.eHeight.setMaximumWidth(100)
        form.addRow(_("Height (mm):"), self.eHeight)

        # Initialize dimension fields from default selected mount box
        self._sync_dimensions_from_list()

        # Assemble columns horizontally
        h_layout = QHBoxLayout()
        h_layout.addLayout(vbox_pochettes)
        h_layout.addLayout(vbox_image)
        h_layout.addLayout(form)

        # Dialog action buttons
        btn_create = QPushButton(_("&Create"))
        btn_create.setDefault(True)
        btn_create.clicked.connect(self._create_stamp)

        btn_close = QPushButton(_("&Done"))
        btn_close.clicked.connect(self.reject)

        bb = QDialogButtonBox(Qt.Orientation.Horizontal)
        bb.addButton(btn_create, QDialogButtonBox.ButtonRole.ActionRole)
        bb.addButton(btn_close, QDialogButtonBox.ButtonRole.ActionRole)

        main_layout = QVBoxLayout(self)
        main_layout.addLayout(h_layout)
        main_layout.addWidget(bb)

    def _sync_dimensions_from_list(self):
        """Update width and height inputs based on active mount box selection."""
        item = self.pochetteList.currentItem()
        if item and self.db is not None:
            box_info = self.db.getCurrentBox(item.text())
            if len(box_info) >= 2:
                self.eWidth.setText(str(box_info[0]))
                self.eHeight.setText(str(box_info[1]))

    def _on_pochette_selected(self, item):
        self._sync_dimensions_from_list()

    def set_image_from_path(self, file_path: str):
        """Load image file, update internal pixmap, and display preview."""
        pix = QPixmap(file_path)
        if not pix.isNull():
            self.customPixmap = pix
            self.fullPhotoPath = file_path
            self.photoLabel.setText("")  # Clear placeholder text
            if pix.width() > pix.height():
                self.photoLabel.setPixmap(pix.scaledToWidth(200, Qt.TransformationMode.SmoothTransformation))
            else:
                self.photoLabel.setPixmap(pix.scaledToHeight(200, Qt.TransformationMode.SmoothTransformation))

    def _load_image(self):
        """Open file dialog for manual image selection."""
        options = QFileDialog.Option.DontUseNativeDialog
        file_name, _filter = QFileDialog.getOpenFileName(
            self, _("Select picture"), "",
            _("All pictures (*.jpg *.jpeg *.png);;PNG (*.png)"),
            options=options
        )
        if file_name:
            self.set_image_from_path(file_name)

    def _create_stamp(self):
        """Instantiate stamp graphic group on target scene with undo support."""
        try:
            width_mm = float(self.eWidth.text().replace(",", "."))
            height_mm = float(self.eHeight.text().replace(",", "."))
            if width_mm <= 0 or height_mm <= 0:
                raise ValueError
        except ValueError:
            QMessageBox.warning(self, _("Invalid size"), _("Width and height must be positive numbers (mm)."))
            return

        desc = self.eTitle.toPlainText()
        nbr = self.eNbr.text().strip()
        value = self.eValue.text().strip()

        # Default placement coordinates on active scene
        x = 50.0
        y = 50.0

        stamp_helper = Stamp()
        stamp_helper.createStampPix(
            self.scene,
            nbr=nbr,
            value=value,
            desc=desc,
            boxWidth=width_mm,
            boxHeight=height_mm,
            x=x,
            y=y,
            pixmap=self.customPixmap
        )
        self.accept()

