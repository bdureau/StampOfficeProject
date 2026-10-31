"""
Album Converter
---------------
Stand-alone batch converter that turns AlbumEasy description files (.txt) and
Feuille Album 4 Excel albums (.xls) into Stamp Album files (.sta).

It lives in the Stamp Album folder and reuses the same importers as the editor
(AlbumEasyImporter, XlsAlbumImporter), so a converted album is identical to an
album imported from the editor and then saved.

    python AlbumConverter.py

Each converted album is saved as soon as it is finished, under the source name
with the .sta extension. Stopping the batch keeps every album already converted.

The converter has its own settings (language, conversion options), stored with
QSettings under "StampAlbum/AlbumConverter"; they do not change the editor.

Author: Boris du Reau
"""
import gettext
import json
import os
import sys
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path

from PyQt6.QtCore import QLibraryInfo, QLocale, QSettings, QSize, Qt, QTimer, QTranslator, QUrl
from PyQt6.QtGui import QAction, QActionGroup, QColor, QDesktopServices, QIcon, QKeySequence
from PyQt6.QtWidgets import (
    QAbstractItemView, QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog,
    QFormLayout, QGroupBox, QHBoxLayout, QHeaderView, QLabel, QLayout, QLineEdit, QListWidget, QListWidgetItem,
    QMainWindow, QMessageBox, QPlainTextEdit, QProgressBar, QPushButton, QSizePolicy, QStyle,
    QTableWidget, QTableWidgetItem, QToolBar, QVBoxLayout, QWidget
)

APP_VERSION = "1.0"
APP_AUTHOR = "Boris du Reau"

MODE_ALBUMEASY = "albumeasy"
MODE_FEUILLE = "feuille"
MODE_NAMES = {MODE_ALBUMEASY: "AlbumEasy", MODE_FEUILLE: "Feuille Album 4"}

LANGUAGES = [("en", "English"), ("fr", "Français")]       # names shown in their own language


# ============================================================================
# Localisation (the language can be changed while the application runs)
# ============================================================================

def _app_dir() -> Path:
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def _resource_dirs(folder: str):
    """Candidate locations of a resource folder (Images, Help, locale): next to the
    application folder first (../Images when the script is in a sub-folder, as for
    Stamp Album), then inside it."""
    base = _app_dir()
    seen, out = set(), []
    for d in (base.parent / folder, base / folder, Path.cwd() / folder):
        key = str(d.resolve()).lower()
        if key not in seen and d.is_dir():
            seen.add(key)
            out.append(d)
    return out


def _locale_dir() -> str:
    for d in (_app_dir() / "locale", _app_dir().parent / "locale"):
        if d.is_dir():
            return str(d)
    return "locale"


_translation = gettext.NullTranslations()
_current_language = "en"


def set_language(lang: str):
    global _translation, _current_language
    _current_language = lang
    _translation = gettext.translation('AlbumConverter', localedir=_locale_dir(),
                                       languages=[lang], fallback=True)


def _(text: str) -> str:
    return _translation.gettext(text)


class Msg:
    """A message translated when it is displayed, so results already in the table
    follow a change of language."""

    def __init__(self, msgid, **kwargs):
        self.msgid = msgid
        self.kwargs = kwargs

    def __str__(self):
        text = _(self.msgid)
        if not self.kwargs:
            return text
        values = {k: (str(v) if isinstance(v, Msg) else v) for k, v in self.kwargs.items()}
        return text.format(**values)


class ConversionError(Exception):
    def __init__(self, msg: Msg):
        super().__init__(msg.msgid)
        self.msg = msg

    def __str__(self):
        return str(self.msg)


def default_language() -> str:
    try:
        from AppLanguage import get_language
        lang = (get_language() or "")[:2].lower()
    except Exception:
        lang = QLocale.system().name()[:2].lower()
    return lang if lang in dict(LANGUAGES) else "en"


# ============================================================================
# Settings
# ============================================================================

POLICY_ASK, POLICY_OVERWRITE, POLICY_SKIP, POLICY_RENAME = "ask", "overwrite", "skip", "rename"
BORDER_STYLES = ["", "triple", "simple", "greek", "dentelle"]       # "" = Stamp Album setting


def _policy_label(policy):
    return {POLICY_ASK: _("Ask"), POLICY_OVERWRITE: _("Replace"),
            POLICY_SKIP: _("Skip"), POLICY_RENAME: _("Rename (Album (2).sta)")}[policy]


def _border_label(style):
    return {"": _("Stamp Album setting"), "triple": _("Triple (Classic)"), "simple": _("Simple (Frame)"),
            "greek": _("Greek (Notched)"), "dentelle": _("Dentelle (Philately)")}[style]


class Settings:
    """Converter settings, persisted with QSettings."""

    DEFAULTS = {
        "language": None,                  # resolved by default_language()
        "existing_policy": POLICY_ASK,
        "same_as_source": False,
        "auto_report": False,
        "border_style": "",
        "author": "",
        "album_language": "fr",
        "image_dirs": [],
    }

    def __init__(self):
        self.qs = QSettings("StampAlbum", "AlbumConverter")
        self.values = {}
        for key, default in self.DEFAULTS.items():
            self.values[key] = self._read(key, default)
        if self.values["language"] not in dict(LANGUAGES):
            self.values["language"] = default_language()
        if self.values["existing_policy"] not in (POLICY_ASK, POLICY_OVERWRITE, POLICY_SKIP, POLICY_RENAME):
            self.values["existing_policy"] = POLICY_ASK
        if self.values["border_style"] not in BORDER_STYLES:
            self.values["border_style"] = ""

    def _read(self, key, default):
        raw = self.qs.value(key, None)
        if raw is None:
            return default
        if isinstance(default, bool):
            return raw in (True, "true", "1", 1)
        if isinstance(default, list):
            try:
                value = json.loads(raw) if isinstance(raw, str) else list(raw)
                return [str(v) for v in value]
            except (ValueError, TypeError):
                return []
        return str(raw)

    def __getitem__(self, key):
        return self.values[key]

    def update(self, new_values: dict):
        for key, value in new_values.items():
            self.values[key] = value
            self.qs.setValue(key, json.dumps(value) if isinstance(value, list) else value)
        self.qs.sync()

    # Per-mode conveniences (last folders used)
    def get(self, key, default=""):
        return self.qs.value(key, default, str)

    def set(self, key, value):
        self.qs.setValue(key, value)


# ============================================================================
# Icons (PNG files in ../Images, see ICON_FILES)
# ============================================================================

