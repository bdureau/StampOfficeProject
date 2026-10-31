"""
StampPhoto - Main Application Window
------------------------------------
Photo and stamp viewer and batch resolution converter designed for
collectors and philatelists. Part of the stampOffice suite.

Browses the pictures of a source folder and converts the current picture,
the selected pictures or all of them, to JPG at a low, medium or high
resolution (or all three), into a destination folder. The interface language
(French / English) can be changed while the application runs.

Browsing:
  - the pictures are listed in alphabetical order (natural order: "timbre2"
    before "timbre10", upper/lower case and accents ignored);
  - the name of the current picture is shown under the preview;
  - typing the beginning of a name (pattern) selects every picture whose name
    starts with it; * and ? wildcards may be used ("France_18*_ceres");
  - a panel on the right of the picture shows its file size (KB), format,
    width and height in pixels, resolution (dpi) and estimated size in mm.

Conversion rules:
  - the configured size (low/medium/high) limits the longest side of the
    picture, so portrait and landscape pictures are reduced alike;
  - the EXIF orientation of camera and phone pictures is applied;
  - transparent areas are filled with white (JPG has no transparency);
  - a picture that cannot be read or written is reported, the others are
    still converted;
  - existing files in the destination are only replaced after confirmation,
    and two pictures with the same name (timbre.png, timbre.jpg) produce
    different files.

Author: Boris du Reau
Date: 2026-10-31
"""

import os
import re
import sys
import fnmatch
import gettext
import configparser
import unicodedata
from collections import Counter
from pathlib import Path
from PIL import Image, ImageOps, UnidentifiedImageError

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFileDialog, QMessageBox, QComboBox,
    QProgressBar, QStatusBar, QToolBar, QListWidget, QListWidgetItem, QLineEdit,
    QSplitter, QAbstractItemView, QGroupBox, QFormLayout
)
from PyQt6.QtGui import QAction, QActionGroup, QPixmap, QIcon, QCloseEvent, QImageReader, QDesktopServices
from PyQt6.QtCore import Qt, QLibraryInfo, QLocale, QStandardPaths, QTranslator, QUrl, QItemSelectionModel

from SPAbout import SPAboutDlg
from SPConfig import SPConfigDialog

CONFIG_FILE = "StampPhoto.cfg"
APP_ICON_PNG = "StampPhoto.png"     # in the Images folder (../Images)
APP_ICON_ICO = "StampPhoto.ico"     # next to StampPhoto.py (also used to build the .exe)
APP_USER_MODEL_ID = "stampOffice.StampPhoto"

# Resolution assumed to estimate the size in mm when the file has none, or only
# the 72/96 dpi that cameras and screens write by default (not a scan resolution)
ASSUMED_SCAN_DPI = 300
MIN_REAL_DPI = 100

# User manuals, in the Help folder (../Help)
MANUALS = {
    "fr": "StampPhoto Manuel utilisateur.pdf",
    "en": "StampPhoto User Manual.pdf",
}
VALID_EXTENSIONS = ('.png', '.jpg', '.jpeg', '.bmp', '.tif', '.tiff', '.webp')

# Conversion targets: key, configuration option, default size (px), file name suffix
RESOLUTIONS = [
    ("low", "low_width", "800", "_low"),
    ("med", "medium_width", "1600", "_med"),
    ("high", "high_width", "2400", "_high"),
]

# Folders whose presence identifies the application root folder
_RESOURCE_FOLDERS = ("Images", "locale", "Help", "Photos", "Databases", "docs")


# ============================================================================
# Application paths
# ============================================================================

def get_app_dir() -> Path:
    """Root folder of the application.

    - Executable (sys.frozen): the folder that contains the executable.
    - Python script in a sub-folder: the parent folder when it holds one of the
      resource folders (Images, locale...), otherwise the script folder.
    """
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).resolve().parent
    script_dir = Path(__file__).resolve().parent
    if any((script_dir.parent / folder).is_dir() for folder in _RESOURCE_FOLDERS):
        return script_dir.parent
    return script_dir


def _resource_dir(name: str) -> Path:
    """A resource folder in the application root folder, otherwise next to the script."""
    for candidate in (get_app_dir() / name, Path(__file__).resolve().parent / name):
        if candidate.is_dir():
            return candidate
    return get_app_dir() / name


def get_config_path() -> Path:
    """StampPhoto.cfg in the application folder; in the user's settings folder
    when the application folder is write-protected (e.g. C:\\Program Files)."""
    path = get_app_dir() / CONFIG_FILE
    if os.access(str(path if path.exists() else path.parent), os.W_OK):
        return path
    user_dir = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.GenericConfigLocation))
    user_dir = user_dir / "StampPhoto"
    user_dir.mkdir(parents=True, exist_ok=True)
    return user_dir / CONFIG_FILE


IMAGES_DIR = _resource_dir("Images")
LOCALE_DIR = str(_resource_dir("locale"))


def get_image_icon(filename: str) -> QIcon:
    """Retrieve QIcon from the Images folder if present, otherwise return empty QIcon."""
    icon_path = IMAGES_DIR / filename
    if icon_path.exists():
        return QIcon(str(icon_path))
    return QIcon()


def get_app_icon() -> QIcon:
    """Application icon: StampPhoto.ico (all its sizes, sharp in the title bar and
    the taskbar) completed with Images/StampPhoto.png for the large sizes."""
    icon = QIcon()
    for path in (Path(__file__).resolve().parent / APP_ICON_ICO, get_app_dir() / APP_ICON_ICO,
                 IMAGES_DIR / APP_ICON_PNG):
        if path.is_file():
            icon.addFile(str(path))
    return icon


