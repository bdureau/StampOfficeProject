"""
StampCatalogue Application
--------------------------
Main application window, menus, toolbar, actions, and user interface.

Every visible text is set in retranslate_ui(): it runs when the window is
built and again after each change of language (SCAppLanguage.set_language),
so the whole interface switches language immediately, without restarting.

Author: Boris du Reau
Date: 2026-10-31
"""

import sys
import os
import sqlite3
import subprocess

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
import SCAppLanguage
from SCAppLanguage import _, get_language
from SCAppPaths import get_app_dir
from SCAboutDlg import SCAboutDlg
from SCConfig import ConfigManager
from SCDatabase import (CollectionManagerDB, CountryCatalogueDB, STATUS_LABELS, CONDITION_LABELS,
                        STATUS_NOT_OWNED, STATUS_OWNED, STATUS_WANTED, STATUS_MISSING,
                        status_label)
from SCDialogs import ConfigurationDialog, CreateCollectionDialog
from SCUtils import get_photo_name, find_file_case_insensitive, export_mancolist_to_excel


class MainWindow(QMainWindow):
    """Main Application Window for StampCatalogue."""

    def __init__(self):
        super().__init__()
        self.resize(1200, 750)

        self.base_dir = get_app_dir()
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
        self.has_photo = False

        self.available_countries = self._detect_available_countries()

        self._create_actions()
        self._create_menu_and_toolbar()
        self._init_ui()
        self.retranslate_ui()
        self._load_collections()

        # Re-apply every text when the language changes
        SCAppLanguage.add_language_listener(self.retranslate_ui)

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

    # ------------------------------------------------------------------ building the window
    def _create_actions(self):
        """Create shared QActions for menus and toolbars (texts: see retranslate_ui)."""
        # Action: New Collection
        icon_add = self._get_icon("new.png", QStyle.StandardPixmap.SP_FileDialogNewFolder)
        self.action_new_coll = QAction(icon_add, "", self)
        self.action_new_coll.triggered.connect(self._create_collection)

        # Action: Delete Collection
        icon_del = self._get_icon("trash.png", QStyle.StandardPixmap.SP_TrashIcon)
        self.action_del_coll = QAction(icon_del, "", self)
        self.action_del_coll.triggered.connect(self._delete_collection)

        # Action: Export Mancolist
        icon_export = self._get_icon("export_to_csv.png", QStyle.StandardPixmap.SP_DialogSaveButton)
        self.action_export_mancolist = QAction(icon_export, "", self)
        self.action_export_mancolist.triggered.connect(self._export_mancolist)

        # Action: Configuration
        icon_config = self._get_icon("config.png", QStyle.StandardPixmap.SP_FileDialogEnd)
        self.action_config = QAction(icon_config, "", self)
        self.action_config.triggered.connect(self._open_settings)

        # Action: User Manual
        icon_help = self._get_icon("help.png", QStyle.StandardPixmap.SP_DialogHelpButton)
        self.action_manual = QAction(icon_help, "", self)
        self.action_manual.triggered.connect(self._open_manual)

        # Action: About
        icon_about = self._get_icon("about.png", QStyle.StandardPixmap.SP_MessageBoxInformation)
        self.action_about = QAction(icon_about, "", self)
        self.action_about.triggered.connect(self._show_about)

        # Action: Exit Application
        icon_exit = self._get_icon("exit.png", QStyle.StandardPixmap.SP_DialogCloseButton)
        self.action_exit = QAction(icon_exit, "", self)
        self.action_exit.setShortcut("Ctrl+Q")
        self.action_exit.triggered.connect(self.close)

    def _create_menu_and_toolbar(self):
        """Build Menu Bar and Top ToolBar."""
        menu_bar = self.menuBar()

        # Collection Menu
        self.collection_menu = menu_bar.addMenu("")
        self.collection_menu.addAction(self.action_new_coll)
        self.collection_menu.addAction(self.action_del_coll)
        self.collection_menu.addSeparator()
        self.collection_menu.addAction(self.action_exit)

        # Tools Menu
        self.tools_menu = menu_bar.addMenu("")
        self.tools_menu.addAction(self.action_export_mancolist)

        # Settings Menu
        self.config_menu = menu_bar.addMenu("")
        self.config_menu.addAction(self.action_config)

        # Help Menu
        self.help_menu = menu_bar.addMenu("")
        self.help_menu.addAction(self.action_manual)
        self.help_menu.addSeparator()
        self.help_menu.addAction(self.action_about)

        # Top ToolBar
        self.toolbar = QToolBar(self)
        self.toolbar.setIconSize(QSize(24, 24))
        self.toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.toolbar)

        self.toolbar.addAction(self.action_new_coll)
        self.toolbar.addAction(self.action_del_coll)
        self.toolbar.addSeparator()
        self.toolbar.addAction(self.action_export_mancolist)
        self.toolbar.addSeparator()
        self.toolbar.addAction(self.action_config)
        self.toolbar.addAction(self.action_manual)

    def _init_ui(self):
        """Initialize main layout and child widgets (texts: see retranslate_ui)."""
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)

        # Labels whose text is set in retranslate_ui: {QLabel: message id}
        self.labels = {}

        def label(msgid):
            lbl = QLabel()
            self.labels[lbl] = msgid
            return lbl

        # Collection Selection Header
        self.coll_box = QGroupBox()
        coll_layout = QHBoxLayout()

        coll_layout.addWidget(label("Active Collection:"))
        self.combo_collections = QComboBox()
        self.combo_collections.currentIndexChanged.connect(self._on_collection_changed)
        coll_layout.addWidget(self.combo_collections, stretch=1)

        self.coll_box.setLayout(coll_layout)
        main_layout.addWidget(self.coll_box)

        # Filter Bar
        self.filter_box = QGroupBox()
        filter_layout = QHBoxLayout()

        filter_layout.addWidget(label("Type:"))
        self.combo_type = QComboBox()
        self.combo_type.currentIndexChanged.connect(self._refresh_table)
        filter_layout.addWidget(self.combo_type)

        filter_layout.addWidget(label("Year:"))
        self.combo_year = QComboBox()
        self.combo_year.currentIndexChanged.connect(self._refresh_table)
        filter_layout.addWidget(self.combo_year)

        filter_layout.addWidget(label("Catalog N°:"))
        self.edit_search_nbr = QLineEdit()
        self.edit_search_nbr.textChanged.connect(self._refresh_table)
        filter_layout.addWidget(self.edit_search_nbr)

        self.filter_box.setLayout(filter_layout)
        main_layout.addWidget(self.filter_box)

        # Main Splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Stamps Table
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSortingEnabled(True)
        self.table.itemSelectionChanged.connect(self._on_stamp_selected)
        splitter.addWidget(self.table)

        # Right Panel (Details + Collection Form)
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)

        # Image Viewer
        self.img_label = QLabel()
        self.img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.img_label.setFixedSize(220, 220)
        self.img_label.setStyleSheet("border: 1px solid #cbd5e0; background: #f7fafc;")
        right_layout.addWidget(self.img_label, alignment=Qt.AlignmentFlag.AlignCenter)

        # Details Box
        self.detail_box = QGroupBox()
        detail_form = QFormLayout()

        self.lbl_year = QLabel("-")
        self.lbl_yvert = QLabel("-")
        self.lbl_valeur = QLabel("-")
        self.lbl_desc = QLabel("-")
        self.lbl_desc.setWordWrap(True)

        detail_form.addRow(label("Year:"), self.lbl_year)
        detail_form.addRow(label("Yvert N°:"), self.lbl_yvert)
        detail_form.addRow(label("Value / Color:"), self.lbl_valeur)
        detail_form.addRow(label("Description 1:"), self.lbl_desc)
        self.detail_box.setLayout(detail_form)
        right_layout.addWidget(self.detail_box)

        # Ownership Form
        self.form_box = QGroupBox()
        form = QFormLayout()

        # Items carry a language-neutral code (stored in the database) and a translated text
        self.combo_status = QComboBox()
        for code, _msgid in STATUS_LABELS:
            self.combo_status.addItem("", code)

        self.combo_condition = QComboBox()
        for code, _msgid in CONDITION_LABELS:
            self.combo_condition.addItem("", code)

        self.spin_qty = QSpinBox()
        self.spin_qty.setRange(1, 100)

        self.spin_price = QDoubleSpinBox()
        self.spin_price.setRange(0, 100000)
        self.spin_price.setSuffix(" €")

        self.txt_notes = QTextEdit()
        self.txt_notes.setMaximumHeight(60)

        form.addRow(label("Status:"), self.combo_status)
        form.addRow(label("Condition:"), self.combo_condition)
        form.addRow(label("Quantity:"), self.spin_qty)
        form.addRow(label("Purchase Price:"), self.spin_price)
        form.addRow(label("Notes:"), self.txt_notes)

        self.btn_save = QPushButton()
        self.btn_save.setStyleSheet("background-color: #2b6cb0; color: white; font-weight: bold;")
        self.btn_save.clicked.connect(self._save_stamp_status)
        form.addRow(self.btn_save)

        self.form_box.setLayout(form)
        right_layout.addWidget(self.form_box)

        splitter.addWidget(right_panel)
        splitter.setSizes([650, 350])

        main_layout.addWidget(splitter)

    # ------------------------------------------------------------------ translation
    def retranslate_ui(self):
        """Set every visible text in the current language.
        Called when the window is built and after each change of language."""
        self.setWindowTitle(_("StampCatalogue - Stamp Collection Manager"))

        # Actions (menus and toolbar)
        for action, text, tip in (
                (self.action_new_coll, "New Collection...", "Create a new collection"),
                (self.action_del_coll, "Delete Collection", "Delete current collection"),
                (self.action_export_mancolist, "Export Mancolist (Excel)", "Export missing stamps to Excel"),
                (self.action_config, "Settings...", "Configure application settings"),
                (self.action_manual, "User Manual", "Open user manual"),
                (self.action_about, "About", "About StampCatalogue"),
                (self.action_exit, "Quit", "Quit application")):
            action.setText(_(text))
            action.setToolTip(_(tip))

        self.collection_menu.setTitle(_("&Collection"))
        self.tools_menu.setTitle(_("&Tools"))
        self.config_menu.setTitle(_("&Configuration"))
        self.help_menu.setTitle(_("&Help"))
        self.toolbar.setWindowTitle(_("Main Toolbar"))

        # Group boxes, labels, fields
        self.coll_box.setTitle(_("Collection Selection"))
        self.filter_box.setTitle(_("Catalogue Filters"))
        self.detail_box.setTitle(_("Stamp Details"))
        self.form_box.setTitle(_("Collection Status"))
        for lbl, msgid in self.labels.items():
            lbl.setText(_(msgid))
        self.edit_search_nbr.setPlaceholderText(_("e.g. 154..."))
        self.btn_save.setText(_("Save to Collection"))
        if not self.has_photo:
            self.img_label.setText(_("No Photo Available"))

        # Combo boxes: only the texts change, the selected item is kept
        for combo, labels in ((self.combo_status, STATUS_LABELS), (self.combo_condition, CONDITION_LABELS)):
            for i, (_code, msgid) in enumerate(labels):
                combo.setItemText(i, _(msgid))
        for combo in (self.combo_type, self.combo_year):
            if combo.count() and combo.itemData(0) is None:
                combo.blockSignals(True)
                combo.setItemText(0, _("All"))
                combo.blockSignals(False)

        # Table: headers and the translated status column
        self.table.setHorizontalHeaderLabels([
            _("Yvert N°"),
            _("Year"),
            _("Type"),
            _("Value / Color"),
            _("Description"),
            _("Status")
        ])
        self._refresh_table()

    # ------------------------------------------------------------------ settings, help
    def _open_settings(self):
        """Open settings dialog, save the INI configuration and apply the language at once."""
        old_db_type = self.config_manager.get_db_type()
        dialog = ConfigurationDialog(
            current_lang=self.config_manager.get_language(),
            current_db_type=old_db_type,
            parent=self
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_lang, new_db_type = dialog.get_settings()
            self.config_manager.set_settings(new_lang, new_db_type)

            # Switch the whole interface to the new language (retranslate_ui is notified)
            if new_lang != get_language():
                SCAppLanguage.set_language(new_lang)

            if new_db_type != old_db_type:
                QMessageBox.information(
                    self,
                    _("Settings Saved"),
                    _("The database type will be used the next time the application starts.")
                )

    def _show_about(self):
        """Display about dialog."""
        dialog = SCAboutDlg(self)
        dialog.exec()

    def _open_manual(self):
        """Open language-specific manual file."""
        lang = get_language()
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

    # ------------------------------------------------------------------ collections
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

        # First item "All" carries no data (None = no filter), whatever its translated text
        self.combo_type.blockSignals(True)
        self.combo_type.clear()
        self.combo_type.addItem(_("All"), None)
        for stamp_type in self.country_db.load_types():
            self.combo_type.addItem(str(stamp_type), stamp_type)
        self.combo_type.blockSignals(False)

        self.combo_year.blockSignals(True)
        self.combo_year.clear()
        self.combo_year.addItem(_("All"), None)
        for year in self.country_db.load_years():
            self.combo_year.addItem(str(year), year)
        self.combo_year.blockSignals(False)

        self._refresh_table()

    def _refresh_table(self, *args):
        """Refresh catalogue table records based on active filters."""
        if not self.country_db or self.current_collection_id is None:
            return

        stamps = self.country_db.get_stamps(
            stamp_type=self.combo_type.currentData(),
            year=self.combo_year.currentData(),
            search_nbr=self.edit_search_nbr.text().strip()
        )

        user_items = self.central_db.get_collection_items(self.current_collection_id)

        self.table.blockSignals(True)
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
            status_code = user_data[0] if user_data else STATUS_NOT_OWNED
            status_item = QTableWidgetItem(status_label(status_code))

            if status_code == STATUS_OWNED:
                status_item.setForeground(Qt.GlobalColor.darkGreen)
            elif status_code == STATUS_WANTED:
                status_item.setForeground(Qt.GlobalColor.red)

            self.table.setItem(row_idx, 5, status_item)

            full_data = stamp + (user_data,)
            self.table.item(row_idx, 0).setData(Qt.ItemDataRole.UserRole, full_data)

        self.table.setSortingEnabled(True)

        # Keep the selected stamp selected (without reloading the form being edited)
        if self.selected_nbr is not None:
            for row in range(self.table.rowCount()):
                if self.table.item(row, 0).text() == str(self.selected_nbr):
                    self.table.selectRow(row)
                    break
        self.table.blockSignals(False)

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
            self._select_code(self.combo_status, status)
            self._select_code(self.combo_condition, cond)
            self.spin_qty.setValue(qty if qty else 1)
            self.spin_price.setValue(price if price else 0.0)
            self.txt_notes.setPlainText(notes if notes else "")
        else:
            self._select_code(self.combo_status, STATUS_NOT_OWNED)
            self.combo_condition.setCurrentIndex(0)
            self.spin_qty.setValue(1)
            self.spin_price.setValue(0.0)
            self.txt_notes.clear()

        self._load_stamp_image(nbr, stype, sub_nbr)

    @staticmethod
    def _select_code(combo, code):
        """Select the combo item that carries the given code (first item if unknown)."""
        idx = combo.findData(code)
        combo.setCurrentIndex(idx if idx >= 0 else 0)

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
                self.has_photo = True
                return

        self.has_photo = False
        self.img_label.setText(_("No Photo Available"))

    def _save_stamp_status(self):
        """Save ownership details to the collection database."""
        if not self.selected_nbr or self.current_collection_id is None:
            return

        status = self.combo_status.currentData()
        if status == STATUS_NOT_OWNED:
            self.central_db.remove_item(self.current_collection_id, self.selected_nbr)
        else:
            self.central_db.save_item(
                collection_id=self.current_collection_id,
                stamp_nbr=self.selected_nbr,
                status=status,
                condition=self.combo_condition.currentData(),
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
            status = user_data[0] if user_data else STATUS_MISSING

            if not user_data or status in (STATUS_WANTED, STATUS_MISSING):
                notes = user_data[4] if user_data else ""
                mancolist.append((nbr, year, stype, valcolor, desc, status_label(status), notes))

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
        self.has_photo = False
        self.img_label.setText(_("No Photo Available"))

    def closeEvent(self, event):
        """Clean up active database handles upon exit."""
        SCAppLanguage.remove_language_listener(self.retranslate_ui)
        if self.central_db:
            self.central_db.close()
        if self.country_db:
            self.country_db.close()
        event.accept()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    # Qt's own texts (Yes / No buttons of the message boxes...) in the configured language
    SCAppLanguage.install_qt_translator()
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