ICON_FILES = {
    "albumeasy": "conv_albumeasy.png",
    "feuille": "conv_feuille.png",
    "config": "conv_config.png",
    "stop": "conv_stop.png",
    "quit": "conv_quit.png",
    "folder": "conv_folder.png",
    "report": "conv_report.png",
    "help": "conv_help.png",
    "about": "conv_about.png",
    "app": "conv_app.png",
}
# Used only when an icon file is missing, so the application keeps working
_FALLBACK = {
    "albumeasy": QStyle.StandardPixmap.SP_FileIcon, "feuille": QStyle.StandardPixmap.SP_FileDialogDetailedView,
    "config": QStyle.StandardPixmap.SP_FileDialogInfoView, "stop": QStyle.StandardPixmap.SP_BrowserStop,
    "quit": QStyle.StandardPixmap.SP_DialogCloseButton, "folder": QStyle.StandardPixmap.SP_DirOpenIcon,
    "report": QStyle.StandardPixmap.SP_DialogSaveButton, "help": QStyle.StandardPixmap.SP_DialogHelpButton,
    "about": QStyle.StandardPixmap.SP_MessageBoxInformation, "app": QStyle.StandardPixmap.SP_DesktopIcon,
}
_icon_cache = {}
_missing_icons = []


def find_image(filename: str):
    for folder in _resource_dirs("Images"):
        path = folder / filename
        if path.is_file():
            return path
    return None


def make_icon(name: str) -> QIcon:
    if name not in _icon_cache:
        path = find_image(ICON_FILES[name])
        if path is not None:
            _icon_cache[name] = QIcon(str(path))
        else:
            _missing_icons.append(ICON_FILES[name])
            _icon_cache[name] = QApplication.style().standardIcon(_FALLBACK[name])
    return _icon_cache[name]


def _app_icon():
    if find_image(ICON_FILES["app"]) is not None:
        return make_icon("app")
    path = find_image("stamp_book.png")
    return QIcon(str(path)) if path is not None else make_icon("app")


# ============================================================================
# Conversion of a single file
# ============================================================================

STATUS_PENDING, STATUS_RUNNING, STATUS_OK, STATUS_WARN, STATUS_ERROR, STATUS_SKIPPED, STATUS_STOPPED = range(7)
STATUS_COLORS = {
    STATUS_OK: QColor("#1b7f3b"),
    STATUS_WARN: QColor("#b26a00"),
    STATUS_ERROR: QColor("#c62828"),
    STATUS_SKIPPED: QColor("#6b6b6b"),
    STATUS_STOPPED: QColor("#6b6b6b"),
}


def _status_text(status):
    return {
        STATUS_PENDING: _("Pending"),
        STATUS_RUNNING: _("Converting..."),
        STATUS_OK: _("Converted"),
        STATUS_WARN: _("Converted with warnings"),
        STATUS_ERROR: _("Failed"),
        STATUS_SKIPPED: _("Skipped"),
        STATUS_STOPPED: _("Not converted (stopped)"),
    }[status]


@dataclass
class Options:
    """Options applied to every file of a batch."""
    border_style: str = ""
    author: str = ""
    album_language: str = "fr"
    image_dirs: list = field(default_factory=list)


@dataclass
class Job:
    source: Path
    target: Path
    status: int = STATUS_PENDING
    pages: int = 0
    stamps: int = 0
    summary: object = ""          # str or Msg
    details: list = field(default_factory=list)


def _make_albumeasy_importer(image_dirs):
    """AlbumEasyImporter that also looks for missing pictures in extra folders.
    (Subclass: the importer shared with the editor is not modified.)"""
    from AlbumEasyImporter import AlbumEasyImporter

    class ConverterAlbumEasyImporter(AlbumEasyImporter):
        def _load_pixmap(self, rel_path):
            pix = super()._load_pixmap(rel_path)
            if not pix.isNull() or self.img_hide or not rel_path or rel_path not in self.missing_images:
                return pix
            saved = self.base_dir
            try:
                for folder in image_dirs:
                    for candidate in (rel_path, Path(rel_path.replace('\\', '/')).name):
                        self.missing_images.remove(rel_path)
                        already_missing = candidate in self.missing_images
                        self.base_dir = Path(folder)
                        pix = super()._load_pixmap(candidate)
                        if candidate != rel_path and not already_missing and candidate in self.missing_images:
                            self.missing_images.remove(candidate)
                        if not pix.isNull():
                            return pix
                        if rel_path not in self.missing_images:
                            self.missing_images.append(rel_path)
            finally:
                self.base_dir = saved
            return pix

    return ConverterAlbumEasyImporter


def convert_file(mode, source: Path, target: Path, options: Options = None, on_page=None):
    """Convert one album and save it. Returns (pages, stamps, warnings).
    Raises an exception if the file cannot be converted."""
    from AlbumWriter import HeadlessAlbum, save_album

    options = options or Options()
    album = HeadlessAlbum(on_new_page=on_page, border_style=options.border_style or None)
    album.album_metadata["author"] = options.author          # an ALBUM_AUTHOR command overrides it
    album.album_metadata["language"] = options.album_language
    warnings = []
    try:
        if mode == MODE_ALBUMEASY:
            importer_cls = _make_albumeasy_importer(options.image_dirs)
            report = importer_cls(album, str(source)).run()
            for path in report.get("missing_images", []):
                warnings.append(Msg("Image not found: {path}", path=path))
            for cmd, n in sorted(report.get("unsupported", {}).items()):
                warnings.append(Msg("Ignored command: {cmd} ({n}x)", cmd=cmd, n=n))
            warnings += report.get("notes", [])
        else:
            try:
                import olefile
                from XlsAlbumImporter import XlsAlbumImporter
            except ImportError as e:
                if "olefile" in str(e):
                    raise ConversionError(Msg("The 'olefile' module is required: pip install olefile"))
                raise
            if not olefile.isOleFile(str(source)):
                raise ConversionError(Msg("This is not an Excel 97-2003 workbook (.xls)."))
            report = XlsAlbumImporter(album, str(source)).run()
            if report.get("no_image"):
                warnings.append(Msg("{n} stamp(s) without image", n=report["no_image"]))
            warnings += [w.replace("\n", " ") for w in report.get("warnings", [])]

        if not album.pages:
            raise ConversionError(Msg("No album page was found in this file."))

        save_album(album.pages, str(target), album.album_metadata)
        return len(album.pages), album.stamp_count(), warnings
    finally:
        album.dispose()


def unique_target(target: Path, taken=()) -> Path:
    """Album.sta -> Album (2).sta, Album (3).sta ... (first free name)."""
    taken = {str(t).lower() for t in taken}
    n = 2
    while True:
        candidate = target.with_name(f"{target.stem} ({n}).sta")
        if not candidate.exists() and str(candidate).lower() not in taken:
            return candidate
        n += 1