def set_windows_app_id():
    """On Windows, give the process its own identity so that the taskbar shows
    the StampPhoto icon instead of the Python icon."""
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_USER_MODEL_ID)
        except (AttributeError, OSError):
            pass


_qt_translator = None


def install_qt_translator(lang: str):
    """Load Qt's own translations (Yes / No buttons of the message boxes...)."""
    global _qt_translator
    app = QApplication.instance()
    if app is None:
        return
    if _qt_translator is not None:
        app.removeTranslator(_qt_translator)
        _qt_translator = None
    translator = QTranslator(app)
    if translator.load(QLocale(lang), "qtbase", "_",
                       QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)):
        app.installTranslator(translator)
        _qt_translator = translator


# ============================================================================
# Picture conversion
# ============================================================================

def prepare_rgb(im: Image.Image) -> Image.Image:
    """Picture ready to be saved as JPG: EXIF orientation applied and
    transparent areas filled with white."""
    im = ImageOps.exif_transpose(im)
    if im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info):
        im = im.convert("RGBA")
        background = Image.new("RGB", im.size, (255, 255, 255))
        background.paste(im, mask=im.getchannel("A"))
        return background
    return im.convert("RGB")


def resize_longest_side(im: Image.Image, max_side: int) -> Image.Image:
    """Reduce the picture so that its longest side is at most max_side
    (smaller pictures are not enlarged)."""
    width, height = im.size
    longest = max(width, height)
    if longest <= max_side:
        return im.copy()
    scale = max_side / longest
    new_size = (max(1, round(width * scale)), max(1, round(height * scale)))
    return im.resize(new_size, Image.Resampling.LANCZOS)


# ============================================================================
# Picture information (size, pixels, resolution, size in mm)
# ============================================================================

def _as_float(value):
    try:
        if isinstance(value, tuple):            # (numerator, denominator)
            return float(value[0]) / float(value[1]) if value[1] else None
        return float(value)
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def read_picture_info(path: str) -> dict:
    """File size, format, size in pixels (as displayed, EXIF orientation applied)
    and resolution in dpi (None when the file does not record one).
    Only the header of the file is read, not the whole picture."""
    info = {"bytes": os.path.getsize(path), "format": "", "width": 0, "height": 0, "dpi": None}
    with Image.open(path) as im:
        info["format"] = im.format or os.path.splitext(path)[1].lstrip(".").upper()
        width, height = im.size
        exif = im.getexif()
        if exif.get(0x0112) in (5, 6, 7, 8):     # rotated by 90 degrees: width and height swap
            width, height = height, width
        info["width"], info["height"] = width, height

        dpi = None
        raw = im.info.get("dpi")                 # JPEG (JFIF), PNG (pHYs), TIFF, BMP
        if raw:
            dpi = (_as_float(raw[0]), _as_float(raw[1]))
        elif 0x011A in exif:                     # EXIF XResolution / YResolution
            x, y = _as_float(exif.get(0x011A)), _as_float(exif.get(0x011B, exif.get(0x011A)))
            unit = exif.get(0x0128, 2)           # 2 = inch, 3 = centimetre
            if x and y:
                dpi = (x * 2.54, y * 2.54) if unit == 3 else (x, y)
        if dpi and dpi[0] and dpi[1] and dpi[0] > 1 and dpi[1] > 1:
            if exif.get(0x0112) in (5, 6, 7, 8):
                dpi = (dpi[1], dpi[0])
            info["dpi"] = (round(dpi[0], 1), round(dpi[1], 1))
    return info


def estimated_size_mm(info: dict):
    """(width mm, height mm, dpi used, assumed?) from the pixels and the resolution.
    When the file has no real scan resolution, ASSUMED_SCAN_DPI is used."""
    dpi = info.get("dpi")
    assumed = not dpi or min(dpi) < MIN_REAL_DPI
    dpi_x, dpi_y = (ASSUMED_SCAN_DPI, ASSUMED_SCAN_DPI) if assumed else dpi
    return info["width"] / dpi_x * 25.4, info["height"] / dpi_y * 25.4, (dpi_x, dpi_y), assumed


# ============================================================================
# Names: alphabetical order and pattern search
# ============================================================================

def fold_text(text: str) -> str:
    """Text for comparisons: lower case, without accents ("Élysée" -> "elysee")."""
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def natural_key(name: str):
    """Sort key of the natural alphabetical order: "timbre2" before "timbre10"."""
    return [int(part) if part.isdigit() else part for part in re.split(r"(\d+)", fold_text(name))]


def name_starts_with(name: str, pattern: str) -> bool:
    """True if the file name starts with the pattern (case and accents ignored).
    The pattern may contain the wildcards * (any text) and ? (any character)."""
    pattern = fold_text(pattern.strip())
    if not pattern:
        return False
    name = fold_text(name)
    if any(c in pattern for c in "*?["):
        return fnmatch.fnmatchcase(name, pattern + "*")
    return name.startswith(pattern)


