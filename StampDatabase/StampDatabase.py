"""
StampDatabase Application
-------------------------
A standalone desktop database administration application for managing
country-specific stamp catalogues used by StampAlbum and StampCatalogue.

Author: Boris du Reau
Year: 2026
"""

import sys
import sqlite3
from pathlib import Path
import shutil  # Requis pour la méthode handle_dropped_image
from DropImageLabel import DropImageLabel

from PyQt6 import QtGui
from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QComboBox, QLabel, QTableWidget, QTableWidgetItem, QPushButton,
    QHeaderView, QLineEdit, QMessageBox, QFileDialog, QGroupBox,
    QFormLayout, QTextEdit, QSplitter, QDialog, QToolBar
)
from PyQt6.QtGui import QPixmap, QKeySequence, QDesktopServices, QUndoStack, QIcon, QAction

# Modules de support découpés
from DatabaseAdapter import CountryDatabaseAdapter, test_ms_access_support
from UndoCommands import UpdateStampCommand, AddStampCommand, DeleteStampsCommand
from SDDialogs import DatabaseInfoDialog, CreateDatabaseDialog
from Delegates import TypeDelegate
from SDAboutDlg import SDAboutDlg
import ImportExport
import StampDatabaseConfig
import translateXLSXDatabase

# Localization setup
import gettext
from SDAppLanguage import get_language

gettext.find("StampDatabase")
translate = gettext.translation(
    'StampDatabase', localedir='locale', languages=[get_language()], fallback=True
)
translate.install()
_ = translate.gettext