# ============================================================================
# Configuration dialog
# ============================================================================

class ConfigDialog(QDialog):
    def __init__(self, settings: Settings, parent=None):
        super().__init__(parent)
        self.setWindowTitle(_("Configuration"))
        self.setWindowIcon(make_icon("config"))
        self.resize(560, 560)

        # --- General
        self.languageCombo = QComboBox()
        for code, name in LANGUAGES:
            self.languageCombo.addItem(name, code)
        general = QFormLayout()
        general.addRow(_("Application language:"), self.languageCombo)
        box_general = QGroupBox(_("General"))
        box_general.setLayout(general)

        # --- Conversion
        self.policyCombo = QComboBox()
        for policy in (POLICY_ASK, POLICY_OVERWRITE, POLICY_SKIP, POLICY_RENAME):
            self.policyCombo.addItem(_policy_label(policy), policy)
        self.sameAsSourceCheck = QCheckBox(_("Save each album next to its source file"))
        self.autoReportCheck = QCheckBox(_("Save a report automatically at the end of each batch"))
        conv = QFormLayout()
        conv.addRow(_("If the .sta file already exists:"), self.policyCombo)
        conv.addRow("", self.sameAsSourceCheck)
        conv.addRow("", self.autoReportCheck)
        box_conv = QGroupBox(_("Conversion"))
        box_conv.setLayout(conv)

        # --- Converted albums
        self.borderCombo = QComboBox()
        for style in BORDER_STYLES:
            self.borderCombo.addItem(_border_label(style), style)
        self.authorEdit = QLineEdit()
        self.authorEdit.setPlaceholderText(_("Used when the source file names no author"))
        self.albumLangCombo = QComboBox()
        for code, name in LANGUAGES:
            self.albumLangCombo.addItem(name, code)
        albums = QFormLayout()
        albums.addRow(_("Page border:"), self.borderCombo)
        albums.addRow(_("Author:"), self.authorEdit)
        albums.addRow(_("Album language:"), self.albumLangCombo)
        box_albums = QGroupBox(_("Converted albums"))
        box_albums.setLayout(albums)

        # --- AlbumEasy pictures
        self.dirList = QListWidget()
        self.dirList.setMinimumHeight(80)
        btn_add = QPushButton(_("&Add folder..."))
        btn_add.clicked.connect(self._add_dir)
        btn_remove = QPushButton(_("&Remove"))
        btn_remove.clicked.connect(lambda: [self.dirList.takeItem(self.dirList.row(i))
                                            for i in self.dirList.selectedItems()])
        dir_buttons = QVBoxLayout()
        dir_buttons.addWidget(btn_add)
        dir_buttons.addWidget(btn_remove)
        dir_buttons.addStretch()
        dirs_row = QHBoxLayout()
        dirs_row.addWidget(self.dirList)
        dirs_row.addLayout(dir_buttons)
        hint = QLabel(_("Pictures not found next to the AlbumEasy file are searched in these folders, in order."))
        hint.setWordWrap(True)
        pics = QVBoxLayout()
        pics.addWidget(hint)
        pics.addLayout(dirs_row)
        box_pics = QGroupBox(_("AlbumEasy pictures"))
        box_pics.setLayout(pics)

        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel |
                              QDialogButtonBox.StandardButton.RestoreDefaults)
        bb.button(QDialogButtonBox.StandardButton.Ok).setText(_("OK"))
        bb.button(QDialogButtonBox.StandardButton.Cancel).setText(_("Cancel"))
        bb.button(QDialogButtonBox.StandardButton.RestoreDefaults).setText(_("Restore defaults"))
        bb.button(QDialogButtonBox.StandardButton.RestoreDefaults).clicked.connect(self._restore_defaults)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        for box in (box_general, box_conv, box_albums, box_pics):
            layout.addWidget(box)
        layout.addWidget(bb)

        self._load(settings.values)

    def _load(self, values):
        self._select(self.languageCombo, values["language"])
        self._select(self.policyCombo, values["existing_policy"])
        self.sameAsSourceCheck.setChecked(bool(values["same_as_source"]))
        self.autoReportCheck.setChecked(bool(values["auto_report"]))
        self._select(self.borderCombo, values["border_style"])
        self.authorEdit.setText(values["author"])
        self._select(self.albumLangCombo, values["album_language"])
        self.dirList.clear()
        for d in values["image_dirs"]:
            self._append_dir(d)

    @staticmethod
    def _select(combo, data):
        idx = combo.findData(data)
        combo.setCurrentIndex(idx if idx >= 0 else 0)

    def _restore_defaults(self):
        values = dict(Settings.DEFAULTS)
        values["language"] = self.languageCombo.currentData()      # keep the current language
        self._load(values)

    def _append_dir(self, folder):
        item = QListWidgetItem(folder)
        item.setData(Qt.ItemDataRole.UserRole, folder)
        if not Path(folder).is_dir():
            item.setForeground(QColor("#c62828"))
            item.setToolTip(_("This folder does not exist"))
        self.dirList.addItem(item)

    def _add_dir(self):
        folder = QFileDialog.getExistingDirectory(
            self, _("Select a picture folder"), "",
            options=QFileDialog.Option.DontUseNativeDialog | QFileDialog.Option.ShowDirsOnly)
        if folder and folder not in self.values()["image_dirs"]:
            self._append_dir(folder)

    def values(self) -> dict:
        return {
            "language": self.languageCombo.currentData(),
            "existing_policy": self.policyCombo.currentData(),
            "same_as_source": self.sameAsSourceCheck.isChecked(),
            "auto_report": self.autoReportCheck.isChecked(),
            "border_style": self.borderCombo.currentData(),
            "author": self.authorEdit.text().strip(),
            "album_language": self.albumLangCombo.currentData(),
            "image_dirs": [self.dirList.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.dirList.count())],
        }


# ============================================================================
# File selection dialog
# ============================================================================