class StampPhotoApp(QMainWindow):
    """Main application window for the StampPhoto tool."""

    def __init__(self):
        super().__init__()
        self.setWindowIcon(get_app_icon())

        self.images = []
        self.current_index = -1
        self.source_dir = ""
        self.dest_dir = ""

        # Picture shown in the preview, kept in memory to rescale it when the
        # window is resized without reading the file again: (path, QPixmap)
        self._pixmap_cache = (None, QPixmap())
        self._picture_info = None

        # Batch conversion state
        self._busy = False
        self._stop_requested = False
        self._close_after_batch = False

        self.config_path = get_config_path()
        self.config = configparser.ConfigParser()
        self._load_config()
        self._setup_translation()

        self._init_ui()
        self.retranslate_ui()

        # If a saved directory exists, automatically load it
        if self.source_dir and os.path.isdir(self.source_dir):
            self._load_images_from_source()

    # ------------------------------------------------------------------ configuration
    def _load_config(self):
        """Initialize default values, then read StampPhoto.cfg."""
        self.config["General"] = {
            "language": "fr",
            "last_source_dir": "",
            "last_dest_dir": "",
            "jpeg_quality": "85"
        }
        self.config["Resolutions"] = {
            "low_width": "800",
            "medium_width": "1600",
            "high_width": "2400"
        }

        # File to read: the one of the application folder or, the first time,
        # the one that earlier versions wrote in the current folder
        source = None
        legacy = Path.cwd() / CONFIG_FILE
        if self.config_path.exists():
            source = self.config_path
        elif legacy.exists():
            source = legacy

        if source is not None:
            self._read_config_file(source)

        self.current_lang = self.config.get("General", "language", fallback="fr")
        self.source_dir = self.config.get("General", "last_source_dir", fallback="")
        self.dest_dir = self.config.get("General", "last_dest_dir", fallback="")

        # First start, or settings moved from the old location: write the file
        if source != self.config_path:
            self._save_config()

    def _read_config_file(self, path: Path):
        """Read the INI file in UTF-8, or in cp1252 for files written by older versions."""
        for encoding in ("utf-8", "cp1252"):
            try:
                self.config.read(path, encoding=encoding)
                return
            except UnicodeDecodeError:
                continue
            except configparser.Error:
                return      # damaged file: keep the default values

    def _save_config(self):
        """Persist settings to StampPhoto.cfg."""
        if not self.config.has_section("General"):
            self.config.add_section("General")

        self.config["General"]["language"] = getattr(self, "current_lang", "fr")
        self.config["General"]["last_source_dir"] = getattr(self, "source_dir", "")
        self.config["General"]["last_dest_dir"] = getattr(self, "dest_dir", "")
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                self.config.write(f)
        except OSError as e:
            if hasattr(self, "status"):
                self.status.showMessage(f"{self._('Settings could not be saved:')} {e}", 6000)

    # ------------------------------------------------------------------ language
    def _setup_translation(self):
        """Initialize gettext translation according to current configuration."""
        try:
            translation = gettext.translation(
                domain="stampphoto",
                localedir=LOCALE_DIR,
                languages=[self.current_lang],
                fallback=True
            )
            self._ = translation.gettext
        except Exception:
            self._ = lambda s: s
        install_qt_translator(self.current_lang)

    def set_language(self, lang_code: str):
        """Update active language without needing an application restart."""
        if self.current_lang != lang_code:
            self.current_lang = lang_code
            self._save_config()
            self._setup_translation()
            self.retranslate_ui()
        else:
            self._update_language_checks()

    def _update_language_checks(self):
        self.action_lang_fr.setChecked(self.current_lang == "fr")
        self.action_lang_en.setChecked(self.current_lang == "en")

    # ------------------------------------------------------------------ user interface
    def _init_ui(self):
        """Initialize widgets, layouts, menus, and toolbars."""
        self.setMinimumSize(880, 680)

        # Top menu bar. The menu titles are text only: when a menu title has an
        # icon, the menu bar shows the icon instead of the text (texts are set
        # in retranslate_ui). The icons stay on the menu items.
        menubar = self.menuBar()
        self.menu_file = menubar.addMenu("File")
        self.menu_config = menubar.addMenu("Config")
        self.menu_help = menubar.addMenu("Help")

        # File menu items
        self.action_exit = QAction(get_image_icon("exit.png"), "", self)
        self.action_exit.triggered.connect(self.close)
        self.menu_file.addAction(self.action_exit)

        # Config menu items: the language in use is checked
        self.menu_lang = self.menu_config.addMenu("")
        self.lang_group = QActionGroup(self)
        self.lang_group.setExclusive(True)
        self.action_lang_fr = QAction("Français", self, checkable=True)
        self.action_lang_fr.triggered.connect(lambda: self.set_language("fr"))
        self.action_lang_en = QAction("English", self, checkable=True)
        self.action_lang_en.triggered.connect(lambda: self.set_language("en"))
        for action in (self.action_lang_fr, self.action_lang_en):
            self.lang_group.addAction(action)
            self.menu_lang.addAction(action)

        self.action_preferences = QAction(get_image_icon("config.png"), "", self)
        self.action_preferences.triggered.connect(self._open_config_dialog)
        self.menu_config.addAction(self.action_preferences)

        # Help menu items
        self.action_manual = QAction(get_image_icon("manual.svg.png"), "", self)
        self.action_manual.triggered.connect(self._show_manual)
        self.action_about = QAction(get_image_icon("about.png"), "", self)
        self.action_about.triggered.connect(self._show_about)
        self.menu_help.addAction(self.action_manual)
        self.menu_help.addAction(self.action_about)

        # Main Toolbar (title translated in retranslate_ui)
        self.toolbar = QToolBar(self)
        self.toolbar.setObjectName("mainToolbar")
        self.addToolBar(self.toolbar)

        self.act_source = QAction(get_image_icon("folder_source.svg.png"), "", self)
        self.act_source.triggered.connect(self._choose_source_dir)
        self.toolbar.addAction(self.act_source)

        self.act_dest = QAction(get_image_icon("folder_dest.svg.png"), "", self)
        self.act_dest.triggered.connect(self._choose_dest_dir)
        self.toolbar.addAction(self.act_dest)

        self.toolbar.addSeparator()

        # Toolbar conversion shortcuts
        self.act_tb_convert = QAction(get_image_icon("convert_single.svg.png"), "", self)
        self.act_tb_convert.triggered.connect(self._convert_current)
        self.toolbar.addAction(self.act_tb_convert)

        self.act_tb_convert_all = QAction(get_image_icon("convert_all.svg.png"), "", self)
        self.act_tb_convert_all.triggered.connect(self._convert_all)
        self.toolbar.addAction(self.act_tb_convert_all)

        self.toolbar.addSeparator()

        # Settings and help, same actions as in the menus
        self.toolbar.addAction(self.action_preferences)
        self.toolbar.addAction(self.action_manual)
        self.toolbar.addAction(self.action_about)

        self.toolbar.addSeparator()

        # Exit action on toolbar
        self.act_tb_exit = QAction(get_image_icon("exit.png"), "", self)
        self.act_tb_exit.triggered.connect(self.close)
        self.toolbar.addAction(self.act_tb_exit)

        # Central widget and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # Left: pattern search and list of the pictures in alphabetical order.
        # Right: preview, name of the current picture and navigation.
        splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(splitter, stretch=1)

        list_panel = QWidget()
        list_layout = QVBoxLayout(list_panel)
        list_layout.setContentsMargins(0, 0, 0, 0)

        self.edit_search = QLineEdit()
        self.edit_search.setClearButtonEnabled(True)
        self.edit_search.textChanged.connect(self._on_search_changed)
        self.edit_search.returnPressed.connect(self._on_search_changed)
        list_layout.addWidget(self.edit_search)

        self.lbl_matches = QLabel()
        self.lbl_matches.setWordWrap(True)
        self.lbl_matches.setStyleSheet("color: #555;")
        list_layout.addWidget(self.lbl_matches)

        self.list_images = QListWidget()
        self.list_images.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.list_images.currentRowChanged.connect(self._on_list_current_changed)
        self.list_images.itemSelectionChanged.connect(self._update_selection_state)
        list_layout.addWidget(self.list_images, stretch=1)

        view_panel = QWidget()
        view_layout = QVBoxLayout(view_panel)
        view_layout.setContentsMargins(0, 0, 0, 0)

        # Centered photo display area
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setStyleSheet("background-color: #242424; border: 1px solid #444; "
                                       "border-radius: 4px; color: #dddddd;")
        self.image_label.setMinimumSize(200, 200)

        # Information panel, on the right of the picture
        self.info_box = QGroupBox()
        self.info_box.setFixedWidth(230)
        info_form = QFormLayout(self.info_box)
        info_form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        info_form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        self.info_titles = {}
        self.info_values = {}
        for key in ("size", "format", "width", "height", "dpi", "mm"):
            title, value = QLabel(), QLabel("-")
            title.setStyleSheet("color: #555;")
            value.setWordWrap(True)
            value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            value_font = value.font()
            value_font.setBold(True)
            value.setFont(value_font)
            info_form.addRow(title, value)
            self.info_titles[key], self.info_values[key] = title, value
        self.lbl_mm_note = QLabel()
        self.lbl_mm_note.setWordWrap(True)
        self.lbl_mm_note.setStyleSheet("color: #8a5a00;")
        info_form.addRow(self.lbl_mm_note)

        picture_row = QHBoxLayout()
        picture_row.addWidget(self.image_label, stretch=1)
        picture_row.addWidget(self.info_box, alignment=Qt.AlignmentFlag.AlignTop)
        view_layout.addLayout(picture_row, stretch=1)

        # Name of the current picture
        self.lbl_name = QLabel()
        self.lbl_name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_name.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        name_font = self.lbl_name.font()
        name_font.setBold(True)
        name_font.setPointSize(name_font.pointSize() + 1)
        self.lbl_name.setFont(name_font)
        view_layout.addWidget(self.lbl_name)

        splitter.addWidget(list_panel)
        splitter.addWidget(view_panel)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([240, 760])

        # Backward and forward navigation buttons
        nav_layout = QHBoxLayout()
        self.btn_prev = QPushButton()
        self.btn_prev.setFixedHeight(36)
        self.btn_prev.clicked.connect(self._prev_image)
        nav_layout.addWidget(self.btn_prev)

        self.lbl_counter = QLabel("- / -")
        self.lbl_counter.setAlignment(Qt.AlignmentFlag.AlignCenter)
        nav_layout.addWidget(self.lbl_counter)

        self.btn_next = QPushButton()
        self.btn_next.setFixedHeight(36)
        self.btn_next.clicked.connect(self._next_image)
        nav_layout.addWidget(self.btn_next)
        view_layout.addLayout(nav_layout)

        # Conversion options bar
        conv_layout = QHBoxLayout()
        self.lbl_res = QLabel()
        conv_layout.addWidget(self.lbl_res)

        self.combo_res = QComboBox()
        for key in ("low", "med", "high", "all"):
            self.combo_res.addItem("", key)          # texts set in retranslate_ui
        conv_layout.addWidget(self.combo_res)

        self.btn_convert = QPushButton()
        self.btn_convert.setIcon(get_image_icon("convert_single.svg.png"))
        self.btn_convert.clicked.connect(self._convert_current)
        conv_layout.addWidget(self.btn_convert)

        self.btn_convert_all = QPushButton()
        self.btn_convert_all.setIcon(get_image_icon("convert_all.svg.png"))
        self.btn_convert_all.clicked.connect(self._convert_all)
        conv_layout.addWidget(self.btn_convert_all)

        self.btn_convert_sel = QPushButton()
        self.btn_convert_sel.setIcon(get_image_icon("convert_all.svg.png"))
        self.btn_convert_sel.clicked.connect(self._convert_selection)
        self.btn_convert_sel.setEnabled(False)
        conv_layout.addWidget(self.btn_convert_sel)
        main_layout.addLayout(conv_layout)

        # Progress bar with its Stop button, visible during a batch conversion
        progress_layout = QHBoxLayout()
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        progress_layout.addWidget(self.progress_bar, stretch=1)
        self.btn_stop = QPushButton()
        self.btn_stop.setVisible(False)
        self.btn_stop.clicked.connect(self._request_stop)
        progress_layout.addWidget(self.btn_stop)
        main_layout.addLayout(progress_layout)

        # Status bar
        self.status = QStatusBar()
        self.setStatusBar(self.status)

    def retranslate_ui(self):
        """Update all interface labels immediately when language changes."""
        self.setWindowTitle(self._("StampPhoto - stampOffice Suite"))

        # Menu titles (text only, see _init_ui)
        self.menu_file.setTitle(self._("&File"))
        self.menu_config.setTitle(self._("&Config"))
        self.menu_help.setTitle(self._("&Help"))

        # Menu items
        self.action_exit.setText(self._("&Exit"))
        self.menu_lang.setTitle(self._("&Language"))
        self._update_language_checks()
        self.action_preferences.setText(self._("&Preferences..."))
        self.action_manual.setText(self._("&Manual"))
        self.action_about.setText(self._("&About"))

        # Actions and Buttons
        self.toolbar.setWindowTitle(self._("Main Toolbar"))
        self.act_source.setText(self._("Select Source Folder..."))
        self.act_source.setToolTip(self._("Select Source Folder..."))
        self.act_dest.setText(self._("Select Destination Folder..."))
        self.act_dest.setToolTip(self._("Select Destination Folder..."))

        self.act_tb_convert.setText(self._("Convert Current"))
        self.act_tb_convert.setToolTip(self._("Convert Current"))
        self.act_tb_convert_all.setText(self._("Convert All"))
        self.act_tb_convert_all.setToolTip(self._("Convert All"))

        self.act_tb_exit.setText(self._("&Exit"))
        self.act_tb_exit.setToolTip(self._("Exit Application"))

        self.btn_prev.setText(self._("◀ Previous"))
        self.btn_next.setText(self._("Next ▶"))
        self.lbl_res.setText(self._("Resolution:"))
        self.btn_convert.setText(self._("Convert Current"))
        self.btn_convert_all.setText(self._("Convert All"))
        self.btn_stop.setText(self._("Stop"))
        self.edit_search.setPlaceholderText(self._("Search: beginning of the name..."))
        self.edit_search.setToolTip(self._("Selects every picture whose name starts with this text "
                                           "(* and ? wildcards allowed)"))
        self.list_images.setToolTip(self._("Ctrl+click or Shift+click to select several pictures"))

        # Toolbar buttons that share the menu actions: tooltip without the "&"
        self.action_preferences.setToolTip(self._("Preferences"))
        self.action_manual.setToolTip(self._("User manual"))
        self.action_about.setToolTip(self._("About StampPhoto"))

        # Information panel
        self.info_box.setTitle(self._("Picture information"))
        for key, text in (("size", self._("File size:")), ("format", self._("Format:")),
                          ("width", self._("Width:")), ("height", self._("Height:")),
                          ("dpi", self._("Resolution:")), ("mm", self._("Estimated size:"))):
            self.info_titles[key].setText(text)
        self._update_selection_state()
        self._update_match_label()

        # Resolution choices: only the texts change, the selection is kept
        for i, text in enumerate((self._("Low Resolution"), self._("Medium Resolution"),
                                  self._("High Resolution"), self._("All Resolutions"))):
            self.combo_res.setItemText(i, text)

        self._update_image_display()

    def closeEvent(self, event: QCloseEvent):
        """Prompt confirmation dialog before closing the application."""
        if self._busy:
            reply = QMessageBox.question(
                self,
                self._("Confirm Exit"),
                self._("A conversion is in progress. Stop it and exit StampPhoto?"),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                # Closed once the picture being converted is finished
                self._close_after_batch = True
                self._stop_requested = True
            event.ignore()
            return
        if self._close_after_batch:
            event.accept()
            return
        reply = QMessageBox.question(
            self,
            self._("Confirm Exit"),
            self._("Are you sure you want to exit StampPhoto?"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            event.accept()
        else:
            event.ignore()

    # ------------------------------------------------------------------ folders and preview
    def _choose_source_dir(self):
        """Prompt user for photo directory."""
        directory = QFileDialog.getExistingDirectory(
            self, self._("Select Source Folder"), self.source_dir
        )
        if directory:
            self.source_dir = directory
            self._save_config()
            self._load_images_from_source()

    def _choose_dest_dir(self):
        """Prompt user for target export directory."""
        directory = QFileDialog.getExistingDirectory(
            self, self._("Select Destination Folder"), self.dest_dir
        )
        if directory:
            self.dest_dir = directory
            self._save_config()
            self.status.showMessage(f"{self._('Destination:')} {self.dest_dir}", 4000)

    def _load_images_from_source(self):
        """Scan source directory for valid image files."""
        try:
            names = sorted(os.listdir(self.source_dir), key=str.lower)
        except OSError as e:
            names = []
            self.status.showMessage(f"{self._('The folder cannot be read:')} {e}", 6000)
        names = [f for f in names
                 if f.lower().endswith(VALID_EXTENSIONS) and os.path.isfile(os.path.join(self.source_dir, f))]
        names.sort(key=natural_key)              # natural alphabetical order
        self.images = [os.path.join(self.source_dir, f) for f in names]

        self.list_images.blockSignals(True)
        self.list_images.clear()
        for name in names:
            item = QListWidgetItem(name)
            item.setToolTip(name)
            self.list_images.addItem(item)
        self.list_images.blockSignals(False)

        self.current_index = 0 if self.images else -1
        self._pixmap_cache = (None, QPixmap())
        self._update_image_display()
        # Keep the search active on the new folder
        self._on_search_changed()

    def _current_pixmap(self) -> QPixmap:
        """Picture shown in the preview, read from disk only when it changes.
        The EXIF orientation is applied, as for the conversion."""
        path = self.images[self.current_index]
        if self._pixmap_cache[0] != path:
            reader = QImageReader(path)
            reader.setAutoTransform(True)
            self._pixmap_cache = (path, QPixmap.fromImage(reader.read()))
            try:
                self._picture_info = read_picture_info(path)
            except Exception:
                self._picture_info = None          # unreadable: shown as "-"
        return self._pixmap_cache[1]

    def _update_image_display(self):
        """Render the current image inside the central preview widget."""
        if not self.images or self.current_index < 0:
            self.image_label.setText(self._("No images found in the selected folder."))
            self.lbl_counter.setText("- / -")
            self.lbl_name.setText("")
            self._show_picture_info(None)
            return

        # Name of the picture, and the same picture highlighted in the list
        self.lbl_name.setText(os.path.basename(self.images[self.current_index]))
        if self.list_images.currentRow() != self.current_index:
            self.list_images.blockSignals(True)
            self.list_images.setCurrentRow(self.current_index, QItemSelectionModel.SelectionFlag.NoUpdate)
            self.list_images.blockSignals(False)
        self.list_images.scrollToItem(self.list_images.item(self.current_index))

        pixmap = self._current_pixmap()
        if not pixmap.isNull():
            scaled_pixmap = pixmap.scaled(
                self.image_label.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.image_label.setPixmap(scaled_pixmap)
        else:
            self.image_label.setText(self._("Failed to load image."))

        self._show_picture_info(self._picture_info)

        counter_pattern = self._("Image {current} / {total}")
        self.lbl_counter.setText(
            counter_pattern.format(current=self.current_index + 1, total=len(self.images))
        )

    def _number(self, value: float, decimals: int = 0) -> str:
        """Number written the way of the interface language (1 234,5 / 1,234.5)."""
        return QLocale(self.current_lang).toString(float(value), 'f', decimals)

    def _show_picture_info(self, info):
        """Fill the information panel on the right of the picture."""
        values = self.info_values
        if not info:
            for label in values.values():
                label.setText("-")
            self.lbl_mm_note.setText("")
            self.lbl_mm_note.setVisible(False)
            return
        size_kb = info["bytes"] / 1024
        values["size"].setText(self._("{size} KB").format(size=self._number(size_kb, 1)))
        values["format"].setText(info["format"])
        values["width"].setText(self._("{n} pixels").format(n=self._number(info["width"])))
        values["height"].setText(self._("{n} pixels").format(n=self._number(info["height"])))
        dpi = info["dpi"]
        if dpi is None:
            values["dpi"].setText(self._("not recorded in the file"))
        elif abs(dpi[0] - dpi[1]) < 0.5:
            values["dpi"].setText(self._("{dpi} dpi").format(dpi=self._number(dpi[0])))
        else:
            values["dpi"].setText(self._("{x} × {y} dpi").format(x=self._number(dpi[0]), y=self._number(dpi[1])))

        width_mm, height_mm, used_dpi, assumed = estimated_size_mm(info)
        values["mm"].setText(self._("{w} × {h} mm").format(w=self._number(width_mm, 1), h=self._number(height_mm, 1)))
        if assumed:
            reason = (self._("The file records no resolution.") if dpi is None else
                      self._("{dpi} dpi is the default value of cameras and screens, not a scan resolution.")
                      .format(dpi=self._number(min(dpi))))
            self.lbl_mm_note.setText(reason + " " + self._("Size estimated for a scan at {dpi} dpi.")
                                     .format(dpi=ASSUMED_SCAN_DPI))
        else:
            self.lbl_mm_note.setText("")
        self.lbl_mm_note.setVisible(assumed)

    def resizeEvent(self, event):
        """Maintain proper image scaling when window dimensions change."""
        super().resizeEvent(event)
        self._update_image_display()

    def _on_list_current_changed(self, row: int):
        """A picture was clicked (or reached with the arrow keys) in the list."""
        if 0 <= row < len(self.images) and row != self.current_index:
            self.current_index = row
            self._update_image_display()

    def _matching_rows(self):
        pattern = self.edit_search.text()
        return [i for i, path in enumerate(self.images) if name_starts_with(os.path.basename(path), pattern)]

    def _on_search_changed(self, *args):
        """Select every picture whose name starts with the pattern, and show the first one."""
        if not self.edit_search.text().strip():
            self._update_match_label()
            return
        rows = self._matching_rows()
        self.list_images.blockSignals(True)
        self.list_images.clearSelection()
        for row in rows:
            self.list_images.item(row).setSelected(True)
        self.list_images.blockSignals(False)
        if rows:
            self.current_index = rows[0]
            self._update_image_display()
        self._update_selection_state()
        self._update_match_label()

    def _update_match_label(self):
        """Result of the pattern search, or the number of selected pictures."""
        pattern = self.edit_search.text().strip()
        if pattern:
            n = len(self._matching_rows())
            if n:
                text = self._("{n} picture(s) starting with \"{pattern}\"").format(n=n, pattern=pattern)
            else:
                text = self._("No picture starts with \"{pattern}\"").format(pattern=pattern)
        else:
            n = len(self.list_images.selectedItems())
            text = self._("{n} picture(s) selected").format(n=n) if n > 1 else ""
        self.lbl_matches.setText(text)
        self.lbl_matches.setVisible(bool(text))

    def _selected_paths(self):
        rows = sorted(self.list_images.row(item) for item in self.list_images.selectedItems())
        return [self.images[r] for r in rows if 0 <= r < len(self.images)]

    def _update_selection_state(self):
        """Enable "Convert Selection" when pictures are selected; its text shows how many."""
        n = len(self.list_images.selectedItems())
        self.btn_convert_sel.setText(self._("Convert Selection ({n})").format(n=n) if n
                                     else self._("Convert Selection"))
        self.btn_convert_sel.setEnabled(n > 0 and not self._busy)
        if not self.edit_search.text().strip():
            self._update_match_label()

    def _prev_image(self):
        """Navigate to the previous picture."""
        if self.images and self.current_index > 0:
            self.current_index -= 1
            self._update_image_display()

    def _next_image(self):
        """Navigate to the next picture."""
        if self.images and self.current_index < len(self.images) - 1:
            self.current_index += 1
            self._update_image_display()

    # ------------------------------------------------------------------ conversion
    def _target_sizes(self, target_key: str):
        """[(longest side in px, file suffix)] for the chosen resolution."""
        sizes = []
        for key, option, default, suffix in RESOLUTIONS:
            if target_key in (key, "all"):
                try:
                    value = int(self.config.get("Resolutions", option, fallback=default))
                except ValueError:
                    value = int(default)
                sizes.append((max(1, value), suffix))
        return sizes

    def _output_base_name(self, img_path: str) -> str:
        """Base name of the converted files. When several pictures of the source
        folder share the same name (timbre.png, timbre.jpg), the original
        extension is added so that they do not overwrite each other."""
        stem, ext = os.path.splitext(os.path.basename(img_path))
        same_name = Counter(os.path.splitext(os.path.basename(p))[0].lower() for p in self.images)
        if same_name[stem.lower()] > 1:
            return f"{stem}_{ext.lstrip('.').lower()}"
        return stem

    def _plan_conversion(self, img_paths, target_key):
        """[(source picture, [(longest side, destination file)])]"""
        sizes = self._target_sizes(target_key)
        plan = []
        for img_path in img_paths:
            base = self._output_base_name(img_path)
            outputs = [(size, os.path.join(self.dest_dir, f"{base}{suffix}.jpg")) for size, suffix in sizes]
            plan.append((img_path, outputs))
        return plan

    def _resize_and_save_jpg(self, img_path: str, outputs):
        """Convert the picture to JPG for each (longest side, destination file).
        Raises an exception if the picture cannot be read or a file cannot be written."""
        try:
            quality = int(self.config.get("General", "jpeg_quality", fallback="85"))
        except ValueError:
            quality = 85
        quality = min(95, max(1, quality))

        with Image.open(img_path) as im:
            rgb_im = prepare_rgb(im)
            for max_side, dest_path in outputs:
                resize_longest_side(rgb_im, max_side).save(dest_path, "JPEG", quality=quality)

    def _check_paths_configured(self) -> bool:
        """Validate source and target paths before running conversion."""
        if not self.images:
            QMessageBox.warning(self, self._("Warning"), self._("Please select a source folder with images first."))
            return False
        if not self.dest_dir or not os.path.isdir(self.dest_dir):
            QMessageBox.warning(self, self._("Warning"), self._("Please select a destination directory."))
            return False
        return True

    def _ask_existing(self, plan):
        """When converted files already exist: 'replace', 'skip' or None (cancel)."""
        existing = [dest for _src, outputs in plan for _size, dest in outputs if os.path.exists(dest)]
        if not existing:
            return "replace"
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Question)
        box.setWindowTitle(self._("Files already exist"))
        box.setText(self._("{n} file(s) already exist in the destination folder.").format(n=len(existing)))
        box.setInformativeText("\n".join(os.path.basename(p) for p in existing[:8])
                               + ("\n…" if len(existing) > 8 else ""))
        btn_replace = box.addButton(self._("Replace"), QMessageBox.ButtonRole.AcceptRole)
        btn_skip = box.addButton(self._("Keep existing files"), QMessageBox.ButtonRole.ActionRole)
        btn_cancel = box.addButton(self._("Cancel"), QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(btn_skip)
        box.setEscapeButton(btn_cancel)
        box.exec()
        clicked = box.clickedButton()
        if clicked is btn_replace:
            return "replace"
        if clicked is btn_skip:
            return "skip"
        return None

    def _set_busy(self, busy: bool, batch: bool):
        """Lock the commands during a conversion (a second click would start
        another conversion on top of the first one)."""
        self._busy = busy
        for widget in (self.act_source, self.act_dest, self.act_tb_convert, self.act_tb_convert_all,
                       self.btn_convert, self.btn_convert_all, self.combo_res,
                       self.action_preferences, self.menu_lang, self.edit_search, self.list_images):
            widget.setEnabled(not busy)
        self.btn_convert_sel.setEnabled(not busy and bool(self.list_images.selectedItems()))
        self.progress_bar.setVisible(busy and batch)
        self.btn_stop.setVisible(busy and batch)
        self.btn_stop.setEnabled(True)
        if busy:
            QApplication.setOverrideCursor(Qt.CursorShape.BusyCursor)
        else:
            QApplication.restoreOverrideCursor()

    def _request_stop(self):
        """Stop the batch after the picture being converted."""
        self._stop_requested = True
        self.btn_stop.setEnabled(False)
        self.status.showMessage(self._("Stopping after the current picture..."))

    def _run_conversion(self, img_paths, batch: bool):
        """Convert the given pictures and report the result."""
        if self._busy or not self._check_paths_configured():
            return
        plan = self._plan_conversion(img_paths, self.combo_res.currentData())
        decision = self._ask_existing(plan)
        if decision is None:
            return

        total = len(plan)
        converted, skipped, failures = 0, 0, []
        already_done = 0            # pictures whose files all exist and were kept
        self._stop_requested = False
        self._set_busy(True, batch)
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(0)
        try:
            for i, (img_path, outputs) in enumerate(plan):
                if self._stop_requested:
                    break
                if decision == "skip":
                    kept = [o for o in outputs if not os.path.exists(o[1])]
                    skipped += len(outputs) - len(kept)
                    if not kept:
                        already_done += 1
                    outputs = kept
                name = os.path.basename(img_path)
                self.status.showMessage(self._("Converting {name}...").format(name=name))
                if outputs:
                    try:
                        self._resize_and_save_jpg(img_path, outputs)
                        converted += 1
                    except Exception as e:      # unreadable picture, disk full, read-only folder...
                        failures.append(f"{name}: {self._failure_reason(e)}")
                self.progress_bar.setValue(i + 1)
                QApplication.processEvents()
        finally:
            stopped = self._stop_requested
            self._set_busy(False, batch)
            self.status.clearMessage()

        if self._close_after_batch:
            self.close()
            return
        # Pictures whose files were all kept are not part of the count
        self._report(total - already_done, converted, skipped, failures, stopped, batch)

    def _failure_reason(self, error: Exception) -> str:
        """Short reason shown to the user (no technical message with full paths)."""
        if isinstance(error, UnidentifiedImageError):
            return self._("unreadable or damaged picture")
        if isinstance(error, PermissionError):
            return self._("permission denied in the destination folder")
        if isinstance(error, OSError) and error.strerror:
            return error.strerror
        return str(error) or error.__class__.__name__

    def _report(self, total, converted, skipped, failures, stopped, batch):
        """Final message of a conversion (total: pictures that had to be converted)."""
        lines = []
        if stopped:
            lines.append(self._("Conversion stopped: {done} of {total} picture(s) converted.")
                         .format(done=converted, total=total))
        elif not failures:
            lines.append(self._("Batch conversion completed successfully!") if batch
                         else self._("Conversion completed successfully!"))
        if skipped:
            lines.append(self._("{n} existing file(s) kept.").format(n=skipped))
        if failures:
            if not stopped:
                lines.append(self._("{done} of {total} picture(s) converted.").format(done=converted, total=total))
            lines.append("")
            lines.append(self._("{n} picture(s) could not be converted:").format(n=len(failures)))
            lines += ["• " + f for f in failures[:10]]
            if len(failures) > 10:
                lines.append("…")
            QMessageBox.warning(self, self._("Warning"), "\n".join(lines))
        else:
            QMessageBox.information(self, self._("Success") if not stopped else self._("Stop"),
                                    "\n".join(lines))

    def _convert_current(self):
        """Convert the currently previewed photo."""
        if self.images and self.current_index >= 0:
            self._run_conversion([self.images[self.current_index]], batch=False)
        else:
            self._check_paths_configured()

    def _convert_all(self):
        """Batch convert all images located in the source directory."""
        self._run_conversion(list(self.images), batch=True)

    def _convert_selection(self):
        """Batch convert the pictures selected in the list (e.g. found with the search)."""
        paths = self._selected_paths()
        if paths:
            self._run_conversion(paths, batch=True)

    # ------------------------------------------------------------------ dialogs
    def _open_config_dialog(self):
        """Open the SPConfig preferences dialog."""
        dlg = SPConfigDialog(self.config, parent=self, tr_func=self._)
        if dlg.exec():
            new_lang = self.config.get("General", "language", fallback="fr")
            self._save_config()
            if new_lang != self.current_lang:
                self.set_language(new_lang)

    def _show_about(self):
        """Display the SPAbout dialog."""
        dlg = SPAboutDlg(parent=self, lang=self.current_lang, tr_func=self._)
        dlg.exec()

    def _manual_path(self):
        """The PDF manual in the current language, otherwise in the other language."""
        help_dir = _resource_dir("Help")
        names = [MANUALS.get(self.current_lang)] + [n for lang, n in MANUALS.items() if lang != self.current_lang]
        for name in names:
            if name and (help_dir / name).is_file():
                return help_dir / name
        return None

    def _show_manual(self):
        """Open the PDF user manual; show basic usage instructions if it is missing."""
        path = self._manual_path()
        if path is not None and QDesktopServices.openUrl(QUrl.fromLocalFile(str(path))):
            return
        manual_text = self._(
            "1. Click 'Select Source Folder' to browse your photo directory.\n"
            "2. Navigate between stamps using Previous and Next buttons.\n"
            "3. Choose a destination folder.\n"
            "4. Choose resolution (Low, Medium, High, or All) and click Convert.\n"
            "All converted files are exported in JPG format with resolution suffixes."
        )
        QMessageBox.information(self, self._("StampPhoto Manual"), manual_text)


if __name__ == "__main__":
    set_windows_app_id()                 # before any window is created
    app = QApplication(sys.argv)
    app.setWindowIcon(get_app_icon())    # used by every window and dialog
    window = StampPhotoApp()
    window.show()
    sys.exit(app.exec())
