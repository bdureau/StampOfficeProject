"""
Rich Text Stamp Dialog Module
-----------------------------
Dialog window allowing creation and live editing of rich text stamps
with dedicated format editors for title, number, and nominal value.

Author: Boris du Reau
"""
import sys
import gettext
from PyQt6 import QtGui
from pathlib import Path
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import (
    QIcon, QPixmap, QFont, QDragEnterEvent, QDropEvent,
    QTextBlockFormat, QTextCharFormat
)
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel,
    QLineEdit, QListWidget, QPushButton, QDialogButtonBox,
    QFileDialog, QMessageBox, QFontComboBox, QSpinBox,
    QToolButton, QTextEdit, QGroupBox, QColorDialog
)

from SpellHighlighter import SpellHighlighter
from Databases import DB
from SAAppPaths import get_images_dir, get_config_value, list_countries
from Stamp import RichTextStamp
from AppLanguage import get_language

# Setup gettext localization
gettext.find("RichTextStampDlg")
translate = gettext.translation('RichTextStampDlg', localedir='locale', languages=[get_language()], fallback=True)
translate.install()
_ = translate.gettext


class DropImageLabel(QLabel):
    """Custom QLabel supporting image file drag and drop operations."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.parent_dialog = parent

    def dragEnterEvent(self, event: QDragEnterEvent):
        """Accept drag event if it contains supported local image URLs."""
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                ext = Path(url.toLocalFile()).suffix.lower()
                if ext in [".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp"]:
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dropEvent(self, event: QDropEvent):
        """Extract dropped image path and pass it to the dialog."""
        for url in event.mimeData().urls():
            file_path = url.toLocalFile()
            if file_path and self.parent_dialog is not None:
                self.parent_dialog.set_image_from_path(file_path)
                event.acceptProposedAction()
                return
        event.ignore()


class RichTextEditorWidget(QGroupBox):
    """Reusable mini rich-text editor widget featuring formatting controls and live preview."""

    def __init__(self, title: str, default_font_size: int = 10, editor_height: int = 60, language: str = "fr",parent=None):
        super().__init__(title, parent)
        self.default_font_size = default_font_size
        self.editor_height = editor_height
        self.language = language
        self._create_ui()

    def _get_icon(self, icon_name: str) -> QIcon:
        """Dynamically load icon asset from application Images directory."""
        images_dir = get_images_dir()
        icon_path = images_dir / icon_name
        if icon_path.exists():
            return QIcon(str(icon_path))
        return QIcon(f"../Images/{icon_name}")

    def _create_ui(self):
        vbox = QVBoxLayout(self)
        vbox.setContentsMargins(6, 6, 6, 6)
        vbox.setSpacing(4)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(2)

        # Font family combo
        self.font_combo = QFontComboBox()
        self.font_combo.setMaximumWidth(140)
        default_font_name = get_config_value('default font', 'Arial')
        self.font_combo.setCurrentFont(QFont(default_font_name))
        self.font_combo.currentFontChanged.connect(self._set_font_family)
        toolbar.addWidget(self.font_combo)

        # Font size spin box
        self.size_spin = QSpinBox()
        self.size_spin.setRange(6, 72)
        self.size_spin.setValue(self.default_font_size)
        self.size_spin.setMaximumWidth(50)
        self.size_spin.valueChanged.connect(self._set_font_size)
        toolbar.addWidget(self.size_spin)

        # Bold button
        self.btn_bold = QToolButton()
        self.btn_bold.setText("B")
        self.btn_bold.setCheckable(True)
        self.btn_bold.setStyleSheet("font-weight: bold;")
        self.btn_bold.clicked.connect(self._toggle_bold)
        toolbar.addWidget(self.btn_bold)

        # Italic button
        self.btn_italic = QToolButton()
        self.btn_italic.setText("I")
        self.btn_italic.setCheckable(True)
        self.btn_italic.setStyleSheet("font-style: italic;")
        self.btn_italic.clicked.connect(self._toggle_italic)
        toolbar.addWidget(self.btn_italic)

        # Underline button
        self.btn_underline = QToolButton()
        self.btn_underline.setText("U")
        self.btn_underline.setCheckable(True)
        self.btn_underline.setStyleSheet("text-decoration: underline;")
        self.btn_underline.clicked.connect(self._toggle_underline)
        toolbar.addWidget(self.btn_underline)

        # Color picker button
        self.btn_color = QToolButton()
        self.btn_color.setText("🎨")
        self.btn_color.setToolTip(_("Text Color"))
        self.btn_color.clicked.connect(self._choose_color)
        toolbar.addWidget(self.btn_color)

        # Alignment buttons
        self.btn_align_left = QToolButton()
        self.btn_align_left.setIcon(self._get_icon("justify left.png"))
        self.btn_align_left.setIconSize(QSize(16, 16))
        self.btn_align_left.clicked.connect(lambda: self._set_alignment(Qt.AlignmentFlag.AlignLeft))
        toolbar.addWidget(self.btn_align_left)

        self.btn_align_center = QToolButton()
        self.btn_align_center.setIcon(self._get_icon("justify center.png"))
        self.btn_align_center.setIconSize(QSize(16, 16))
        self.btn_align_center.clicked.connect(lambda: self._set_alignment(Qt.AlignmentFlag.AlignCenter))
        toolbar.addWidget(self.btn_align_center)

        self.btn_align_right = QToolButton()
        self.btn_align_right.setIcon(self._get_icon("justify right.png"))
        self.btn_align_right.setIconSize(QSize(16, 16))
        self.btn_align_right.clicked.connect(lambda: self._set_alignment(Qt.AlignmentFlag.AlignRight))
        toolbar.addWidget(self.btn_align_right)

        toolbar.addStretch()
        vbox.addLayout(toolbar)

        # Rich text editor area
        self.editor = QTextEdit()
        self.editor.setFixedHeight(self.editor_height)
        self.editor.setFontFamily(default_font_name)
        self.editor.setFontPointSize(float(self.default_font_size))
        self.editor.cursorPositionChanged.connect(self._update_format_controls)
        vbox.addWidget(self.editor)

        # Attachement du correcteur en direct
        self.highlighter = SpellHighlighter(self.editor.document(), language=self.language)

    def set_language(self, lang: str):
        self.language = lang
        if hasattr(self, "highlighter") and self.highlighter:
            self.highlighter.set_language(lang)

    def _set_font_family(self, font):
        fmt = QTextCharFormat()
        fmt.setFontFamily(font.family())
        self._apply_char_format(fmt)

    def _set_font_size(self, size):
        fmt = QTextCharFormat()
        fmt.setFontPointSize(float(size))
        self._apply_char_format(fmt)

    def _toggle_bold(self):
        fmt = QTextCharFormat()
        fmt.setFontWeight(QFont.Weight.Bold if self.btn_bold.isChecked() else QFont.Weight.Normal)
        self._apply_char_format(fmt)

    def _toggle_italic(self):
        fmt = QTextCharFormat()
        fmt.setFontItalic(self.btn_italic.isChecked())
        self._apply_char_format(fmt)

    def _toggle_underline(self):
        fmt = QTextCharFormat()
        fmt.setFontUnderline(self.btn_underline.isChecked())
        self._apply_char_format(fmt)

    def _choose_color(self):
        color = QColorDialog.getColor(self.editor.textColor(), self, _("Select Text Color"))
        if color.isValid():
            fmt = QTextCharFormat()
            fmt.setForeground(color)
            self._apply_char_format(fmt)

    def _set_alignment(self, align_flag):
        block_fmt = QTextBlockFormat()
        block_fmt.setAlignment(align_flag)
        self.editor.textCursor().mergeBlockFormat(block_fmt)

    def _apply_char_format(self, fmt):
        cursor = self.editor.textCursor()
        if not cursor.hasSelection():
            cursor.select(cursor.SelectionType.WordUnderCursor)
        cursor.mergeCharFormat(fmt)
        self.editor.mergeCurrentCharFormat(fmt)

    def _update_format_controls(self):
        fmt = self.editor.currentCharFormat()
        if fmt.fontFamily():
            self.font_combo.blockSignals(True)
            self.font_combo.setCurrentFont(QFont(fmt.fontFamily()))
            self.font_combo.blockSignals(False)

        if fmt.fontPointSize() > 0:
            self.size_spin.blockSignals(True)
            self.size_spin.setValue(int(fmt.fontPointSize()))
            self.size_spin.blockSignals(False)

        self.btn_bold.setChecked(fmt.fontWeight() == QFont.Weight.Bold)
        self.btn_italic.setChecked(fmt.fontItalic())
        self.btn_underline.setChecked(fmt.fontUnderline())

    def set_html(self, html_text: str):
        self.editor.blockSignals(True)
        self.editor.setHtml(html_text)
        self.editor.blockSignals(False)

    def get_html(self) -> str:
        return self.editor.toHtml()


class RichTextStampDlg(QDialog):
    """Dialog allowing custom stamp creation or editing with live rich text formatting."""

    def __init__(self, scene=None, stampItem=None, parent=None):
        super().__init__(parent)
        self.scene = scene
        self.stampItem = stampItem
        self.is_edit = (stampItem is not None)

        self.setWindowTitle(_("Edit Rich Text Stamp") if self.is_edit else _("Create Rich Text Stamp"))
        self.setWindowIcon(QIcon(str(get_images_dir() / "stamp_book.png")))
        self.resize(800, 560)

        self.base_dir = self._get_app_dir()
        self.images_dir = self._get_resource_dir("Images")

        icon_path = self.images_dir / "stamp_book.png"
        if icon_path.exists():
            self.setWindowIcon(QtGui.QIcon(str(icon_path)))
        else:
            self.setWindowIcon(QtGui.QIcon('stamp_book.png'))

        self.db = None
        self.customPixmap = QPixmap()
        self.fullPhotoPath = None

        self._init_db()
        self._create_ui()

        if self.is_edit:
            self._load_existing_stamp()

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
        """Initialize connection to master database to load mount box sizes."""
        countries = list_countries()
        if countries:
            try:
                self.db = DB(countries[0])
            except Exception as e:
                print(f"Database error loading mount boxes: {e}")
                self.db = None

    def _create_ui(self):
        # 1. Left column: Mount boxes from database
        vbox_pochettes = QVBoxLayout()
        vbox_pochettes.addWidget(QLabel(_("Pochette type:")))
        self.pochetteList = QListWidget()
        self.pochetteList.setMaximumWidth(150)
        self.pochetteList.itemClicked.connect(self._on_pochette_selected)
        vbox_pochettes.addWidget(self.pochetteList)

        if self.db is not None:
            boxes = self.db.loadBoxList()
            self.pochetteList.addItems(boxes)
            if self.pochetteList.count() > 0:
                self.pochetteList.setCurrentRow(0)

        # 2. Center column: Image preview with Drag and Drop and dimension inputs
        vbox_image = QVBoxLayout()
        vbox_image.addWidget(QLabel(_("Picture:")))

        self.photoLabel = DropImageLabel(self)
        self.photoLabel.setFixedSize(180, 180)
        self.photoLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.photoLabel.setText(_("Drop image here"))
        self.photoLabel.setStyleSheet("border: 2px dashed #888; background: #fafafa; color: #666; font-size: 11px;")
        vbox_image.addWidget(self.photoLabel)

        btn_load_img = QPushButton(_("&Browse picture..."))
        btn_load_img.clicked.connect(self._load_image)
        vbox_image.addWidget(btn_load_img)

        # Dimensions in mm
        form_dims = QFormLayout()
        self.eWidth = QLineEdit()
        self.eWidth.setMaximumWidth(80)
        self.eHeight = QLineEdit()
        self.eHeight.setMaximumWidth(80)
        form_dims.addRow(_("Width (mm):"), self.eWidth)
        form_dims.addRow(_("Height (mm):"), self.eHeight)
        vbox_image.addLayout(form_dims)
        vbox_image.addStretch()

        # 3. Right column: Three dedicated live rich-text editors
        vbox_texts = QVBoxLayout()
        lang = getattr(self.scene, "album_language", "fr") if self.scene else "fr"
        self.editor_desc = RichTextEditorWidget(_("Description (Title)"), default_font_size=10, editor_height=65)
        self.editor_nbr = RichTextEditorWidget(_("Stamp Number"), default_font_size=8, editor_height=45)
        self.editor_val = RichTextEditorWidget(_("Nominal Value"), default_font_size=8, editor_height=45)

        vbox_texts.addWidget(self.editor_desc)
        vbox_texts.addWidget(self.editor_nbr)
        vbox_texts.addWidget(self.editor_val)

        # Main columns layout
        h_all = QHBoxLayout()
        h_all.addLayout(vbox_pochettes)
        h_all.addLayout(vbox_image)
        h_all.addLayout(vbox_texts)

        # Dialog action buttons
        btn_action = QPushButton(_("&Apply") if self.is_edit else _("&Create"))
        btn_action.setDefault(True)
        btn_action.clicked.connect(self._on_action_clicked)

        btn_close = QPushButton(_("&Cancel") if self.is_edit else _("&Done"))
        btn_close.clicked.connect(self.reject)

        bb = QDialogButtonBox(Qt.Orientation.Horizontal)
        bb.addButton(btn_action, QDialogButtonBox.ButtonRole.ActionRole)
        bb.addButton(btn_close, QDialogButtonBox.ButtonRole.ActionRole)

        main_layout = QVBoxLayout(self)
        main_layout.addLayout(h_all)
        main_layout.addWidget(bb)

        if not self.is_edit:
            self._sync_dimensions_from_list()

    def _sync_dimensions_from_list(self):
        """Update width and height inputs based on selected mount box."""
        item = self.pochetteList.currentItem()
        if item and self.db is not None:
            box_info = self.db.getCurrentBox(item.text())
            if len(box_info) >= 2:
                self.eWidth.setText(str(box_info[0]))
                self.eHeight.setText(str(box_info[1]))

    def _on_pochette_selected(self, item):
        self._sync_dimensions_from_list()

    def _select_pochette_by_size(self, target_w: float, target_h: float):
        """Find and select the mount box in the list that matches the given dimensions."""
        if not self.db or self.pochetteList.count() == 0:
            return

        # 1. Quick match based on standard naming convention: "Pochette WxH"
        # Handles both integer formats (e.g. 25x30) and float representations
        w_int = int(target_w) if float(target_w).is_integer() else target_w
        h_int = int(target_h) if float(target_h).is_integer() else target_h
        target_name = f"Pochette {w_int}x{h_int}"

        matched_items = self.pochetteList.findItems(target_name, Qt.MatchFlag.MatchExactly)
        if matched_items:
            self.pochetteList.blockSignals(True)
            self.pochetteList.setCurrentItem(matched_items[0])
            self.pochetteList.blockSignals(False)
            return

        # 2. Fallback: inspect actual dimensions of each box via database lookup
        for row in range(self.pochetteList.count()):
            item = self.pochetteList.item(row)
            box_info = self.db.getCurrentBox(item.text())
            if len(box_info) >= 2:
                try:
                    db_w = float(box_info[0])
                    db_h = float(box_info[1])
                    if abs(db_w - float(target_w)) < 0.1 and abs(db_h - float(target_h)) < 0.1:
                        self.pochetteList.blockSignals(True)
                        self.pochetteList.setCurrentItem(item)
                        self.pochetteList.blockSignals(False)
                        return
                except (ValueError, TypeError):
                    continue

    def _load_existing_stamp(self):
        """Populate editors and image with current rich text stamp data."""
        stamp_helper = RichTextStamp()
        data = stamp_helper.readRichStamp(self.stampItem)

        self.editor_desc.set_html(data.get('stampDesc_html', ''))
        self.editor_nbr.set_html(data.get('stampNbr_html', ''))
        self.editor_val.set_html(data.get('stampValue_html', ''))

        # self.eWidth.setText(str(data.get('stampBox_boxWidth', 25.0)))
        # self.eHeight.setText(str(data.get('stampBox_boxHeight', 30.0)))
        box_w = data.get('stampBox_boxWidth', 25.0)
        box_h = data.get('stampBox_boxHeight', 30.0)

        self.eWidth.setText(str(box_w))
        self.eHeight.setText(str(box_h))

        # Synchronize and select the matching mount box item in pochetteList
        self._select_pochette_by_size(box_w, box_h)

        pix = data.get('pixmapItem_image')
        if isinstance(pix, QPixmap) and not pix.isNull():
            self.customPixmap = pix
            self.photoLabel.setText("")
            if pix.width() > pix.height():
                self.photoLabel.setPixmap(pix.scaledToWidth(180, Qt.TransformationMode.SmoothTransformation))
            else:
                self.photoLabel.setPixmap(pix.scaledToHeight(180, Qt.TransformationMode.SmoothTransformation))

    def set_image_from_path(self, file_path: str):
        """Load image file and display preview thumbnail."""
        pix = QPixmap(file_path)
        if not pix.isNull():
            self.customPixmap = pix
            self.fullPhotoPath = file_path
            self.photoLabel.setText("")
            if pix.width() > pix.height():
                self.photoLabel.setPixmap(pix.scaledToWidth(180, Qt.TransformationMode.SmoothTransformation))
            else:
                self.photoLabel.setPixmap(pix.scaledToHeight(180, Qt.TransformationMode.SmoothTransformation))

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

    def _on_action_clicked(self):
        """Validate inputs and create or update the RichTextStamp group."""
        try:
            width_mm = float(self.eWidth.text().replace(",", "."))
            height_mm = float(self.eHeight.text().replace(",", "."))
            if width_mm <= 0 or height_mm <= 0:
                raise ValueError
        except ValueError:
            QMessageBox.warning(self, _("Invalid size"), _("Width and height must be positive numbers (mm)."))
            return

        desc_html = self.editor_desc.get_html()
        nbr_html = self.editor_nbr.get_html()
        val_html = self.editor_val.get_html()

        stamp_helper = RichTextStamp()

        if self.is_edit and self.stampItem is not None:
            stamp_helper.updateRichStamp(
                self.stampItem,
                self.scene,
                nbr_html=nbr_html,
                value_html=val_html,
                desc_html=desc_html,
                boxWidth=width_mm,
                boxHeight=height_mm,
                pixmap=self.customPixmap
            )
        else:
            stamp_helper.createRichStampPix(
                self.scene,
                nbr_html=nbr_html,
                value_html=val_html,
                desc_html=desc_html,
                boxWidth=width_mm,
                boxHeight=height_mm,
                x=50.0,
                y=50.0,
                pixmap=self.customPixmap
            )

        self.accept()