class ConvertDialog(QDialog):
    """Select the files to convert and where to save the albums."""

    def __init__(self, mode, settings: Settings, parent=None):
        super().__init__(parent)
        self.mode = mode
        self.settings = settings
        if mode == MODE_ALBUMEASY:
            self.setWindowTitle(_("Convert AlbumEasy files"))
            self.setWindowIcon(make_icon("albumeasy"))
            self.file_filter = _("AlbumEasy files (*.txt);;All files (*)")
        else:
            self.setWindowTitle(_("Convert Feuille Album 4 files"))
            self.setWindowIcon(make_icon("feuille"))
            self.file_filter = _("Feuille Album 4 files (*.xls);;All files (*)")
        self.resize(660, 460)

        self.fileList = QListWidget()
        self.fileList.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.fileList.setAlternatingRowColors(True)

        btn_add = QPushButton(_("&Add files..."))
        btn_add.clicked.connect(self._add_files)
        btn_remove = QPushButton(_("&Remove"))
        btn_remove.clicked.connect(self._remove_selected)
        btn_clear = QPushButton(_("C&lear"))
        btn_clear.clicked.connect(self.fileList.clear)

        files_buttons = QVBoxLayout()
        files_buttons.addWidget(btn_add)
        files_buttons.addWidget(btn_remove)
        files_buttons.addWidget(btn_clear)
        files_buttons.addStretch()

        files_row = QHBoxLayout()
        files_row.addWidget(self.fileList)
        files_row.addLayout(files_buttons)

        self.countLabel = QLabel()
        self.fileList.model().rowsInserted.connect(self._update_count)
        self.fileList.model().rowsRemoved.connect(self._update_count)

        # Destination
        self.sameAsSourceCheck = QCheckBox(_("Save each album next to its source file"))
        self.sameAsSourceCheck.setChecked(bool(settings["same_as_source"]))
        self.sameAsSourceCheck.toggled.connect(self._update_dest_state)
        self.destEdit = QLineEdit(self.settings.get(f"{mode}/dest_dir", ""))
        self.destButton = QPushButton(_("&Browse..."))
        self.destButton.clicked.connect(self._choose_dest)
        dest_row = QHBoxLayout()
        dest_row.addWidget(self.destEdit)
        dest_row.addWidget(self.destButton)

        self.policyCombo = QComboBox()
        for policy in (POLICY_ASK, POLICY_OVERWRITE, POLICY_SKIP, POLICY_RENAME):
            self.policyCombo.addItem(_policy_label(policy), policy)
        self.policyCombo.setCurrentIndex(max(0, self.policyCombo.findData(settings["existing_policy"])))

        form = QFormLayout()
        form.addRow("", self.sameAsSourceCheck)
        form.addRow(_("Destination folder:"), dest_row)
        form.addRow(_("If the .sta file already exists:"), self.policyCombo)

        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.button(QDialogButtonBox.StandardButton.Ok).setText(_("&Convert"))
        bb.button(QDialogButtonBox.StandardButton.Cancel).setText(_("Cancel"))
        bb.accepted.connect(self._validate)
        bb.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(_("Files to convert:")))
        layout.addLayout(files_row)
        layout.addWidget(self.countLabel)
        layout.addLayout(form)
        layout.addWidget(bb)
        self._update_count()
        self._update_dest_state()

    def _update_dest_state(self, *args):
        enabled = not self.sameAsSourceCheck.isChecked()
        self.destEdit.setEnabled(enabled)
        self.destButton.setEnabled(enabled)

    def _update_count(self, *args):
        self.countLabel.setText(_("{n} file(s) selected").format(n=self.fileList.count()))

    def _add_files(self):
        start = self.settings.get(f"{self.mode}/source_dir", "")
        names, _filter = QFileDialog.getOpenFileNames(
            self, _("Select the files to convert"), start, self.file_filter,
            options=QFileDialog.Option.DontUseNativeDialog)
        if not names:
            return
        self.settings.set(f"{self.mode}/source_dir", str(Path(names[0]).parent))
        if not self.destEdit.text().strip():
            self.destEdit.setText(str(Path(names[0]).parent))
        self.add_files(names)

    def add_files(self, names):
        existing = {self.fileList.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.fileList.count())}
        for name in names:
            path = str(Path(name).resolve())
            if path in existing:
                continue
            item = QListWidgetItem(Path(path).name)
            item.setToolTip(path)
            item.setData(Qt.ItemDataRole.UserRole, path)
            self.fileList.addItem(item)
            existing.add(path)

    def _remove_selected(self):
        for item in self.fileList.selectedItems():
            self.fileList.takeItem(self.fileList.row(item))

    def _choose_dest(self):
        folder = QFileDialog.getExistingDirectory(
            self, _("Select the destination folder"), self.destEdit.text(),
            options=QFileDialog.Option.DontUseNativeDialog | QFileDialog.Option.ShowDirsOnly)
        if folder:
            self.destEdit.setText(folder)

    def _validate(self):
        if self.fileList.count() == 0:
            QMessageBox.warning(self, self.windowTitle(), _("Please add at least one file to convert."))
            return
        if not self.same_as_source():
            if not self.destEdit.text().strip():
                QMessageBox.warning(self, self.windowTitle(), _("Please select a destination folder."))
                return
            dest = Path(self.destEdit.text().strip())
            if not dest.is_dir():
                ret = QMessageBox.question(
                    self, self.windowTitle(),
                    _("The folder does not exist:\n{path}\n\nCreate it?").format(path=dest))
                if ret != QMessageBox.StandardButton.Yes:
                    return
                try:
                    dest.mkdir(parents=True, exist_ok=True)
                except OSError as e:
                    QMessageBox.critical(self, self.windowTitle(), str(e))
                    return

        # Two sources must not produce the same .sta file
        seen, clashes = {}, []
        for source, target in self.targets():
            key = str(target).lower()
            if key in seen:
                clashes.append(f"{seen[key].name} / {source.name}  ->  {target.name}")
            else:
                seen[key] = source
        if clashes:
            QMessageBox.warning(
                self, self.windowTitle(),
                _("Several selected files would produce the same .sta file. "
                  "Remove one of them or save next to the source files:") + "\n\n" + "\n".join(clashes))
            return

        if not self.same_as_source():
            self.settings.set(f"{self.mode}/dest_dir", str(self.destination()))
        self.accept()

    def same_as_source(self) -> bool:
        return self.sameAsSourceCheck.isChecked()

    def selected_files(self):
        return [Path(self.fileList.item(i).data(Qt.ItemDataRole.UserRole)) for i in range(self.fileList.count())]

    def destination(self) -> Path:
        return Path(self.destEdit.text().strip())

    def targets(self):
        out = []
        for f in self.selected_files():
            folder = f.parent if self.same_as_source() else self.destination()
            out.append((f, folder / (f.stem + ".sta")))
        return out

    def policy(self) -> str:
        return self.policyCombo.currentData()


# ============================================================================
# Main window
# ============================================================================