class MainWindow(QMainWindow):
    """Main Window for StampDatabase administration tool."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle(_("StampDatabase - Stamp Catalogue Administrator"))
        self.resize(1300, 850)

        self.base_dir = self._get_app_dir()
        self.db_dir = self.base_dir / "Databases"
        self.config_manager = StampDatabaseConfig.AppConfigManager(self.base_dir / "StampDatabase.cfg")
        self.current_db_type = self.config_manager.db_type
        self.db_adapter = None
        self.current_country = None
        self.is_dirty = False

        self.images_dir = self.base_dir / "Images"

        icon_path = self.images_dir / "StampDB.png"
        if icon_path.exists():
            self.setWindowIcon(QtGui.QIcon(str(icon_path)))
        else:
            self.setWindowIcon(QtGui.QIcon('StampDB.png'))

        self.undo_stack = QUndoStack(self)
        self.undo_stack.cleanChanged.connect(self._update_dirty_state)

        self.available_countries = self._detect_available_countries()

        self._init_ui()
        self._init_menubar()
        self._init_toolbar()
        self._load_country_list()

    def handle_dropped_image(self, source_image_path: Path):
        """Prend en charge l'image glissée-déposée, la renomme et la copie."""
        stamp_nbr = self.edit_nbr.text().strip()
        if not stamp_nbr:
            QMessageBox.warning(
                self,
                _("Warning"),
                _("Please select or specify a stamp record number before dropping an image.")
            )
            return

        if not self.current_country:
            QMessageBox.warning(
                self,
                _("Warning"),
                _("No active country database selected.")
            )
            return

        stamp_type = self.edit_type.currentText().strip()
        stamp_sub_nbr = self.edit_sub_nbr.text().strip()

        # 1. Générer le nom cible normalisé T01-...
        target_filename = self.getPhotoName(stamp_nbr, stamp_type, stamp_sub_nbr)

        # 2. Déterminer le dossier de destination (dossier du pays dans Images/)
        target_dir = self.base_dir / "Photos" / str(self.current_country)
        target_dir.mkdir(parents=True, exist_ok=True)
        target_file_path = target_dir / target_filename

        # 3. Vérifier si le fichier existe déjà (ou sous une casse différente)
        existing_file = self._find_file_case_insensitive(target_dir, target_filename)

        if existing_file and existing_file.exists():
            reply = QMessageBox.question(
                self,
                _("Confirm Overwrite"),
                _(f"An image for this stamp already exists ({existing_file.name}).\nDo you want to overwrite it?"),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
            destination_path = existing_file
        else:
            destination_path = target_file_path

        # 4. Copier et convertir si nécessaire en JPG
        try:
            pixmap = QPixmap(str(source_image_path))
            if pixmap.isNull():
                # En cas de format non chargeable par Qt, simple copie brute
                shutil.copy2(source_image_path, destination_path)
            else:
                # Sauvegarde au format standard JPEG haute qualité
                pixmap.save(str(destination_path), "JPG", quality=95)

            # 5. Recharger immédiatement l'affichage
            self._load_stamp_image(stamp_nbr, stamp_type, stamp_sub_nbr)

            QMessageBox.information(
                self,
                _("Success"),
                _(f"Image saved successfully as:\n{target_filename}")
            )
        except Exception as e:
            QMessageBox.critical(
                self,
                _("Error"),
                f"{_('Failed to save image:')}\n{str(e)}"
            )

    def _get_app_dir(self) -> Path:
        """Détermine le répertoire racine de l'application."""
        if getattr(sys, 'frozen', False):
            return Path(sys.executable).resolve().parent
        else:
            script_dir = Path(__file__).resolve().parent
            parent_dir = script_dir.parent
            if any((parent_dir / folder).exists() for folder in ["Databases", "Images", "Photos"]):
                return parent_dir
            return script_dir

    def _detect_available_countries(self):
        """Detect country Databases in Databases/ folder."""
        if not self.db_dir.exists():
            return []
        ext = ".db" if self.current_db_type == "sqlite" else ".mdb"
        return sorted([f.stem for f in self.db_dir.glob(f"*{ext}") if f.stem not in ["master", "collections"]])

    def show_access_warning_popup(self):
        """Display warning popup when MS Access is not configured or drivers are missing."""
        QMessageBox.warning(
            self,
            _("MS Access Configuration Error"),
            _("<b>Microsoft Access is not configured properly or drivers are missing.</b><br><br>"
              "Please refer to the application documentation to install the required "
              "64-bit ODBC Access drivers (<code>accessdatabaseengine_X64.exe /quiet</code>).<br><br>"
              "MS Access features have been disabled. The application will revert to SQLite mode.")
        )

    def _init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)

        # Country Header Bar
        country_box = QGroupBox(_("Database Selection"))
        country_layout = QHBoxLayout()
        country_layout.addWidget(QLabel(_("Active Country Database:")))
        self.combo_country = QComboBox()
        self.combo_country.currentIndexChanged.connect(self._on_country_changed)
        country_layout.addWidget(self.combo_country, stretch=1)
        country_layout.addStretch(2)
        country_box.setLayout(country_layout)
        main_layout.addWidget(country_box)

        # Filter Bar
        filter_box = QGroupBox(_("Catalogue Filters"))
        filter_layout = QHBoxLayout()

        filter_layout.addWidget(QLabel(_("Type:")))
        self.combo_type = QComboBox()
        self.combo_type.setMinimumWidth(250)
        self.combo_type.currentTextChanged.connect(self._refresh_table)
        filter_layout.addWidget(self.combo_type, stretch=3)

        filter_layout.addWidget(QLabel(_("Year:")))
        self.combo_year = QComboBox()
        self.combo_year.currentTextChanged.connect(self._refresh_table)
        filter_layout.addWidget(self.combo_year, stretch=1)

        filter_layout.addWidget(QLabel(_("Catalog N°:")))
        self.edit_search_nbr = QLineEdit()
        self.edit_search_nbr.setPlaceholderText(_("e.g. 154..."))
        self.edit_search_nbr.setMaxLength(10)
        self.edit_search_nbr.setMaximumWidth(100)
        self.edit_search_nbr.textChanged.connect(self._refresh_table)
        filter_layout.addWidget(self.edit_search_nbr, stretch=1)

        filter_box.setLayout(filter_layout)
        main_layout.addWidget(filter_box)

        # Main Splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Table
        self.table = QTableWidget()
        self.table.setItemDelegateForColumn(2, TypeDelegate(self.table, main_window=self))
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            _("Yvert N°"), _("Year"), _("Type"),
            _("Value / Color"), _("Description 1"), _("Description")
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self.table.setSortingEnabled(True)
        self.table.itemSelectionChanged.connect(self._on_stamp_selected)
        splitter.addWidget(self.table)

        # Right Panel
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)

        self.img_label = DropImageLabel(self)
        self.img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.img_label.setFixedSize(200, 200)
        self.img_label.setStyleSheet(
            "border: 2px dashed #a0aec0; background: #f7fafc; border-radius: 6px;"
        )
        self.img_label.setToolTip(_("Drag and drop an image file here to assign it to the current stamp."))
        right_layout.addWidget(self.img_label, alignment=Qt.AlignmentFlag.AlignCenter)

        editor_box = QGroupBox(_("Stamp Catalogue Record Editor"))
        form = QFormLayout()

        self.edit_nbr = QLineEdit()
        self.edit_sub_nbr = QLineEdit()
        self.edit_year = QLineEdit()
        self.edit_type = QComboBox()
        self.edit_type.setEditable(True)
        self.edit_valcolor = QLineEdit()

        self.edit_desc1 = QTextEdit()
        self.edit_desc1.setMaximumHeight(50)
        self.edit_desc = QTextEdit()
        self.edit_desc.setMaximumHeight(50)

        self.edit_width = QLineEdit()
        self.edit_height = QLineEdit()

        self.edit_sequence = QLineEdit()
        self.edit_sequence.setReadOnly(True)
        self.edit_sequence.setStyleSheet("background-color: #edf2f7; color: #718096;")

        self.edit_ascii_seq = QLineEdit()
        self.edit_ascii_seq.setReadOnly(True)
        self.edit_ascii_seq.setStyleSheet("background-color: #edf2f7; color: #718096;")

        form.addRow(_("Yvert N°:"), self.edit_nbr)
        form.addRow(_("Sub N° / Variant:"), self.edit_sub_nbr)
        form.addRow(_("Year:"), self.edit_year)
        form.addRow(_("Category / Type:"), self.edit_type)
        form.addRow(_("Value / Color:"), self.edit_valcolor)
        form.addRow(_("Description 1:"), self.edit_desc1)
        form.addRow(_("Description:"), self.edit_desc)
        form.addRow(_("Width (mm):"), self.edit_width)
        form.addRow(_("Height (mm):"), self.edit_height)
        form.addRow(_("Sequence:"), self.edit_sequence)
        form.addRow(_("ASCII Sequence:"), self.edit_ascii_seq)

        btn_apply = QPushButton(_("Apply Record Modification"))
        btn_apply.setStyleSheet("background-color: #1d6f42; color: white; font-weight: bold;")
        btn_apply.clicked.connect(self._on_apply_record_edit)
        form.addRow(btn_apply)

        editor_box.setLayout(form)
        right_layout.addWidget(editor_box)

        btn_layout = QHBoxLayout()
        btn_add = QPushButton(_("Add Stamp Record"))
        btn_add.setStyleSheet("background-color: #2b6cb0; color: white; font-weight: bold;")
        btn_add.clicked.connect(self._on_add_stamp_record)
        btn_layout.addWidget(btn_add)

        btn_delete = QPushButton(_("Delete Stamp Record(s)"))
        btn_delete.setStyleSheet("background-color: #c53030; color: white; font-weight: bold;")
        btn_delete.clicked.connect(self._on_delete_stamp_record)
        btn_layout.addWidget(btn_delete)

        right_layout.addLayout(btn_layout)
        splitter.addWidget(right_panel)
        splitter.setSizes([650, 450])
        main_layout.addWidget(splitter)

    def _init_menubar(self):
        menubar = self.menuBar()

        # File
        file_menu = menubar.addMenu(_("&File"))
        self.act_create_db = QAction(_("Create New Empty SQLite DB..."), self)
        self.act_create_db.setIcon(QIcon(str(self.base_dir / "Images" / "database_add.png")))
        self.act_create_db.triggered.connect(self.create_new_sqlite_db)
        file_menu.addAction(self.act_create_db)

        self.act_save_db = QAction(_("Save Changes"), self)
        self.act_save_db.setIcon(QIcon(str(self.base_dir / "Images" / "save.png")))
        self.act_save_db.setShortcut(QKeySequence.StandardKey.Save)
        self.act_save_db.triggered.connect(self.save_changes)
        file_menu.addAction(self.act_save_db)
        file_menu.addSeparator()

        self.act_db_info = QAction(_("Current Database Info..."), self)
        self.act_db_info.triggered.connect(self.open_db_info)
        file_menu.addAction(self.act_db_info)
        file_menu.addSeparator()

        self.act_convert_access = QAction(_("Import MS Access DB to SQLite..."), self)
        self.act_convert_access.triggered.connect(self.import_ms_access_to_sqlite)
        file_menu.addAction(self.act_convert_access)

        self.act_import_csv = QAction(_("Import CSV..."), self)
        self.act_import_csv.setIcon(QIcon(str(self.base_dir / "Images" / "import_csv.png")))
        self.act_import_csv.triggered.connect(self.import_csv)
        file_menu.addAction(self.act_import_csv)

        self.act_export_csv = QAction(_("Export CSV..."), self)
        self.act_export_csv.setIcon(QIcon(str(self.base_dir / "Images" / "export_to_csv.png")))
        self.act_export_csv.triggered.connect(self.export_csv)
        file_menu.addAction(self.act_export_csv)
        file_menu.addSeparator()

        self.act_import_xlsx = QAction(_("Import Excel (XLSX)..."), self)
        self.act_import_xlsx.setIcon(QIcon(str(self.base_dir / "Images" / "import_xlsx.png")))
        self.act_import_xlsx.triggered.connect(self.import_xlsx)
        file_menu.addAction(self.act_import_xlsx)

        self.act_export_xlsx = QAction(_("Export Excel (XLSX)..."), self)
        self.act_export_xlsx.setIcon(QIcon(str(self.base_dir / "Images" / "export_to_xlsx.png")))
        self.act_export_xlsx.triggered.connect(self.export_xlsx)
        file_menu.addAction(self.act_export_xlsx)
        file_menu.addSeparator()

        self.act_exit_app = QAction(_("&Exit"), self)
        self.act_exit_app.setIcon(QIcon(str(self.base_dir / "Images" / "exit.png")))
        self.act_exit_app.setShortcut(QKeySequence.StandardKey.Quit)
        self.act_exit_app.triggered.connect(self.close)
        file_menu.addAction(self.act_exit_app)

        # Edit
        edit_menu = menubar.addMenu(_("&Edit"))
        self.act_undo = QAction(_("&Undo"), self)
        self.act_undo.setIcon(QIcon(str(self.base_dir / "Images" / "undo.png")))
        self.act_undo.setShortcut(QKeySequence.StandardKey.Undo)
        self.act_undo.setEnabled(self.undo_stack.canUndo())
        self.act_undo.triggered.connect(self.undo_stack.undo)
        self.undo_stack.canUndoChanged.connect(self.act_undo.setEnabled)
        edit_menu.addAction(self.act_undo)

        self.act_redo = QAction(_("&Redo"), self)
        self.act_redo.setIcon(QIcon(str(self.base_dir / "Images" / "redo.png")))
        self.act_redo.setShortcut(QKeySequence.StandardKey.Redo)
        self.act_redo.setEnabled(self.undo_stack.canRedo())
        self.act_redo.triggered.connect(self.undo_stack.redo)
        self.undo_stack.canRedoChanged.connect(self.act_redo.setEnabled)
        edit_menu.addAction(self.act_redo)
        edit_menu.addSeparator()

        self.act_select_all = QAction(_("Select All"), self)
        self.act_select_all.setShortcut(QKeySequence.StandardKey.SelectAll)
        self.act_select_all.triggered.connect(self.table.selectAll)
        edit_menu.addAction(self.act_select_all)

        # Utilities
        utilities_menu = menubar.addMenu(_("&Utilities"))
        self.act_translate_xlsx = QAction(_("Translate XLSX File..."), self)
        self.act_translate_xlsx.setIcon(QIcon(str(self.base_dir / "Images" / "translate_xlsx.png")))
        self.act_translate_xlsx.triggered.connect(self.translate_xlsx_catalogue)
        utilities_menu.addAction(self.act_translate_xlsx)

        # Config
        config_menu = menubar.addMenu(_("&Config"))
        self.act_config = QAction(_("Setup Application..."), self)
        self.act_config.setIcon(QIcon(str(self.base_dir / "Images" / "config.png")))
        self.act_config.triggered.connect(self.open_config)
        config_menu.addAction(self.act_config)

        # Help
        help_menu = menubar.addMenu(_("&Help"))
        self.act_help = QAction(_("User Manual"), self)
        self.act_help.setIcon(QIcon(str(self.base_dir / "Images" / "help.png")))
        self.act_help.triggered.connect(self.open_manual)
        help_menu.addAction(self.act_help)

        self.act_about = QAction(_("About StampDatabase"), self)
        self.act_about.setIcon(QIcon(str(self.base_dir / "Images" / "about.png")))
        self.act_about.triggered.connect(self.open_about)
        help_menu.addAction(self.act_about)

    def _init_toolbar(self):
        toolbar = QToolBar(_("Main Toolbar"))
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        toolbar.addAction(self.act_create_db)
        toolbar.addAction(self.act_save_db)
        toolbar.addSeparator()
        toolbar.addAction(self.act_undo)
        toolbar.addAction(self.act_redo)
        toolbar.addSeparator()
        toolbar.addAction(self.act_import_csv)
        toolbar.addAction(self.act_export_csv)
        toolbar.addAction(self.act_import_xlsx)
        toolbar.addAction(self.act_export_xlsx)
        toolbar.addSeparator()
        toolbar.addAction(self.act_config)
        toolbar.addAction(self.act_help)
        toolbar.addAction(self.act_about)
        toolbar.addSeparator()
        toolbar.addAction(self.act_exit_app)

    def import_ms_access_to_sqlite(self):
        if not test_ms_access_support():
            self.show_access_warning_popup()
            return

        file_path, _filter = QFileDialog.getOpenFileName(
            self, _("Select MS Access Database"), "", "MS Access Database (*.mdb *.accdb)"
        )
        if not file_path:
            return

        import pyodbc
        access_path = Path(file_path)
        country_name = access_path.stem
        out_path = self.db_dir / f"{country_name}.db"

        if out_path.exists():
            reply = QMessageBox.question(
                self, _("File Exists"),
                _(f"SQLite database '{country_name}.db' already exists. Do you want to overwrite it?"),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        try:
            conn_str = f"Driver={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={access_path};"
            access_conn = pyodbc.connect(conn_str)
            access_cur = access_conn.cursor()

            sqlite_conn = sqlite3.connect(out_path)
            sqlite_cur = sqlite_conn.cursor()

            sqlite_cur.execute("""
                CREATE TABLE IF NOT EXISTS Stamp_List (
                    key TEXT PRIMARY KEY, nbr TEXT, year TEXT, type TEXT, valuecolor TEXT,
                    stampDescription1 TEXT, stampDescription TEXT, width TEXT, height TEXT,
                    sequence TEXT, ascii_seq TEXT, sub_nbr TEXT
                )
            """)

            try:
                access_cur.execute("SELECT key, nbr, year, type, valuecolor, stampDescription1, stampDescription, width, height, sequence, ascii_seq, sub_nbr FROM Stamp_List")
                for row in access_cur.fetchall():
                    sqlite_cur.execute("""
                        INSERT OR REPLACE INTO Stamp_List VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, tuple(str(val) if val is not None else "" for val in row))
            except Exception as ex:
                QMessageBox.warning(self, _("Table Import Notice"), f"{_('Could not fully replicate Stamp_List table:')}\n{str(ex)}")

            sqlite_cur.execute("""
                CREATE TABLE IF NOT EXISTS db_info (
                    Author TEXT, Country TEXT, Description TEXT, Version TEXT, Catalogue TEXT, Language TEXT
                )
            """)

            try:
                access_cur.execute("SELECT Author, Country, Description, Version, Catalogue, Language FROM db_info")
                for row in access_cur.fetchall():
                    sqlite_cur.execute("""
                        INSERT INTO db_info VALUES (?, ?, ?, ?, ?, ?)
                    """, tuple(str(val) if val is not None else "" for val in row))
            except Exception:
                sqlite_cur.execute("""
                    INSERT INTO db_info VALUES (?, ?, ?, ?, ?, ?)
                """, ("Boris du Reau", country_name, f"{country_name} Stamp Catalogue", "1.0", "Yvert", "fr"))

            sqlite_conn.commit()
            access_conn.close()
            sqlite_conn.close()

            self.current_db_type = "sqlite"
            self._load_country_list()
            idx = self.combo_country.findText(country_name)
            if idx != -1:
                self.combo_country.setCurrentIndex(idx)

            QMessageBox.information(self, _("Import Success"), _(f"MS Access database '{country_name}' successfully imported and converted to SQLite!"))
        except Exception as e:
            QMessageBox.critical(self, _("Conversion Error"), f"{_('Error importing Access database:')}\n{str(e)}")

    def create_new_sqlite_db(self):
        if self.current_db_type != "sqlite":
            QMessageBox.warning(self, _("SQLite Only"), _("Creating a new database is only supported for SQLite."))
            return

        dialog = CreateDatabaseDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_data()
            country = data["country"]
            if not country:
                QMessageBox.warning(self, _("Error"), _("Collection name cannot be empty."))
                return

            db_path = self.db_dir / f"{country}.db"
            if db_path.exists():
                QMessageBox.critical(self, _("Error"), _("A database for this country already exists."))
                return

            conn = sqlite3.connect(db_path)
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS Stamp_List (
                    key TEXT PRIMARY KEY, nbr TEXT, year TEXT, type TEXT, valuecolor TEXT,
                    stampDescription1 TEXT, stampDescription TEXT, width TEXT, height TEXT,
                    sequence TEXT, ascii_seq TEXT, sub_nbr TEXT
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS db_info (
                    Author TEXT, Country TEXT, Description TEXT, Version TEXT, Catalogue TEXT, Language TEXT
                )
            """)
            cur.execute("""
                INSERT INTO db_info VALUES (?, ?, ?, ?, ?, ?)
            """, (data["author"], country, data["description"], "1.0", data["catalogue"], data["language"]))
            conn.commit()
            conn.close()

            self._load_country_list()
            idx = self.combo_country.findText(country)
            if idx != -1:
                self.combo_country.setCurrentIndex(idx)
            QMessageBox.information(self, _("Success"), _(f"New SQLite database '{country}.db' created successfully."))

    def open_db_info(self):
        if not self.db_adapter:
            return
        dialog = DatabaseInfoDialog(self.db_adapter, self.current_country, self)
        dialog.exec()

    def _load_country_list(self):
        self.combo_country.blockSignals(True)
        self.combo_country.clear()
        self.available_countries = self._detect_available_countries()
        self.combo_country.addItems(self.available_countries)
        self.combo_country.blockSignals(False)
        self.act_create_db.setEnabled(self.current_db_type == "sqlite")
        if self.available_countries:
            self._on_country_changed(0)

    def _on_country_changed(self, index):
        if not self._check_unsaved_changes():
            return

        country_name = self.combo_country.currentText()
        if not country_name:
            return

        if self.current_db_type == "access" and not test_ms_access_support():
            self.show_access_warning_popup()
            self.current_db_type = "sqlite"

        self.current_country = country_name
        if self.db_adapter:
            self.db_adapter.close()

        try:
            self.db_adapter = CountryDatabaseAdapter(country_name, self.db_dir, self.current_db_type)
        except RuntimeError:
            self.show_access_warning_popup()
            self.current_db_type = "sqlite"
            self.db_adapter = CountryDatabaseAdapter(country_name, self.db_dir, "sqlite")

        self.undo_stack.clear()
        self.is_dirty = False

        self.combo_type.blockSignals(True)
        self.combo_type.clear()
        self.combo_type.addItem(_("All"))
        self.combo_type.addItems(self.db_adapter.load_types())
        self.combo_type.blockSignals(False)

        self.edit_type.blockSignals(True)
        self.edit_type.clear()
        if self.db_adapter:
            self.edit_type.addItems(self.db_adapter.load_types())
        self.edit_type.blockSignals(False)

        self.combo_year.blockSignals(True)
        self.combo_year.clear()
        self.combo_year.addItem(_("All"))
        self.combo_year.addItems([str(y) for y in self.db_adapter.load_years()])
        self.combo_year.blockSignals(False)

        self._refresh_table()

    def _refresh_table(self):
        if not self.db_adapter:
            return

        self.table.setSortingEnabled(False)
        stamps = self.db_adapter.get_stamps(
            stamp_type=self.combo_type.currentText(),
            year=self.combo_year.currentText(),
            search_nbr=self.edit_search_nbr.text().strip()
        )

        self.table.setRowCount(0)
        for row_idx, stamp in enumerate(stamps):
            key, nbr, year, stype, valcolor, desc1, desc, width, height, seq, ascii_seq, sub_nbr = stamp
            self.table.insertRow(row_idx)
            self.table.setItem(row_idx, 0, QTableWidgetItem(str(nbr or "")))
            self.table.setItem(row_idx, 1, QTableWidgetItem(str(year or "")))

            type_item = QTableWidgetItem(str(stype or ""))
            type_item.setFlags(type_item.flags() | Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row_idx, 2, type_item)

            self.table.setItem(row_idx, 3, QTableWidgetItem(str(valcolor or "")))
            self.table.setItem(row_idx, 4, QTableWidgetItem(str(desc1 or "")))
            self.table.setItem(row_idx, 5, QTableWidgetItem(str(desc or "")))
            self.table.item(row_idx, 0).setData(Qt.ItemDataRole.UserRole, stamp)

        self.table.setSortingEnabled(True)
        if self.table.rowCount() > 0:
            self.table.selectRow(0)
            self._on_stamp_selected()

    def _on_stamp_selected(self):
        selected_rows = self.table.selectedItems()
        if not selected_rows:
            return

        row = self.table.currentRow()
        stamp_data = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        key, nbr, year, stype, valcolor, desc1, desc, width, height, seq, ascii_seq, sub_nbr = stamp_data

        self.edit_nbr.setText(str(nbr or ""))
        self.edit_sub_nbr.setText(str(sub_nbr or ""))
        self.edit_year.setText(str(year or ""))
        self.edit_type.setCurrentText(str(stype or ""))
        self.edit_valcolor.setText(str(valcolor or ""))
        self.edit_desc1.setPlainText(str(desc1 or ""))
        self.edit_desc.setPlainText(str(desc or ""))
        self.edit_width.setText(str(width or ""))
        self.edit_height.setText(str(height or ""))
        self.edit_sequence.setText(str(seq or ""))
        self.edit_ascii_seq.setText(str(ascii_seq or ""))
        self._load_stamp_image(nbr, stype, sub_nbr)

    def _on_apply_record_edit(self):
        selected_rows = self.table.selectedItems()
        if not selected_rows or not self.db_adapter:
            return

        row = self.table.currentRow()
        old_stamp_data = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        stamp_key = old_stamp_data[0]

        new_stamp_data = (
            stamp_key,
            self.edit_nbr.text().strip(),
            self.edit_year.text().strip(),
            self.edit_type.currentText().strip(),
            self.edit_valcolor.text().strip(),
            self.edit_desc1.toPlainText().strip(),
            self.edit_desc.toPlainText().strip(),
            self.edit_width.text().strip(),
            self.edit_height.text().strip(),
            self.edit_sequence.text().strip(),
            self.edit_ascii_seq.text().strip(),
            self.edit_sub_nbr.text().strip()
        )
        cmd = UpdateStampCommand(self, stamp_key, old_stamp_data, new_stamp_data)
        self.undo_stack.push(cmd)

    def _on_add_stamp_record(self):
        if not self.db_adapter:
            return

        new_key = str(self.db_adapter.get_max_key() + 1)
        new_stamp_data = (
            new_key, "0", "2026", "Poste", "", "",
            _("New Stamp Description"), "20", "25", "1000", "1000", ""
        )

        self.combo_type.blockSignals(True)
        self.combo_year.blockSignals(True)
        self.edit_search_nbr.blockSignals(True)
        self.combo_type.setCurrentText(_("All"))
        self.combo_year.setCurrentText(_("All"))
        self.edit_search_nbr.clear()
        self.combo_type.blockSignals(False)
        self.combo_year.blockSignals(False)
        self.edit_search_nbr.blockSignals(False)

        cmd = AddStampCommand(self, new_stamp_data)
        self.undo_stack.push(cmd)

    def _on_delete_stamp_record(self):
        if not self.db_adapter:
            return

        selected_ranges = self.table.selectedRanges()
        if not selected_ranges:
            return

        selected_rows = sorted(list(set(
            row for r in selected_ranges for row in range(r.topRow(), r.bottomRow() + 1)
        )))
        if not selected_rows:
            return

        stamps_to_delete = []
        for row in selected_rows:
            stamp_data = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
            if stamp_data:
                stamps_to_delete.append(stamp_data)

        count = len(stamps_to_delete)
        if count == 0:
            return

        msg = _("Are you sure you want to delete 1 selected stamp record?") if count == 1 else _(f"Are you sure you want to delete {count} selected stamp records?")
        reply = QMessageBox.question(self, _("Confirm Delete"), msg, QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            cmd = DeleteStampsCommand(self, stamps_to_delete)
            self.undo_stack.push(cmd)

    def apply_stamp_data(self, key, stamp_data):
        if not self.db_adapter:
            return

        _, nbr, year, stype, valcolor, desc1, desc, width, height, seq, ascii_seq, sub_nbr = stamp_data
        self.db_adapter.update_stamp(key, nbr, year, stype, valcolor, desc1, desc, width, height, seq, ascii_seq, sub_nbr)
        self._refresh_table()

        current_val = self.edit_type.currentText()
        self.edit_type.blockSignals(True)
        self.edit_type.clear()
        self.edit_type.addItems(self.db_adapter.load_types())
        self.edit_type.setCurrentText(current_val)
        self.edit_type.blockSignals(False)

    def _update_dirty_state(self, is_clean):
        self.is_dirty = not is_clean
        prefix = "*" if self.is_dirty else ""
        self.setWindowTitle(f"{prefix}StampDatabase - {self.current_country}")

    def save_changes(self):
        if self.db_adapter and self.is_dirty:
            self.db_adapter.commit()
            self.undo_stack.setClean()
            QMessageBox.information(self, _("Saved"), _("Database changes saved successfully."))

    def _check_unsaved_changes(self) -> bool:
        if self.is_dirty:
            reply = QMessageBox.question(
                self, _("Unsaved Changes"),
                _("You have unsaved database changes. Do you want to save them now?"),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.save_changes()
                return True
            elif reply == QMessageBox.StandardButton.Cancel:
                return False
        return True

    def getPhotoName(self, stampNumber: str, stampType: str, stampSubNbr) -> str:
        subNbr = f"-{stampSubNbr}" if stampSubNbr is not None and str(stampSubNbr).strip() not in ["", "None"] else ""
        stampNumber_str = str(stampNumber)
        type_prefix = stampNumber_str[0:2]

        prefix_map = {
            "A ": f"T01-030-{stampNumber_str[2:]}{subNbr}.jpg",
            "BF": f"T01-080-{stampNumber_str[3:]}{subNbr}.jpg",
            "S ": f"T01-170-{stampNumber_str[2:]}{subNbr}.jpg",
            "BC": f"T01-000-BC{stampNumber_str[3:]}{subNbr}.jpg",
            "B ": f"T01-000-B{stampNumber_str[2:]}{subNbr}.jpg",
            "P ": f"T01-000-P{stampNumber_str[2:]}{subNbr}.jpg",
            "PR": f"T01-420-{stampNumber_str[3:]}{subNbr}.jpg",
            "FM": f"T01-190-{stampNumber_str[3:]}{subNbr}.jpg",
            "TA": f"T01-270-{stampNumber_str[3:]}{subNbr}.jpg",
            "CR": f"T01-565-{stampNumber_str[3:]}{subNbr}.jpg",
            "GU": f"T01-150-{stampNumber_str[3:]}{subNbr}.jpg",
            "AL": f"T01-110-{stampNumber_str[3:]}{subNbr}.jpg",
            "JN": f"T01-160-{stampNumber_str[3:]}{subNbr}.jpg",
            "PC": f"T01-120-{stampNumber_str[3:]}{subNbr}.jpg",
            "CP": f"T01-130-{stampNumber_str[3:]}{subNbr}.jpg",
            "FP": f"T01-140-{stampNumber_str[3:]}{subNbr}.jpg",
            "CF": f"T01-180-CF-{stampNumber_str[3:]}{subNbr}.jpg",
            "CO": f"T01-200-{stampNumber_str[3:]}{subNbr}.jpg",
            "TL": f"T01-210-{stampNumber_str[3:]}{subNbr}.jpg",
            "MT": f"T01-211-{stampNumber_str[3:]}{subNbr}.jpg",
            "TE": f"T01-215-{stampNumber_str[3:]}{subNbr}.jpg",
            "GR": f"T01-220-{stampNumber_str[3:]}{subNbr}.jpg",
            "PM": f"T01-230-{stampNumber_str[3:]}{subNbr}.jpg",
            "F ": f"T01-240-{stampNumber_str[2:]}{subNbr}.jpg",
            "F-": f"T01-000-F{stampNumber_str[2:]}{subNbr}.jpg",
            "BI": f"T01-250-{stampNumber_str[2:]}{subNbr}.jpg",
            "MA": f"T01-251-{stampNumber_str[2:]}{subNbr}.jpg",
            "DI": f"T01-260-{stampNumber_str[2:]}{subNbr}.jpg"
        }
        if type_prefix in prefix_map:
            return prefix_map[type_prefix]

        stampType_str = str(stampType).strip() if stampType else ""
        type_str_map = {
            "COURS INSTRUCTION": f"T01-252-{stampNumber_str}{subNbr}.jpg",
            "Préoblitéré COURS INSTRUCTION": f"T01-253-{stampNumber_str}{subNbr}.jpg",
            "RECOUVREMENT COURS INSTRUCTION": f"T01-254-{stampNumber_str}{subNbr}.jpg",
            "TAXES COURS INSTRUCTION": f"T01-255-{stampNumber_str}{subNbr}.jpg",
            "POSTE AERIENNE MILITAIRE": f"T01-256-{stampNumber_str}{subNbr}.jpg"
        }
        return type_str_map.get(stampType_str, f"T01-000-{stampNumber_str}{subNbr}.jpg")

    def _find_file_case_insensitive(self, folder_path: Path, filename: str) -> Path:
        if not folder_path.is_dir():
            return None
        exact_path = folder_path / filename
        if exact_path.exists():
            return exact_path
        target_lower = filename.lower()
        for item in folder_path.iterdir():
            if item.is_file() and item.name.lower() == target_lower:
                return item
        return None

    def _load_stamp_image(self, stamp_nbr, stamp_type, stamp_sub_nbr=""):
        rel_filename = self.getPhotoName(stamp_nbr, stamp_type, stamp_sub_nbr)
        possible_folders = [
            self.base_dir / "Photos" / str(self.current_country)
        ]
        for folder in possible_folders:
            found_path = self._find_file_case_insensitive(folder, rel_filename)
            if found_path:
                pixmap = QPixmap(str(found_path))
                if not pixmap.isNull():
                    scaled_pixmap = pixmap.scaledToWidth(200) if pixmap.width() > pixmap.height() else pixmap.scaledToHeight(200)
                    self.img_label.setPixmap(scaled_pixmap)
                    return
        self.img_label.setText(_("No Photo Available"))

    def _select_stamp_by_key_or_nbr(self, target_key: str, target_nbr: str):
        if not self.table or self.table.rowCount() == 0:
            return
        for row in range(self.table.rowCount()):
            item_nbr = self.table.item(row, 0)
            if not item_nbr:
                continue
            stamp_data = item_nbr.data(Qt.ItemDataRole.UserRole)
            if stamp_data and (str(stamp_data[0]) == str(target_key) or str(stamp_data[1]) == str(target_nbr)):
                self.table.selectRow(row)
                self.table.scrollToItem(item_nbr, QTableWidget.ScrollHint.EnsureVisible)
                self._on_stamp_selected()
                break

    def import_csv(self):
        ImportExport.import_csv(self)

    def export_csv(self):
        ImportExport.export_csv(self)

    def import_xlsx(self):
        ImportExport.import_xlsx(self)

    def export_xlsx(self):
        ImportExport.export_xlsx(self)

    def translate_xlsx_catalogue(self):
        translateXLSXDatabase.translate_xlsx_interactive(self)

    def open_config(self):
        StampDatabaseConfig.open_config(self)

    def open_manual(self):
        doc_dir = self.base_dir / "Help"
        manual_filename = "StampDatabase Manuel utilisateur 19-10-2026.pdf" if self.config_manager.language == "fr" else "StampDatabase User Manual 19-10-2026.pdf"
        manual_path = doc_dir / manual_filename
        if manual_path.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(manual_path)))
        else:
            QMessageBox.warning(self, _("Manual Error"), _("User manual file not found."))

    def open_about(self):
        dialog = SDAboutDlg(self)
        dialog.exec()

    def closeEvent(self, event):
        if self._check_unsaved_changes():
            if self.db_adapter:
                self.db_adapter.close()
            event.accept()
        else:
            event.ignore()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())