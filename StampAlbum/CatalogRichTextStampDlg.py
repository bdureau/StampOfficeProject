"""
Catalog Rich Text Stamp Dialog Module
-------------------------------------
Dialog window allowing the selection of stamps from catalog databases
and formatting their texts using live rich-text editors before inserting
them as autonomous RichTextStamp objects.

Author: Boris du Reau
"""

import gettext
from pathlib import Path
from PyQt6.QtCore import Qt
from PyQt6 import QtGui
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel,
    QLineEdit, QListWidget, QListView, QPushButton, QDialogButtonBox,
    QMessageBox, QComboBox, QRadioButton, QGroupBox
)
from PyQt6.QtGui import QPixmap, QStandardItem

from Databases import DB
from SAAppPaths import (
    get_images_dir, get_photos_dir, get_config_value, list_countries
)
from Stamp import RichTextStamp
from RichTextStampDlg import RichTextEditorWidget
from AppLanguage import get_language

# Setup gettext localization
gettext.find("CatalogRichTextStampDlg")
translate = gettext.translation('CatalogRichTextStampDlg', localedir='locale', languages=[get_language()], fallback=True)
translate.install()
_ = translate.gettext


class CatalogRichTextStampDlg(QDialog):
    """Dialog to query stamps from catalog databases and customize their rich text."""

    def __init__(self, lastStampObj=None, scene=None, parent=None):
        super(CatalogRichTextStampDlg, self).__init__(parent)
        self.setWindowTitle(_("Create Catalog Rich Text Stamp"))
        self.resize(920, 640)

        self.scene = scene
        self.db = None
        self.currentStampNbr = ""
        self.fullPhotoPath = None

        if lastStampObj is None:
            lastStampObj = {'country': None, 'type': None, 'year': None, 'nbr': None}

        self._create_ui()
        self.populateData(lastStampObj)

    def get_configured_country(self) -> str:
        """Read default country from configuration file."""
        return get_config_value('default country', "France")

    def _create_ui(self):
        # 1. Left Column: Mount boxes list from master DB
        vLayout1 = QVBoxLayout()
        vLayout1.addWidget(QLabel(_("Pochette type:")))
        self.pochetteList = QListWidget()
        self.pochetteList.setMaximumWidth(140)
        self.pochetteList.itemClicked.connect(self._sync_dimensions_from_box)
        vLayout1.addWidget(self.pochetteList)

        # 2. Middle Column: Catalog selection (Country, Type, Year, Stamp Number, Image preview)
        vLayoutCatalog = QVBoxLayout()

        self.selectedCountryCombo = QComboBox()
        self.selectedCountryCombo.currentTextChanged.connect(self.countryClicked)
        vLayoutCatalog.addWidget(QLabel(_("Country:")))
        vLayoutCatalog.addWidget(self.selectedCountryCombo)

        self.stampTypeCombo = QComboBox()
        self.stampTypeCombo.currentTextChanged.connect(self.stampTypeClicked)
        vLayoutCatalog.addWidget(QLabel(_("Stamp type:")))
        vLayoutCatalog.addWidget(self.stampTypeCombo)

        # Year and Stamp Number lists in horizontal layout
        hLayoutLists = QHBoxLayout()

        vLayoutYear = QVBoxLayout()
        vLayoutYear.addWidget(QLabel(_("Years:")))
        self.yearsList = QListWidget()
        self.yearsList.setMaximumWidth(90)
        self.yearsList.itemClicked.connect(self.yearClicked)
        self.yearsList.currentItemChanged.connect(self.yearChanged)
        vLayoutYear.addWidget(self.yearsList)
        hLayoutLists.addLayout(vLayoutYear)

        vLayoutStampNbr = QVBoxLayout()
        vLayoutStampNbr.addWidget(QLabel(_("Stamp nbr:")))
        self.stampNbrList = QListView()
        self.stampNbrList.setMaximumWidth(90)
        vLayoutStampNbr.addWidget(self.stampNbrList)
        hLayoutLists.addLayout(vLayoutStampNbr)

        vLayoutCatalog.addLayout(hLayoutLists)

        # Image preview
        self.photo = QLabel()
        self.photo.setFixedHeight(160)
        self.photo.setFixedWidth(180)
        self.photo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.photo.setStyleSheet("border: 1px dashed #aaa; background: #fafafa;")
        vLayoutCatalog.addWidget(self.photo)

        # Dimensions in mm
        form_dims = QFormLayout()
        self.eWidth = QLineEdit()
        self.eWidth.setMaximumWidth(80)
        self.eHeight = QLineEdit()
        self.eHeight.setMaximumWidth(80)
        form_dims.addRow(_("Width (mm):"), self.eWidth)
        form_dims.addRow(_("Height (mm):"), self.eHeight)
        vLayoutCatalog.addLayout(form_dims)

        # Description selector radio buttons
        self.rbtn1 = QRadioButton(_("Description 1"))
        self.rbtn2 = QRadioButton(_("Description 2"))
        self.rbtn3 = QRadioButton(_("Both (1 & 2)"))
        self.rbtn4 = QRadioButton(_("None"))
        self.rbtn3.setChecked(True)

        self.rbtn1.toggled.connect(self._update_description_choice)
        self.rbtn2.toggled.connect(self._update_description_choice)
        self.rbtn3.toggled.connect(self._update_description_choice)
        self.rbtn4.toggled.connect(self._update_description_choice)

        rbGroup = QGroupBox(_("Description format:"))
        vbox_rb = QVBoxLayout(rbGroup)
        vbox_rb.addWidget(self.rbtn1)
        vbox_rb.addWidget(self.rbtn2)
        vbox_rb.addWidget(self.rbtn3)
        vbox_rb.addWidget(self.rbtn4)
        vLayoutCatalog.addWidget(rbGroup)

        # 3. Right Column: Three dedicated RichTextEditorWidget editors
        vbox_editors = QVBoxLayout()
        self.editor_desc = RichTextEditorWidget(_("Description (Title)"), default_font_size=10, editor_height=65)
        self.editor_nbr = RichTextEditorWidget(_("Stamp Number"), default_font_size=8, editor_height=45)
        self.editor_val = RichTextEditorWidget(_("Nominal Value"), default_font_size=8, editor_height=45)

        vbox_editors.addWidget(self.editor_desc)
        vbox_editors.addWidget(self.editor_nbr)
        vbox_editors.addWidget(self.editor_val)

        # Master horizontal layout
        h_all = QHBoxLayout()
        h_all.addLayout(vLayout1)
        h_all.addLayout(vLayoutCatalog)
        h_all.addLayout(vbox_editors)

        # Action Buttons
        btn_create = QPushButton(_("&Create"))
        btn_create.setDefault(True)
        btn_create.clicked.connect(self.createStamp)

        btn_close = QPushButton(_("&Done"))
        btn_close.clicked.connect(self.accept)

        bb = QDialogButtonBox(Qt.Orientation.Horizontal)
        bb.addButton(btn_create, QDialogButtonBox.ButtonRole.ActionRole)
        bb.addButton(btn_close, QDialogButtonBox.ButtonRole.ActionRole)

        btn_create.setText(_("&Create"))
        btn_close.setText(_("&Done"))

        main_layout = QVBoxLayout(self)
        main_layout.addLayout(h_all)
        main_layout.addWidget(bb)

        # Cache variables for the raw descriptions
        self._raw_desc1 = ""
        self._raw_desc2 = ""

    def populateData(self, lastStampObj):
        """Populate databases, countries, categories and initial selection."""
        if lastStampObj and lastStampObj.get('country'):
            target_country = lastStampObj['country']
        else:
            target_country = self.get_configured_country()

        self.stampCountries = list_countries()
        if not self.stampCountries:
            QMessageBox.warning(self, _("No database"), _("No country database was found in 'Databases'."))
            return

        if target_country not in self.stampCountries:
            target_country = self.stampCountries[0]

        try:
            self.db = DB(target_country)
        except Exception as e:
            QMessageBox.critical(self, _("Database error"), str(e))
            self.db = None
            return

        self.selectedCountryCombo.blockSignals(True)
        self.selectedCountryCombo.addItems(self.stampCountries)
        self.selectedCountryCombo.setCurrentText(target_country)
        self.selectedCountryCombo.blockSignals(False)
        self.currentCountry = target_country

        # Load boxes
        retBoxList = self.db.loadBoxList()
        self.pochetteList.clear()
        self.pochetteList.addItems(retBoxList)

        # Load stamp types
        retStampType = self.db.loadStampType()
        self.stampTypeCombo.clear()
        self.stampTypeCombo.addItems(retStampType)
        if lastStampObj.get('type'):
            self.stampTypeCombo.setCurrentText(lastStampObj['type'])

        # Load years
        retYearList = self.db.loadYearList(self.stampTypeCombo.currentText())
        self.yearsList.clear()
        self.yearsList.addItems(retYearList)
        if lastStampObj.get('year'):
            yearItem = self.yearsList.findItems(lastStampObj['year'], Qt.MatchFlag.MatchExactly)
            if yearItem:
                self.yearsList.setCurrentItem(yearItem[0])
            else:
                self.yearsList.setCurrentRow(0)
        else:
            self.yearsList.setCurrentRow(0)

        if self.yearsList.currentItem() is None:
            return

        # Load stamps for active year
        retStampNbrList = self.db.loadStampList(
            self.stampTypeCombo.currentText(), self.yearsList.currentItem().text()
        )
        model = QtGui.QStandardItemModel(self.stampNbrList)
        myIndex = 0
        for i, it in enumerate(retStampNbrList):
            myitem = QStandardItem(str(it[1]))
            myitem.setData(it[0], 256)
            model.appendRow(myitem)
            if lastStampObj.get('nbr') and str(it[1]) == lastStampObj['nbr']:
                myIndex = i

        self.stampNbrList.setModel(model)
        self.stampNbrList.selectionModel().currentChanged.connect(self.onStampCurrentChanged)

        if self.stampNbrList.model().rowCount() > 0:
            self.stampNbrList.setCurrentIndex(self.stampNbrList.model().index(myIndex, 0))
            retitem = self.stampNbrList.model().item(myIndex, 0)
            if retitem:
                self.currentStampNbr = retitem.text()
                self.setStampInfo(retitem)

    def onStampCurrentChanged(self, current, previous):
        if current.isValid():
            retitem = self.stampNbrList.model().item(current.row(), 0)
            if retitem:
                self.currentStampNbr = retitem.text()
                self.setStampInfo(retitem)

    def yearChanged(self, current):
        if current is not None:
            self.yearClicked(current)

    def yearClicked(self, item):
        if item and item.text() and self.db:
            retStampNbrList = self.db.loadStampList(
                self.stampTypeCombo.currentText(), self.yearsList.currentItem().text()
            )
            model = QtGui.QStandardItemModel(self.stampNbrList)
            for it in retStampNbrList:
                myitem = QStandardItem(str(it[1]))
                myitem.setData(it[0], 256)
                model.appendRow(myitem)

            self.stampNbrList.setModel(model)
            self.stampNbrList.selectionModel().currentChanged.connect(self.onStampCurrentChanged)

            if model.rowCount() > 0:
                self.stampNbrList.setCurrentIndex(model.index(0, 0))
                retitem = model.item(0, 0)
                if retitem:
                    self.currentStampNbr = retitem.text()
                    self.setStampInfo(retitem)

    def countryClicked(self, country):
        if country and self.db:
            try:
                self.db.OpenCountryDB(country)
            except Exception as e:
                QMessageBox.critical(self, _("Database error"), str(e))
                return
            self.currentCountry = country
            self.stampTypeCombo.clear()
            self.stampTypeCombo.addItems(self.db.loadStampType())

    def stampTypeClicked(self, stampType):
        if stampType and self.db:
            self.yearsList.clear()
            self.yearsList.addItems(self.db.loadYearList(stampType))
            if self.yearsList.count() > 0:
                self.yearsList.setCurrentRow(0)

    def _sync_dimensions_from_box(self, item):
        if item and self.db:
            box_info = self.db.getCurrentBox(item.text())
            if len(box_info) >= 2:
                self.eWidth.setText(str(box_info[0]))
                self.eHeight.setText(str(box_info[1]))

    def _update_description_choice(self):
        """Update the description rich-text editor based on active radio button."""
        if self.rbtn1.isChecked():
            chosen = self._raw_desc1
        elif self.rbtn2.isChecked():
            chosen = self._raw_desc2
        elif self.rbtn3.isChecked():
            chosen = f"{self._raw_desc1} {self._raw_desc2}".strip()
        else:
            chosen = ""
        self.editor_desc.set_html(chosen)

    def setStampInfo(self, retitem):
        """Fetch stamp information, sync mount box, image thumbnail, and rich-text editors."""
        if not self.db or not retitem or not self.yearsList.currentItem():
            return

        stampType = self.stampTypeCombo.currentText()
        stampYear = self.yearsList.currentItem().text()
        stampNbr = retitem.text()
        stampKey = retitem.data(256)

        # Synchronize mount box
        retPochette = self.db.getPochette(stampNbr, stampType, stampYear, stampKey)
        if retPochette:
            pochetteItem = self.pochetteList.findItems(retPochette[0], Qt.MatchFlag.MatchExactly)
            if pochetteItem:
                self.pochetteList.setCurrentItem(pochetteItem[0])
            else:
                self.pochetteList.setCurrentRow(0)
        else:
            self.pochetteList.setCurrentRow(0)

        # Retrieve stamp database row
        retStampInfo = self.db.stampChanged(stampNbr, stampKey)
        if retStampInfo:
            info = ["" if v is None else str(v) for v in retStampInfo]
            self.eWidth.setText(info[4])
            self.eHeight.setText(info[5])

            self._raw_desc1 = info[7]
            self._raw_desc2 = info[3]
            self._update_description_choice()

            # Set Number and Value in rich editors
            self.editor_nbr.set_html(stampNbr)
            self.editor_val.set_html(info[2])

            # Resolve image path
            stampSubNbr = retStampInfo[6]
            photoName = self.getPhotoName(str(stampNbr), str(stampType), stampSubNbr)
            folder_path = get_photos_dir() / self.currentCountry
            photo_path = folder_path / photoName

            if not photo_path.is_file() and folder_path.is_dir():
                target_name_lower = photoName.lower()
                matching_file = next((f for f in folder_path.iterdir() if f.name.lower() == target_name_lower), None)
                if matching_file:
                    photo_path = matching_file

            if not photo_path.is_file():
                photo_path = get_images_dir() / "blanc.jpg"

            self.fullPhotoPath = str(photo_path)
            pix = QPixmap(self.fullPhotoPath)
            if not pix.isNull():
                if pix.width() > pix.height():
                    self.photo.setPixmap(pix.scaledToWidth(180, Qt.TransformationMode.SmoothTransformation))
                else:
                    self.photo.setPixmap(pix.scaledToHeight(180, Qt.TransformationMode.SmoothTransformation))

    def getPhotoName(self, stampNumber, stampType, stampSubNbr):
        """Construct standard image file name based on stamp category prefix."""
        subNbr = f"-{stampSubNbr}" if stampSubNbr is not None else ""
        type_prefix = str(stampNumber)[:2]

        mapping = {
            "A ": f"T01-030-{stampNumber[2:]}{subNbr}.jpg",
            "BF": f"T01-080-{stampNumber[3:]}{subNbr}.jpg",
            "S ": f"T01-170-{stampNumber[2:]}{subNbr}.jpg",
            "BC": f"T01-000-BC{stampNumber[3:]}{subNbr}.jpg",
            "B ": f"T01-000-B{stampNumber[2:]}{subNbr}.jpg",
            "P ": f"T01-000-P{stampNumber[2:]}{subNbr}.jpg",
            "PR": f"T01-420-{stampNumber[3:]}{subNbr}.jpg",
            "FM": f"T01-190-{stampNumber[3:]}{subNbr}.jpg",
            "TA": f"T01-270-{stampNumber[3:]}{subNbr}.jpg",
            "CR": f"T01-565-{stampNumber[3:]}{subNbr}.jpg",
            "GU": f"T01-150-{stampNumber[3:]}{subNbr}.jpg",
            "AL": f"T01-110-{stampNumber[3:]}{subNbr}.jpg",
            "JN": f"T01-160-{stampNumber[3:]}{subNbr}.jpg",
            "PC": f"T01-120-{stampNumber[3:]}{subNbr}.jpg",
            "CP": f"T01-130-{stampNumber[3:]}{subNbr}.jpg",
            "FP": f"T01-140-{stampNumber[3:]}{subNbr}.jpg",
            "CF": f"T01-180-CF-{stampNumber[3:]}{subNbr}.jpg",
            "CO": f"T01-200-{stampNumber[3:]}{subNbr}.jpg",
            "TL": f"T01-210-{stampNumber[3:]}{subNbr}.jpg",
            "MT": f"T01-211-{stampNumber[3:]}{subNbr}.jpg",
            "TE": f"T01-215-{stampNumber[3:]}{subNbr}.jpg",
            "GR": f"T01-220-{stampNumber[3:]}{subNbr}.jpg",
            "PM": f"T01-230-{stampNumber[3:]}{subNbr}.jpg",
            "F ": f"T01-240-{stampNumber[2:]}{subNbr}.jpg",
            "F-": f"T01-000-F{stampNumber[2:]}{subNbr}.jpg",
            "BI": f"T01-250-{stampNumber[2:]}{subNbr}.jpg",
            "MA": f"T01-251-{stampNumber[2:]}{subNbr}.jpg",
            "DI": f"T01-260-{stampNumber[2:]}{subNbr}.jpg",
        }

        if type_prefix in mapping:
            return mapping[type_prefix]

        clean_type = stampType.strip()
        if clean_type == "COURS INSTRUCTION":
            return f"T01-252-{stampNumber}{subNbr}.jpg"
        elif clean_type == "Préoblitéré COURS INSTRUCTION":
            return f"T01-253-{stampNumber}{subNbr}.jpg"
        elif clean_type == "RECOUVREMENT COURS INSTRUCTION":
            return f"T01-254-{stampNumber}{subNbr}.jpg"
        elif clean_type == "TAXES COURS INSTRUCTION":
            return f"T01-255-{stampNumber}{subNbr}.jpg"
        elif clean_type == "POSTE AERIENNE MILITAIRE":
            return f"T01-256-{stampNumber}{subNbr}.jpg"

        return f"T01-000-{stampNumber}{subNbr}.jpg"

    def createStamp(self):
        """Validate inputs and instantiate a RichTextStamp object onto the scene."""
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

        pix = QPixmap(self.fullPhotoPath) if self.fullPhotoPath else QPixmap()

        stamp_helper = RichTextStamp()
        stamp_helper.createRichStampPix(
            self.scene,
            nbr_html=nbr_html,
            value_html=val_html,
            desc_html=desc_html,
            boxWidth=width_mm,
            boxHeight=height_mm,
            x=50.0,
            y=50.0,
            pixmap=pix
        )