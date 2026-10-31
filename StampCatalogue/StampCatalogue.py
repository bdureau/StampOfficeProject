"""
StampCatalogue Application
--------------------------
Main application window, toolbar, actions, and user interface.

Author: Boris du Reau
Year: 2026
"""

import sys
import os
import sqlite3
import gettext
import subprocess
from pathlib import Path

from PyQt6 import QtGui
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QComboBox, QLabel, QTableWidget, QTableWidgetItem, QPushButton,
    QHeaderView, QLineEdit, QSpinBox, QDoubleSpinBox, QMessageBox,
    QFileDialog, QGroupBox, QFormLayout, QTextEdit, QSplitter,
    QDialog, QToolBar, QStyle
)
from PyQt6.QtGui import QPixmap, QIcon, QAction

# Internal module imports
from SCAppLanguage import get_language
from SCAboutDlg import SCAboutDlg
from SCConfig import ConfigManager
from SCDatabase import CollectionManagerDB, CountryCatalogueDB
from SCDialogs import ConfigurationDialog, CreateCollectionDialog
from SCUtils import get_photo_name, find_file_case_insensitive, export_mancolist_to_excel

# Localization setup
gettext.find("StampCatalogue")
translate = gettext.translation(
    'StampCatalogue', localedir='locale', languages=[get_language()], fallback=True
)
translate.install()
_ = translate.gettext