class ConverterWindow(QMainWindow):
    COL_FILE, COL_STATUS, COL_PAGES, COL_STAMPS, COL_DETAILS = range(5)

    def __init__(self, settings: Settings = None, parent=None):
        super().__init__(parent)
        self.settings = settings or Settings()
        set_language(self.settings["language"])
        self.qt_translator = None
        self._install_qt_translator()

        self.setWindowIcon(_app_icon())
        self.resize(940, 600)

        self.jobs = []
        self.mode = None
        self.dest = None
        self.same_as_source = False
        self.policy = POLICY_ASK
        self.running = False
        self.stop_requested = False
        self.close_when_done = False
        self.quit_confirmed = False
        self.current = -1
        self.started_at = 0.0
        self.result = None              # info on the last finished batch
        self.ask_all = None             # "overwrite" / "skip" chosen with "... all"

        self._create_actions()
        self._create_menus()
        self._create_toolbar()
        self._create_central()
        self.retranslate()
        self._set_idle()

    # ------------------------------------------------------------------ UI
    def _create_actions(self):
        self.actAlbumEasy = QAction(make_icon("albumeasy"), "", self)
        self.actAlbumEasy.setShortcut(QKeySequence("Ctrl+E"))
        self.actAlbumEasy.triggered.connect(lambda: self.start_dialog(MODE_ALBUMEASY))

        self.actFeuille = QAction(make_icon("feuille"), "", self)
        self.actFeuille.setShortcut(QKeySequence("Ctrl+F"))
        self.actFeuille.triggered.connect(lambda: self.start_dialog(MODE_FEUILLE))

        self.actConfig = QAction(make_icon("config"), "", self)
        self.actConfig.setShortcut(QKeySequence("Ctrl+,"))
        self.actConfig.triggered.connect(self.open_config)

        self.actStop = QAction(make_icon("stop"), "", self)
        self.actStop.triggered.connect(self.request_stop)

        self.actQuit = QAction(make_icon("quit"), "", self)
        self.actQuit.setShortcut(QKeySequence("Ctrl+Q"))
        self.actQuit.triggered.connect(self.close)

        self.actManual = QAction(make_icon("help"), "", self)
        self.actManual.setShortcut(QKeySequence.StandardKey.HelpContents)
        self.actManual.triggered.connect(self.open_manual)

        self.actAbout = QAction(make_icon("about"), "", self)
        self.actAbout.triggered.connect(self.about)

        self.languageGroup = QActionGroup(self)
        self.languageGroup.setExclusive(True)
        self.languageActions = {}
        for code, name in LANGUAGES:
            act = QAction(name, self, checkable=True)
            act.setData(code)
            act.triggered.connect(lambda checked, c=code: self.change_language(c))
            self.languageGroup.addAction(act)
            self.languageActions[code] = act

    def _create_menus(self):
        self.menuConversion = self.menuBar().addMenu("")
        self.menuConversion.addAction(self.actAlbumEasy)
        self.menuConversion.addAction(self.actFeuille)
        self.menuConversion.addSeparator()
        self.menuConversion.addAction(self.actStop)
        self.menuConversion.addSeparator()
        self.menuConversion.addAction(self.actQuit)

        self.menuConfig = self.menuBar().addMenu("")
        self.menuConfig.addAction(self.actConfig)
        self.menuLanguage = self.menuConfig.addMenu("")
        for act in self.languageActions.values():
            self.menuLanguage.addAction(act)

        self.menuHelp = self.menuBar().addMenu("")
        self.menuHelp.addAction(self.actManual)
        self.menuHelp.addSeparator()
        self.menuHelp.addAction(self.actAbout)

    def _create_toolbar(self):
        self.toolbar = QToolBar(self)
        self.toolbar.setObjectName("mainToolbar")
        self.toolbar.setMovable(False)
        self.toolbar.setIconSize(QSize(32, 32))
        self.toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)    # icons only, text in tooltips
        self.toolbar.addAction(self.actAlbumEasy)
        self.toolbar.addAction(self.actFeuille)
        self.toolbar.addSeparator()
        self.toolbar.addAction(self.actStop)
        self.toolbar.addSeparator()
        self.toolbar.addAction(self.actConfig)
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.toolbar.addWidget(spacer)
        self.toolbar.addAction(self.actQuit)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.toolbar)

    def _create_central(self):
        self.titleLabel = QLabel()
        font = self.titleLabel.font()
        font.setPointSize(font.pointSize() + 2)
        font.setBold(True)
        self.titleLabel.setFont(font)

        self.currentLabel = QLabel()
        self.currentLabel.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self.progress = QProgressBar()
        self.progress.setTextVisible(True)

        self.stopButton = QPushButton(make_icon("stop"), "")
        self.stopButton.clicked.connect(self.request_stop)

        progress_row = QHBoxLayout()
        progress_row.addWidget(self.progress, 1)
        progress_row.addWidget(self.stopButton)

        self.table = QTableWidget(0, 5)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        header = self.table.horizontalHeader()
        for col in (self.COL_FILE, self.COL_STATUS, self.COL_PAGES, self.COL_STAMPS):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(self.COL_DETAILS, QHeaderView.ResizeMode.Stretch)
        self.table.cellDoubleClicked.connect(self.show_details)

        self.summaryLabel = QLabel()
        self.summaryLabel.setWordWrap(True)
        self.summaryLabel.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self.openFolderButton = QPushButton(make_icon("folder"), "")
        self.openFolderButton.clicked.connect(self.open_destination)
        self.reportButton = QPushButton(make_icon("report"), "")
        self.reportButton.clicked.connect(self.save_report)

        bottom_row = QHBoxLayout()
        bottom_row.addWidget(self.summaryLabel, 1)
        bottom_row.addWidget(self.reportButton)
        bottom_row.addWidget(self.openFolderButton)

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.addWidget(self.titleLabel)
        layout.addWidget(self.currentLabel)
        layout.addLayout(progress_row)
        layout.addWidget(self.table, 1)
        layout.addLayout(bottom_row)
        self.setCentralWidget(central)

    def retranslate(self):
        """(Re)apply every text of the window in the current language."""
        self.setWindowTitle(_("Stamp Album - Album converter"))
        self.menuConversion.setTitle(_("&Conversion"))
        self.menuConfig.setTitle(_("Con&figuration"))
        self.menuLanguage.setTitle(_("&Language"))
        self.menuHelp.setTitle(_("&Help"))
        self.toolbar.setWindowTitle(_("Toolbar"))

        texts = [
            (self.actAlbumEasy, _("Convert &AlbumEasy files..."), _("AlbumEasy"),
             _("Convert AlbumEasy description files (.txt) to Stamp Album albums")),
            (self.actFeuille, _("Convert &Feuille Album 4 files..."), _("Feuille Album 4"),
             _("Convert Feuille Album 4 Excel albums (.xls) to Stamp Album albums")),
            (self.actConfig, _("&Settings..."), _("Configuration"),
             _("Language and conversion options")),
            (self.actStop, _("S&top conversion"), _("Stop"),
             _("Stop after the current file (albums already converted are kept)")),
            (self.actQuit, _("&Quit"), _("Quit"), _("Quit the album converter")),
            (self.actManual, _("User &manual"), _("User manual"), _("Open the user manual (PDF)")),
            (self.actAbout, _("&About..."), _("About"), _("About the album converter")),
        ]
        for act, menu_text, short, tip in texts:
            act.setText(menu_text)
            act.setIconText(short)
            act.setToolTip(f"{short} - {tip}" if short != tip else tip)
            act.setStatusTip(tip)
        for code, act in self.languageActions.items():
            act.setChecked(code == _current_language)

        self.stopButton.setText(_("Stopping...") if (self.running and self.stop_requested) else _("&Stop"))
        self.openFolderButton.setText(_("&Open destination folder"))
        self.reportButton.setText(_("Save &report..."))
        self.table.setHorizontalHeaderLabels([_("File"), _("Status"), _("Pages"), _("Stamps"), _("Details")])
        for row in range(len(self.jobs)):
            self._refresh_row(row)
        self._update_state_texts()

    def _update_state_texts(self):
        if self.running:
            return                                  # updated live during the batch
        if not self.jobs:
            self.titleLabel.setText(_("No conversion in progress"))
            self.currentLabel.setText(_("Use the Conversion menu or the toolbar to choose the albums to convert."))
            self.summaryLabel.setText("")
            self.progress.setFormat("")
            return
        r = self.result or {}
        counts = {s: sum(1 for j in self.jobs if j.status == s) for s in STATUS_COLORS}
        converted = counts[STATUS_OK] + counts[STATUS_WARN]
        self.titleLabel.setText(_("Conversion stopped") if r.get("stopped") else _("Conversion finished"))
        if self.same_as_source:
            where = _("next to the source files")
        else:
            where = str(self.dest)
        self.currentLabel.setText(_("{n} album(s) saved in {dest} ({secs:.0f} s)").format(
            n=converted, dest=where, secs=r.get("elapsed", 0.0)))
        first = _("{n} converted").format(n=converted)
        if counts[STATUS_WARN]:
            first += " (" + _("{n} with warnings").format(n=counts[STATUS_WARN]) + ")"
        parts = [first]
        if counts[STATUS_ERROR]:
            parts.append(_("{n} failed").format(n=counts[STATUS_ERROR]))
        if counts[STATUS_SKIPPED]:
            parts.append(_("{n} skipped").format(n=counts[STATUS_SKIPPED]))
        if counts[STATUS_STOPPED]:
            parts.append(_("{n} not converted").format(n=counts[STATUS_STOPPED]))
        text = ", ".join(parts) + ". " + _("Double-click a line for details.")
        if r.get("report"):
            text += "\n" + _("Report saved: {path}").format(path=r["report"])
        elif r.get("report_error"):
            text += "\n" + _("The report could not be saved: {error}").format(error=r["report_error"])
        self.summaryLabel.setText(text)
        self.progress.setFormat(_("%v / %m files"))

    def _set_idle(self):
        self.running = False
        for act in (self.actAlbumEasy, self.actFeuille, self.actConfig):
            act.setEnabled(True)
        self.menuLanguage.setEnabled(True)
        self.actStop.setEnabled(False)
        self.stopButton.setEnabled(False)
        self.stopButton.setText(_("&Stop"))
        has_jobs = bool(self.jobs)
        self.openFolderButton.setEnabled(has_jobs and self.dest is not None)
        self.reportButton.setEnabled(has_jobs)
        if not has_jobs:
            self.progress.setRange(0, 1)
            self.progress.setValue(0)
        self._update_state_texts()

    # ------------------------------------------------------------------ language & settings
    def _install_qt_translator(self):
        """Qt's own texts (standard buttons of the file dialogs...) in the chosen language."""
        app = QApplication.instance()
        if self.qt_translator is not None:
            app.removeTranslator(self.qt_translator)
            self.qt_translator = None
        translator = QTranslator(app)
        if translator.load(QLocale(_current_language), "qtbase", "_",
                           QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)):
            app.installTranslator(translator)
            self.qt_translator = translator

    def change_language(self, lang):
        if self.running or lang not in dict(LANGUAGES):
            return
        self.settings.update({"language": lang})
        set_language(lang)
        self._install_qt_translator()
        self.retranslate()

    def open_config(self):
        if self.running:
            return
        dlg = ConfigDialog(self.settings, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        values = dlg.values()
        language_changed = values["language"] != self.settings["language"]
        self.settings.update(values)
        if language_changed:
            set_language(values["language"])
            self._install_qt_translator()
            self.retranslate()

    # ------------------------------------------------------------------ help
    MANUALS = {
        "fr": "AlbumConverter Manuel utilisateur.pdf",
        "en": "AlbumConverter User Manual.pdf",
    }

    def manual_path(self):
        """The manual in the current language, otherwise the one in the other language."""
        names = [self.MANUALS.get(_current_language)] + [n for c, n in self.MANUALS.items()
                                                          if c != _current_language]
        for folder in _resource_dirs("Help"):
            for name in names:
                if name and (folder / name).is_file():
                    return folder / name
        return None

    def open_manual(self):
        path = self.manual_path()
        if path is None:
            folders = _resource_dirs("Help") or [_app_dir().parent / "Help"]
            QMessageBox.warning(self, _("User manual"),
                                _("The user manual was not found:") + "\n" +
                                str(folders[0] / self.MANUALS.get(_current_language, self.MANUALS["en"])))
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def about(self):
        from PyQt6.QtCore import PYQT_VERSION_STR, QT_VERSION_STR
        dlg = QDialog(self)
        dlg.setWindowTitle(_("About the album converter"))
        icon = QLabel()
        icon.setPixmap(_app_icon().pixmap(64, 64))
        icon.setAlignment(Qt.AlignmentFlag.AlignTop)

        text = QLabel()
        text.setWordWrap(True)
        text.setTextFormat(Qt.TextFormat.RichText)
        text.setOpenExternalLinks(True)
        text.setText(
            "<h3>" + _("Stamp Album - Album converter") + "</h3>"
            + "<p>" + _("Version {version}").format(version=APP_VERSION) + "</p>"
            + "<p>" + _("Converts stamp albums made with other programs into Stamp Album albums (.sta), "
                        "one file or hundreds at a time:") + "</p><ul>"
            + "<li>" + _("AlbumEasy description files (.txt), with their stamp pictures;") + "</li>"
            + "<li>" + _("Feuille Album 4 Excel albums (.xls), with the pictures they contain.") + "</li></ul>"
            + "<p>" + _("Each album is saved as soon as it is converted. Files that cannot be converted "
                        "are reported with the reason, and a report can be saved.") + "</p>"
            + "<p>" + _("The converted albums open in Stamp Album like any other album and can then be "
                        "edited and printed.") + "</p>"
            + "<p><b>" + _("Author:") + "</b> " + APP_AUTHOR + "<br>"
            + "© 2026 " + APP_AUTHOR + "</p>"
            + "<p><small>Python {py} · PyQt {pyqt} · Qt {qt}</small></p>".format(
                py=sys.version.split()[0], pyqt=PYQT_VERSION_STR, qt=QT_VERSION_STR))

        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        bb.button(QDialogButtonBox.StandardButton.Close).setText(_("Close"))
        bb.rejected.connect(dlg.reject)

        row = QHBoxLayout()
        row.addWidget(icon)
        row.addSpacing(10)
        row.addWidget(text, 1)
        layout = QVBoxLayout(dlg)
        layout.addLayout(row)
        layout.addWidget(bb)
        # Fixed text width: the window then takes the height the whole text needs
        text.setFixedWidth(420)
        layout.setSizeConstraint(QLayout.SizeConstraint.SetFixedSize)
        dlg.exec()

    def batch_options(self) -> Options:
        return Options(border_style=self.settings["border_style"],
                       author=self.settings["author"],
                       album_language=self.settings["album_language"],
                       image_dirs=list(self.settings["image_dirs"]))

    # ------------------------------------------------------------------ start
    def start_dialog(self, mode):
        if self.running:
            return
        dlg = ConvertDialog(mode, self.settings, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        self.start(mode, dlg.targets(), None if dlg.same_as_source() else dlg.destination(), dlg.policy())

    def start(self, mode, targets, dest, policy):
        """targets: list of (source, target .sta); dest: destination folder or None
        when each album is saved next to its source file."""
        self.mode = mode
        self.same_as_source = dest is None
        if dest is None:
            folders = [str(s.parent) for s, _t in targets]
            try:
                dest = Path(os.path.commonpath(folders))
            except ValueError:                      # different drives (Windows)
                dest = Path(folders[0])
        self.dest = dest
        self.policy = policy
        self.options = self.batch_options()
        self.ask_all = None
        self.jobs = [Job(s, t) for s, t in targets]
        self.stop_requested = False
        self.running = True
        self.result = None
        self.current = -1
        self.started_at = time.monotonic()

        self.table.setRowCount(0)
        for job in self.jobs:
            row = self.table.rowCount()
            self.table.insertRow(row)
            item = QTableWidgetItem(job.source.name)
            item.setToolTip(str(job.source))
            self.table.setItem(row, self.COL_FILE, item)
            for col in (self.COL_STATUS, self.COL_PAGES, self.COL_STAMPS, self.COL_DETAILS):
                self.table.setItem(row, col, QTableWidgetItem(""))
            self._refresh_row(row)

        for act in (self.actAlbumEasy, self.actFeuille, self.actConfig):
            act.setEnabled(False)
        self.menuLanguage.setEnabled(False)
        self.actStop.setEnabled(True)
        self.stopButton.setEnabled(True)
        self.stopButton.setText(_("&Stop"))
        self.openFolderButton.setEnabled(True)
        self.reportButton.setEnabled(False)
        if self.same_as_source:
            self.titleLabel.setText(_("Converting {kind} files (saved next to the source files)").format(
                kind=MODE_NAMES[mode]))
        else:
            self.titleLabel.setText(_("Converting {kind} files to {dest}").format(kind=MODE_NAMES[mode], dest=dest))
        self.summaryLabel.setText("")
        self.progress.setRange(0, len(self.jobs))
        self.progress.setValue(0)
        self.progress.setFormat(_("%v / %m files"))
        QTimer.singleShot(0, self._next)

    # ------------------------------------------------------------------ run
    def _existing_decision(self, job) -> str:
        """What to do with a .sta file that already exists."""
        if self.policy != POLICY_ASK:
            return self.policy
        if self.ask_all:
            return self.ask_all
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Question)
        box.setWindowTitle(_("File already exists"))
        box.setText(_("{name} already exists in {folder}.").format(name=job.target.name, folder=job.target.parent))
        box.setInformativeText(_("What do you want to do?"))
        b_replace = box.addButton(_("Replace"), QMessageBox.ButtonRole.AcceptRole)
        b_replace_all = box.addButton(_("Replace all"), QMessageBox.ButtonRole.AcceptRole)
        b_rename = box.addButton(_("Rename"), QMessageBox.ButtonRole.ActionRole)
        b_skip = box.addButton(_("Skip"), QMessageBox.ButtonRole.RejectRole)
        b_skip_all = box.addButton(_("Skip all"), QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(b_rename)
        box.setEscapeButton(b_skip)
        box.exec()
        clicked = box.clickedButton()
        if clicked is b_replace_all:
            self.ask_all = POLICY_OVERWRITE
        elif clicked is b_skip_all:
            self.ask_all = POLICY_SKIP
        return {b_replace: POLICY_OVERWRITE, b_replace_all: POLICY_OVERWRITE, b_rename: POLICY_RENAME,
                b_skip: POLICY_SKIP, b_skip_all: POLICY_SKIP}.get(clicked, POLICY_SKIP)

    def _next(self):
        self.current += 1
        if self.stop_requested or self.current >= len(self.jobs):
            self._finish()
            return

        job = self.jobs[self.current]
        row = self.current
        self.table.scrollToItem(self.table.item(row, 0))

        if job.target.exists():
            decision = self._existing_decision(job)
            if self.stop_requested:                         # Stop clicked while the question was open
                self._finish()
                return
            if decision == POLICY_SKIP:
                job.status = STATUS_SKIPPED
                job.summary = Msg("{name} already exists", name=job.target.name)
                self._refresh_row(row)
                self._advance()
                return
            if decision == POLICY_RENAME:
                job.target = unique_target(job.target, [j.target for j in self.jobs])

        job.status = STATUS_RUNNING
        self._refresh_row(row)
        self.currentLabel.setText(_("File {i} of {n}: {name}").format(
            i=self.current + 1, n=len(self.jobs), name=job.source.name))
        QApplication.processEvents()

        def on_page(n, job=job):
            self.currentLabel.setText(_("File {i} of {n}: {name} - page {page}").format(
                i=self.current + 1, n=len(self.jobs), name=job.source.name, page=n))
            # Keep the window responsive (Stop button, repaint) during a long file
            QApplication.processEvents()

        try:
            QApplication.setOverrideCursor(Qt.CursorShape.BusyCursor)
            job.pages, job.stamps, warnings = convert_file(self.mode, job.source, job.target,
                                                           self.options, on_page)
            job.details = warnings
            job.status = STATUS_WARN if warnings else STATUS_OK
            if warnings:
                job.summary = Msg("{n} warning(s) - {first}", n=len(warnings), first=warnings[0])
            else:
                job.summary = Msg("Saved as {name}", name=job.target.name)
        except ConversionError as e:
            job.status = STATUS_ERROR
            job.summary = e.msg
            job.details = [e.msg]
        except Exception as e:
            job.status = STATUS_ERROR
            job.summary = str(e) or e.__class__.__name__
            job.details = [job.summary, "", traceback.format_exc()]
        finally:
            QApplication.restoreOverrideCursor()

        self._refresh_row(row)
        self._advance()

    def _advance(self):
        self.progress.setValue(self.current + 1)
        QTimer.singleShot(0, self._next)

    def _finish(self):
        for i, job in enumerate(self.jobs):
            if job.status in (STATUS_PENDING, STATUS_RUNNING):
                job.status = STATUS_STOPPED
                self._refresh_row(i)
        self.progress.setValue(sum(1 for j in self.jobs if j.status != STATUS_STOPPED))

        self.result = {
            "stopped": self.stop_requested and any(j.status == STATUS_STOPPED for j in self.jobs),
            "elapsed": time.monotonic() - self.started_at,
        }
        if self.settings["auto_report"]:
            path = self.dest / time.strftime("conversion_%Y%m%d_%H%M%S.txt")
            try:
                path.write_text(self.report_text(), encoding="utf-8")
                self.result["report"] = str(path)
            except OSError as e:
                self.result["report_error"] = str(e)
        self._set_idle()

        if self.close_when_done:
            self.quit_confirmed = True
            self.close()
            return

        failed = [j for j in self.jobs if j.status == STATUS_ERROR]
        if failed:
            lines = [f"• {j.source.name}: {j.summary}" for j in failed[:15]]
            if len(failed) > 15:
                lines.append("…")
            QMessageBox.warning(self, self.titleLabel.text(),
                                _("{n} file(s) could not be converted:").format(n=len(failed))
                                + "\n\n" + "\n".join(lines))

    def request_stop(self):
        if not self.running or self.stop_requested:
            return
        self.stop_requested = True
        self.actStop.setEnabled(False)
        self.stopButton.setEnabled(False)
        self.stopButton.setText(_("Stopping..."))
        self.currentLabel.setText(self.currentLabel.text() + "  " + _("(stopping after the current file)"))

    # ------------------------------------------------------------------ results
    def _refresh_row(self, row):
        job = self.jobs[row]
        status_item = self.table.item(row, self.COL_STATUS)
        status_item.setText(_status_text(job.status))
        color = STATUS_COLORS.get(job.status)
        status_item.setForeground(color if color else self.palette().text().color())
        font = status_item.font()
        font.setBold(job.status in (STATUS_ERROR, STATUS_RUNNING))
        status_item.setFont(font)

        done = job.status in (STATUS_OK, STATUS_WARN)
        self.table.item(row, self.COL_PAGES).setText(str(job.pages) if done else "")
        self.table.item(row, self.COL_STAMPS).setText(str(job.stamps) if done else "")
        details = self.table.item(row, self.COL_DETAILS)
        details.setText(str(job.summary))
        details.setToolTip("\n".join(str(d) for d in job.details[:30]) if job.details else str(job.summary))
        for col in (self.COL_PAGES, self.COL_STAMPS):
            self.table.item(row, col).setTextAlignment(Qt.AlignmentFlag.AlignCenter)

    def show_details(self, row, _col=0):
        if not (0 <= row < len(self.jobs)):
            return
        job = self.jobs[row]
        dlg = QDialog(self)
        dlg.setWindowTitle(job.source.name)
        dlg.resize(640, 380)
        text = QPlainTextEdit()
        text.setReadOnly(True)
        lines = [_("Source: {path}").format(path=job.source),
                 _("Destination: {path}").format(path=job.target),
                 _("Status: {status}").format(status=_status_text(job.status))]
        if job.status in (STATUS_OK, STATUS_WARN):
            lines.append(_("{pages} page(s), {stamps} stamp(s)").format(pages=job.pages, stamps=job.stamps))
        lines.append("")
        lines += [str(d) for d in job.details] or ([str(job.summary)] if job.summary else [])
        text.setPlainText("\n".join(lines))
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        bb.button(QDialogButtonBox.StandardButton.Close).setText(_("Close"))
        bb.rejected.connect(dlg.reject)
        layout = QVBoxLayout(dlg)
        layout.addWidget(text)
        layout.addWidget(bb)
        dlg.exec()

    def open_destination(self):
        if self.dest is not None:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.dest)))

    def report_text(self) -> str:
        dest = _("next to the source files") if self.same_as_source else str(self.dest)
        lines = [_("Album conversion report"), time.strftime("%Y-%m-%d %H:%M:%S"),
                 _("Type: {kind}").format(kind=MODE_NAMES.get(self.mode, "")),
                 _("Destination: {path}").format(path=dest), ""]
        for job in self.jobs:
            lines.append(f"[{_status_text(job.status)}] {job.source}")
            if job.status in (STATUS_OK, STATUS_WARN):
                lines.append("    " + _("{pages} page(s), {stamps} stamp(s)").format(
                    pages=job.pages, stamps=job.stamps) + f" -> {job.target}")
            details = job.details if job.status != STATUS_ERROR else job.details[:1]
            for d in details or ([job.summary] if job.summary else []):
                if str(d):
                    lines.append("    " + str(d))
        return "\n".join(lines) + "\n"

    def save_report(self):
        start = str((self.dest or Path.home()) / time.strftime("conversion_%Y%m%d_%H%M%S.txt"))
        name, _filter = QFileDialog.getSaveFileName(
            self, _("Save report"), start, _("Text files (*.txt)"),
            options=QFileDialog.Option.DontUseNativeDialog)
        if name:
            try:
                Path(name).write_text(self.report_text(), encoding="utf-8")
            except OSError as e:
                QMessageBox.critical(self, _("Save report"), str(e))

    def closeEvent(self, event):
        if self.running:
            ret = QMessageBox.question(
                self, self.windowTitle(),
                _("A conversion is in progress. Stop it and quit?\n"
                  "Albums already converted are kept."))
            if ret == QMessageBox.StandardButton.Yes:
                self.close_when_done = True
                self.request_stop()
            event.ignore()
            return
        if not self.quit_confirmed:
            ret = QMessageBox.question(self, _("Quit"), _("Do you want to quit the album converter?"))
            if ret != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
        event.accept()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("AlbumConverter")
    app.setStyle('Windows')
    app.setWindowIcon(_app_icon())
    win = ConverterWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