class MainWindow(QMainWindow):
    """Main Application Window for StampCatalogue."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle(_("StampCatalogue - Stamp Collection Manager"))
        self.resize(1200, 750)

        self.base_dir = self._get_app_dir()
        self.db_dir = self.base_dir / "Databases"
        self.icons_dir = self.base_dir / "Images"

        icon_path = self.icons_dir / "StampCatalogue.png"
        if icon_path.exists():
            self.setWindowIcon(QtGui.QIcon(str(icon_path)))
        else:
            self.setWindowIcon(QtGui.QIcon('StampCatalogue.png'))

        # Load Configuration
        self.config_manager = ConfigManager(self.base_dir / "StampCatalogue.cfg")

        self.central_db = CollectionManagerDB(self.db_dir)
        self.country_db = None

        self.current_collection_id = None
        self.current_country = None
        self.selected_nbr = None

        self.available_countries = self._detect_available_countries()

        self._create_actions()
        self._create_menu_and_toolbar()
        self._init_ui()
        self._load_collections()

    def _get_app_dir(self) -> Path:
        """Determine the root application directory."""
        if getattr(sys, 'frozen', False):
            return Path(sys.executable).resolve().parent
        else:
            script_dir = Path(__file__).resolve().parent
            parent_dir = script_dir.parent

            if any((parent_dir / folder).exists() for folder in ["Databases", "Images", "Photos", "Help", "locale"]):
                return parent_dir

            return script_dir

    def _get_icon(self, icon_filename: str, fallback_standard_icon: QStyle.StandardPixmap) -> QIcon:
        """Fetch custom PNG icon from images directory or fall back to standard system icon."""
        custom_icon_path = self.icons_dir / icon_filename
        if custom_icon_path.exists():
            return QIcon(str(custom_icon_path))
        return self.style().standardIcon(fallback_standard_icon)

    def _detect_available_countries(self):
        """Detect country database files in the Databases folder."""
        if not self.db_dir.exists():
            return []
        return sorted([f.stem for f in self.db_dir.glob("*.db") if f.stem not in ["master", "collections"]])

    def _create_actions(self):
        """Create shared QActions for menus and toolbars."""
        # Action: New Collection
        icon_add = self._get_icon("new.png", QStyle.StandardPixmap.SP_FileDialogNewFolder)
        self.action_new_coll = QAction(icon_add, _("New Collection..."), self)
        self.action_new_coll.setToolTip(_("Create a new collection"))
        self.action_new_coll.triggered.connect(self._create_collection)

        # Action: Delete Collection
        icon_del = self._get_icon("trash.png", QStyle.StandardPixmap.SP_TrashIcon)
        self.action_del_coll = QAction(icon_del, _("Delete Collection"), self)
        self.action_del_coll.setToolTip(_("Delete current collection"))
        self.action_del_coll.triggered.connect(self._delete_collection)

        # Action: Export Mancolist
        icon_export = self._get_icon("export_to_csv.png", QStyle.StandardPixmap.SP_DialogSaveButton)
        self.action_export_mancolist = QAction(icon_export, _("Export Mancolist (Excel)"), self)
        self.action_export_mancolist.setToolTip(_("Export missing stamps to Excel"))
        self.action_export_mancolist.triggered.connect(self._export_mancolist)

        # Action: Configuration
        icon_config = self._get_icon("config.png", QStyle.StandardPixmap.SP_FileDialogEnd)
        self.action_config = QAction(icon_config, _("Settings..."), self)
        self.action_config.setToolTip(_("Configure application settings"))
        self.action_config.triggered.connect(self._open_settings)

        # Action: User Manual
        icon_help = self._get_icon("help.png", QStyle.StandardPixmap.SP_DialogHelpButton)
        self.action_manual = QAction(icon_help, _("User Manual"), self)
        self.action_manual.setToolTip(_("Open user manual"))
        self.action_manual.triggered.connect(self._open_manual)

        # Action: About
        icon_about = self._get_icon("about.png", QStyle.StandardPixmap.SP_MessageBoxInformation)
        self.action_about = QAction(icon_about, _("About"), self)
        self.action_about.setToolTip(_("About StampCatalogue"))
        self.action_about.triggered.connect(self._show_about)

        # Action: Exit Application
        icon_exit = self._get_icon("exit.png", QStyle.StandardPixmap.SP_DialogCloseButton)
        self.action_exit = QAction(icon_exit, _("Quit"), self)
        self.action_exit.setShortcut("Ctrl+Q")
        self.action_exit.setToolTip(_("Quit application"))
        self.action_exit.triggered.connect(self.close)

    def _create_menu_and_toolbar(self):
        """Build Menu Bar and Top ToolBar."""
        menu_bar = self.menuBar()

        # Collection Menu
        collection_menu = menu_bar.addMenu(_("&Collection"))
        collection_menu.addAction(self.action_new_coll)
        collection_menu.addAction(self.action_del_coll)
        collection_menu.addSeparator()
        collection_menu.addAction(self.action_exit)

        # Tools Menu
        tools_menu = menu_bar.addMenu(_("&Tools"))
        tools_menu.addAction(self.action_export_mancolist)

        # Settings Menu
        config_menu = menu_bar.addMenu(_("&Configuration"))
        config_menu.addAction(self.action_config)

        # Help Menu
        help_menu = menu_bar.addMenu(_("&Help"))
        help_menu.addAction(self.action_manual)
        help_menu.addSeparator()
        help_menu.addAction(self.action_about)

        # Top ToolBar
        toolbar = QToolBar(_("Main Toolbar"))
        toolbar.setIconSize(QSize(24, 24))
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, toolbar)

        toolbar.addAction(self.action_new_coll)
        toolbar.addAction(self.action_del_coll)
        toolbar.addSeparator()
        toolbar.addAction(self.action_export_mancolist)
        toolbar.addSeparator()
        toolbar.addAction(self.action_config)
        toolbar.addAction(self.action_manual)

    def _init_ui(self):
        """Initialize main layout and child widgets."""
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)

        # Collection Selection Header
        coll_box = QGroupBox(_("Collection Selection"))
        coll_layout = QHBoxLayout()

        coll_layout.addWidget(QLabel(_("Active Collection:")))
        self.combo_collections = QComboBox()
        self.combo_collections.currentIndexChanged.connect(self._on_collection_changed)
        coll_layout.addWidget(self.combo_collections, stretch=1)

        coll_box.setLayout(coll_layout)
        main_layout.addWidget(coll_box)

        # Filter Bar
        filter_box = QGroupBox(_("Catalogue Filters"))
        filter_layout = QHBoxLayout()

        filter_layout.addWidget(QLabel(_("Type:")))
        self.combo_type = QComboBox()
        self.combo_type.currentTextChanged.connect(self._refresh_table)
        filter_layout.addWidget(self.combo_type)

        filter_layout.addWidget(QLabel(_("Year:")))
        self.combo_year = QComboBox()
        self.combo_year.currentTextChanged.connect(self._refresh_table)
        filter_layout.addWidget(self.combo_year)

        filter_layout.addWidget(QLabel(_("Catalog N°:")))
        self.edit_search_nbr = QLineEdit()
        self.edit_search_nbr.setPlaceholderText(_("e.g. 154..."))
        self.edit_search_nbr.textChanged.connect(self._refresh_table)
        filter_layout.addWidget(self.edit_search_nbr)

        filter_box.setLayout(filter_layout)
        main_layout.addWidget(filter_box)

        # Main Splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Stamps Table
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            _("Yvert N°"),
            _("Year"),
            _("Type"),
            _("Value / Color"),
            _("Description"),
            _("Status")
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSortingEnabled(True)
        self.table.itemSelectionChanged.connect(self._on_stamp_selected)
        splitter.addWidget(self.table)

        # Right Panel (Details + Collection Form)
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)

        # Image Viewer
        self.img_label = QLabel(_("No Photo Available"))
        self.img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.img_label.setFixedSize(220, 220)
        self.img_label.setStyleSheet("border: 1px solid #cbd5e0; background: #f7fafc;")
        right_layout.addWidget(self.img_label, alignment=Qt.AlignmentFlag.AlignCenter)

        # Details Box
        detail_box = QGroupBox(_("Stamp Details"))
        detail_form = QFormLayout()

        self.lbl_year = QLabel("-")
        self.lbl_yvert = QLabel("-")
        self.lbl_valeur = QLabel("-")
        self.lbl_desc = QLabel("-")
        self.lbl_desc.setWordWrap(True)

        detail_form.addRow(_("Year:"), self.lbl_year)
        detail_form.addRow(_("Yvert N°:"), self.lbl_yvert)
        detail_form.addRow(_("Value / Color:"), self.lbl_valeur)
        detail_form.addRow(_("Description 1:"), self.lbl_desc)
        detail_box.setLayout(detail_form)
        right_layout.addWidget(detail_box)

        # Ownership Form
        form_box = QGroupBox(_("Collection Status"))
        form = QFormLayout()

        self.combo_status = QComboBox()
        self.combo_status.addItems([
            _("Not Owned"),
            _("Owned"),
            _("Manco (Wanted)"),
            _("Ordered")
        ])

        self.combo_condition = QComboBox()
        self.combo_condition.addItems([
            _("Mint Never Hinged (** MNH)"),
            _("Mint Hinged (* MH)"),
            _("Used (Cancelled)"),
            _("On Cover")
        ])

        self.spin_qty = QSpinBox()
        self.spin_qty.setRange(1, 100)

        self.spin_price = QDoubleSpinBox()
        self.spin_price.setRange(0, 100000)
        self.spin_price.setSuffix(" €")

        self.txt_notes = QTextEdit()
        self.txt_notes.setMaximumHeight(60)

        form.addRow(_("Status:"), self.combo_status)
        form.addRow(_("Condition:"), self.combo_condition)
        form.addRow(_("Quantity:"), self.spin_qty)
        form.addRow(_("Purchase Price:"), self.spin_price)
        form.addRow(_("Notes:"), self.txt_notes)

        btn_save = QPushButton(_("Save to Collection"))
        btn_save.setStyleSheet("background-color: #2b6cb0; color: white; font-weight: bold;")
        btn_save.clicked.connect(self._save_stamp_status)
        form.addRow(btn_save)

        form_box.setLayout(form)
        right_layout.addWidget(form_box)

        splitter.addWidget(right_panel)
        splitter.setSizes([650, 350])

        main_layout.addWidget(splitter)

    def _open_settings(self):
        """Open settings dialog and save updated INI configuration."""
        dialog = ConfigurationDialog(
            current_lang=self.config_manager.get_language(),
            current_db_type=self.config_manager.get_db_type(),
            parent=self
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_lang, new_db_type = dialog.get_settings()
            self.config_manager.set_settings(new_lang, new_db_type)

            import SCAppLanguage
            SCAppLanguage.get_language(force_reload=True)

            QMessageBox.information(
                self,
                _("Settings Saved"),
                _("Configuration saved to StampCatalogue.cfg.\nPlease restart the application to apply language changes.")
            )

    def _show_about(self):
        """Display about dialog."""
        dialog = SCAboutDlg(self)
        dialog.exec()

    def _open_manual(self):
        """Open language-specific manual file."""
        lang = self.config_manager.get_language()
        doc_dir = self.base_dir / "Help"

        if lang == "fr":
            help_file = doc_dir / "StampCatalogue Documentation Utilisateur19-10-2026.pdf"
        else:
            help_file = doc_dir / "StampCatalogue User Guide19-10-2026.pdf"

        if help_file.exists():
            try:
                if sys.platform == 'win32':
                    os.startfile(help_file)
                elif sys.platform == 'darwin':
                    subprocess.run(["open", str(help_file)])
                else:
                    subprocess.run(["xdg-open", str(help_file)])
            except Exception as e:
                QMessageBox.critical(self, _("Error"), f"{_('Could not open manual:')}\n{str(e)}")
        else:
            QMessageBox.warning(
                self,
                _("Manual Not Found"),
                f"{_('User manual file not found:')}\n{help_file}"
            )

    def _load_collections(self):
        """Populate the collections dropdown."""
        self.combo_collections.blockSignals(True)
        self.combo_collections.clear()

        collections = self.central_db.get_collections()
        for coll_id, name, country in collections:
            display_text = f"{name} ({country})"
            self.combo_collections.addItem(display_text, userData={"id": coll_id, "country": country})

        self.combo_collections.blockSignals(False)

        if collections:
            self._on_collection_changed(0)
        else:
            self._clear_ui()

    def _create_collection(self):
        """Open dialog to create a new collection."""
        if not self.available_countries:
            QMessageBox.warning(self, _("Warning"), _("No country Databases found in 'Databases/'."))
            return

        dialog = CreateCollectionDialog(self.available_countries, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            name, country = dialog.get_data()
            if not name:
                QMessageBox.warning(self, _("Error"), _("Collection name cannot be empty."))
                return
            try:
                coll_id = self.central_db.create_collection(name, country)
                self._load_collections()
                idx = self.combo_collections.findData({"id": coll_id, "country": country})
                if idx != -1:
                    self.combo_collections.setCurrentIndex(idx)
            except sqlite3.IntegrityError:
                QMessageBox.critical(self, _("Error"), _("A collection with this name already exists."))

    def _delete_collection(self):
        """Delete current selected collection."""
        if self.current_collection_id is None:
            return

        reply = QMessageBox.question(
            self,
            _("Delete Collection"),
            _("Are you sure you want to delete this collection and all its tracked stamps?"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.central_db.delete_collection(self.current_collection_id)
            self._load_collections()

    def _on_collection_changed(self, index):
        """Handle collection dropdown selection change."""
        data = self.combo_collections.currentData()
        if not data:
            self._clear_ui()
            return

        self.current_collection_id = data["id"]
        self.current_country = data["country"]

        if self.country_db:
            self.country_db.close()
        self.country_db = CountryCatalogueDB(self.current_country, self.db_dir)

        self.combo_type.blockSignals(True)
        self.combo_type.clear()
        self.combo_type.addItem(_("All"))
        self.combo_type.addItems(self.country_db.load_types())
        self.combo_type.blockSignals(False)

        self.combo_year.blockSignals(True)
        self.combo_year.clear()
        self.combo_year.addItem(_("All"))
        self.combo_year.addItems([str(y) for y in self.country_db.load_years()])
        self.combo_year.blockSignals(False)

        self._refresh_table()

    def _refresh_table(self):
        """Refresh catalogue table records based on active filters."""
        if not self.country_db or self.current_collection_id is None:
            return

        stamps = self.country_db.get_stamps(
            stamp_type=self.combo_type.currentText(),
            year=self.combo_year.currentText(),
            search_nbr=self.edit_search_nbr.text().strip()
        )

        user_items = self.central_db.get_collection_items(self.current_collection_id)

        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)

        for row_idx, stamp in enumerate(stamps):
            nbr, year, stype, valcolor, desc, key, sub_nbr = stamp
            self.table.insertRow(row_idx)

            self.table.setItem(row_idx, 0, QTableWidgetItem(str(nbr or "")))
            self.table.setItem(row_idx, 1, QTableWidgetItem(str(year or "")))
            self.table.setItem(row_idx, 2, QTableWidgetItem(str(stype or "")))
            self.table.setItem(row_idx, 3, QTableWidgetItem(str(valcolor or "")))
            self.table.setItem(row_idx, 4, QTableWidgetItem(str(desc or "")))

            user_data = user_items.get(str(nbr))
            status_text = user_data[0] if user_data else _("Not Owned")
            status_item = QTableWidgetItem(status_text)

            if status_text == _("Owned"):
                status_item.setForeground(Qt.GlobalColor.darkGreen)
            elif status_text == _("Manco (Wanted)"):
                status_item.setForeground(Qt.GlobalColor.red)

            self.table.setItem(row_idx, 5, status_item)

            full_data = stamp + (user_data,)
            self.table.item(row_idx, 0).setData(Qt.ItemDataRole.UserRole, full_data)

        self.table.setSortingEnabled(True)

    def _on_stamp_selected(self):
        """Handle row selection inside the catalogue table."""
        selected_rows = self.table.selectedItems()
        if not selected_rows:
            return

        row = self.table.currentRow()
        stamp_data = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)

        nbr, year, stype, valcolor, desc, key, sub_nbr, user_data = stamp_data
        self.selected_nbr = nbr

        self.lbl_year.setText(str(year or "-"))
        self.lbl_yvert.setText(str(nbr or "-"))
        self.lbl_valeur.setText(str(valcolor or "-"))
        self.lbl_desc.setText(str(desc or "-"))

        if user_data:
            status, cond, qty, price, notes = user_data
            self.combo_status.setCurrentText(status)
            self.combo_condition.setCurrentText(cond if cond else _("Mint Never Hinged (** MNH)"))
            self.spin_qty.setValue(qty if qty else 1)
            self.spin_price.setValue(price if price else 0.0)
            self.txt_notes.setPlainText(notes if notes else "")
        else:
            self.combo_status.setCurrentText(_("Not Owned"))
            self.combo_condition.setCurrentIndex(0)
            self.spin_qty.setValue(1)
            self.spin_price.setValue(0.0)
            self.txt_notes.clear()

        self._load_stamp_image(nbr, stype, sub_nbr)

    def _load_stamp_image(self, stamp_nbr, stamp_type, stamp_sub_nbr=""):
        """Display stamp photo using case-insensitive lookup."""
        rel_filename = get_photo_name(stamp_nbr, stamp_type, stamp_sub_nbr)

        candidate_folders = [
            self.base_dir / "Images" / str(self.current_country),
            self.base_dir / "Photos" / str(self.current_country),
            self.base_dir / "Images",
            self.base_dir / "Photos",
            self.base_dir
        ]

        found_path = None
        for folder in candidate_folders:
            found_path = find_file_case_insensitive(folder, rel_filename)
            if found_path:
                break

        if found_path:
            pixmap = QPixmap(str(found_path))
            if not pixmap.isNull():
                if pixmap.width() > pixmap.height():
                    scaled_pixmap = pixmap.scaledToWidth(200)
                else:
                    scaled_pixmap = pixmap.scaledToHeight(200)

                self.img_label.setPixmap(scaled_pixmap)
                return

        self.img_label.setText(_("No Photo Available"))

    def _save_stamp_status(self):
        """Save ownership details to the collection database."""
        if not self.selected_nbr or self.current_collection_id is None:
            return

        status = self.combo_status.currentText()
        if status == _("Not Owned"):
            self.central_db.remove_item(self.current_collection_id, self.selected_nbr)
        else:
            self.central_db.save_item(
                collection_id=self.current_collection_id,
                stamp_nbr=self.selected_nbr,
                status=status,
                condition=self.combo_condition.currentText(),
                quantity=self.spin_qty.value(),
                price=self.spin_price.value(),
                notes=self.txt_notes.toPlainText().strip()
            )

        self._refresh_table()

    def _export_mancolist(self):
        """Export missing stamps for the active collection to an Excel file."""
        if not self.country_db or self.current_collection_id is None:
            return

        stamps = self.country_db.get_stamps()
        user_items = self.central_db.get_collection_items(self.current_collection_id)

        mancolist = []
        for stamp in stamps:
            nbr, year, stype, valcolor, desc, key, sub_nbr = stamp
            user_data = user_items.get(str(nbr))
            status = user_data[0] if user_data else _("Missing")

            if not user_data or status in [_("Manco (Wanted)"), _("Missing")]:
                notes = user_data[4] if user_data else ""
                mancolist.append((nbr, year, stype, valcolor, desc, status, notes))

        if not mancolist:
            QMessageBox.information(self, _("Information"), _("No missing stamps found for this collection."))
            return

        coll_name = self.combo_collections.currentText().split(" (")[0]
        default_filename = f"Mancolist_{coll_name}.xlsx"

        file_path, _filter = QFileDialog.getSaveFileName(
            self,
            _("Save Mancolist"),
            default_filename,
            f"{_('Excel Files')} (*.xlsx)"
        )
        if not file_path:
            return

        export_mancolist_to_excel(file_path, mancolist)
        QMessageBox.information(self, _("Success"), f"{_('Mancolist exported successfully:')}\n{file_path}")

    def _clear_ui(self):
        """Reset table and details view when no collection is selected."""
        self.table.setRowCount(0)
        self.lbl_year.setText("-")
        self.lbl_yvert.setText("-")
        self.lbl_valeur.setText("-")
        self.lbl_desc.setText("-")
        self.img_label.setText(_("No Photo Available"))

    def closeEvent(self, event):
        """Clean up active database handles upon exit."""
        if self.central_db:
            self.central_db.close()
        if self.country_db:
            self.country_db.close()
        event.accept()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())