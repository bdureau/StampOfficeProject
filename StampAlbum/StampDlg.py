"""
Stamp Dialog Module
-------------------
Dialog window for selecting and creating stamp items from catalog Databases.

Author: Boris du Reau
"""
import sys
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
from pathlib import Path
from PyQt6 import QtGui
from PyQt6.QtWidgets import (
    QMessageBox,
    QComboBox, QRadioButton, QGroupBox, QLabel, QHBoxLayout, QListView,
    QDialog, QPushButton, QListWidget,
    QLineEdit, QFormLayout, QVBoxLayout, QDialogButtonBox, QPlainTextEdit
)
from PyQt6.QtGui import QPixmap, QStandardItem
from Databases import DB
from Stamp import Stamp
from SAAppPaths import get_config_value, get_photos_dir, get_images_dir, list_countries

import gettext
from AppLanguage import get_language
# Set up gettext localization
gettext.find("StampDlg")
translate = gettext.translation('StampDlg', localedir='locale', languages=[get_language()], fallback=True)
translate.install()
_ = translate.gettext

class StampDlg(QDialog):
    """Dialog window for selecting catalog stamps and inserting them into the page."""
    def __init__(self, lastStampObj=None, scene=None, parent=None):
        super(StampDlg, self).__init__(parent)
        self.setWindowTitle(_("Create new stamp"))

        self.base_dir = self._get_app_dir()
        self.images_dir = self._get_resource_dir("Images")

        icon_path = self.images_dir / "stamp_book.png"
        if icon_path.exists():
            self.setWindowIcon(QtGui.QIcon(str(icon_path)))
        else:
            self.setWindowIcon(QtGui.QIcon('stamp_book.png'))

        self.currentStampNbr = ""
        self.fullPhotoPath = None
        self.db = None
        # La scène doit être connue AVANT createDlg (les boutons Create l'utilisent)
        self.scene = scene
        if lastStampObj is None:
            lastStampObj = {'country': None, 'type': None, 'year': None, 'nbr': None}
        self.createDlg(lastStampObj)
        if lastStampObj['country'] is not None:
            print(lastStampObj['country'])
            print(lastStampObj['year'])
            print(lastStampObj['type'])
            print(lastStampObj['nbr'])

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

    def get_configured_country(self) -> str:
        """Read default country setting from stamp_album.cfg configuration file."""
        return get_config_value('default country', "France")

    def onStampCurrentChanged(self, current, previous):
        """Met à jour l'affichage du timbre lors d'un changement de sélection (souris ou clavier)."""
        if current.isValid():
            self.stampClicked(current)

    def keyPressEvent(self, e):
        """Laisse Qt gérer nativement la navigation au clavier via le selectionModel."""
        super().keyPressEvent(e)

    def createDlg(self, lastStampObj):
        """Initialize dialog layout, widgets, and form controls."""
        # Mount box types section
        vLayout1 = QVBoxLayout()
        pochettesType = QLabel(_("Pochette type"))
        self.pochetteList = QListWidget()
        self.pochetteList.setMaximumWidth(150)
        vLayout1.addWidget(pochettesType)
        vLayout1.addWidget(self.pochetteList)

        # where to go if the pochette is clicked
        self.pochetteList.itemClicked.connect(self.pochetteClicked)

        # Years
        years = QLabel(_("Years:"))
        self.yearsList = QListWidget()
        self.yearsList.setMaximumWidth(100)
        vLayoutYear = QVBoxLayout()

        vLayoutYear.addWidget(years)
        vLayoutYear.addWidget(self.yearsList)

        # where to go if the year is clicked
        self.yearsList.itemClicked.connect(self.yearClicked)
        self.yearsList.itemChanged.connect(self.yearClicked)
        self.yearsList.currentItemChanged.connect(self.yearChanged)


        # stamp nbr
        stampNbr = QLabel(_("Stamp nbr:"))
        self.stampNbrList = QListView()
        self.stampNbrList.setMaximumWidth(100)
        vLayoutStampNbr = QVBoxLayout()

        vLayoutStampNbr.addWidget(stampNbr)
        vLayoutStampNbr.addWidget(self.stampNbrList)

        # where to go if the stamp is clicked
        #self.stampNbrList.clicked.connect(self.stampClicked)

        # hlayout to group them
        hLayout2 = QHBoxLayout()
        hLayout2.addLayout(vLayoutYear)
        hLayout2.addLayout(vLayoutStampNbr)

        # vlayout to group them
        vLayout2 = QVBoxLayout()
        vLayout2.addLayout(hLayout2)
        # preview stamp photo
        self.photo = QLabel()
        self.photo.setFixedHeight(200)
        self.photo.setFixedWidth(200)
        self.photo.setPixmap(QPixmap(""))
        vLayout2.addWidget(self.photo)

        self.stampTypeCombo = QComboBox()

        self.stampTypeCombo.setMaximumWidth(250)
        self.stampTypeCombo.currentTextChanged.connect(self.stampTypeClicked)


        self.selectedCountryCombo = QComboBox()
        self.selectedCountryCombo.setMaximumWidth(100)

        self.selectedCountryCombo.currentTextChanged.connect(self.countryClicked)

        self.eWidth = QLineEdit()
        self.eWidth.setMaximumWidth(100)
        self.eHeight = QLineEdit()
        self.eHeight.setMaximumWidth(100)
        self.eYear = QLineEdit()
        self.eYear.setMaximumWidth(100)
        self.eValue = QLineEdit()
        self.eValue.setMaximumWidth(150)

        # descChoiceLbl = QLabel("Select the description to use:")
        rbtn1 = QRadioButton(_('Use description 1'))
        rbtn2 = QRadioButton(_('Use description 2'))
        rbtn3 = QRadioButton(_('Use description 1 and 2'))
        rbtn4 = QRadioButton(_('No description'))

        rbtn3.setChecked(True)

        rbGroup = QGroupBox(_("Select the description to use:"))
        vbox = QVBoxLayout()
        rbGroup.setLayout(vbox)

        vbox.addWidget(rbtn1)
        vbox.addWidget(rbtn2)
        vbox.addWidget(rbtn3)
        vbox.addWidget(rbtn4)

        self.eStampDescription = QPlainTextEdit()
        self.eStampDescription.setFixedHeight(50)
        self.eStampDescription2 = QPlainTextEdit()
        self.eStampDescription2.setFixedHeight(50)


        fLayout = QFormLayout()
        fLayout.addRow(_("Stamp type:"), self.stampTypeCombo)
        fLayout.addRow(_("Selected country:"), self.selectedCountryCombo)
        fLayout.addRow(_("Witdh:"), self.eWidth)
        fLayout.addRow(_("Height:"), self.eHeight)
        fLayout.addRow(_("Year:"), self.eYear)
        fLayout.addRow(_("Value:"), self.eValue)
        fLayout.addRow(_("Stamp description:"), self.eStampDescription)
        fLayout.addRow(_("Stamp description2:"), self.eStampDescription2)

        fLayout.addRow("", rbGroup)

        # ok /cancel button
        createButton = QPushButton(self.tr(_("&Create")))
        createButton.setDefault(True)

        createButton2 = QPushButton(self.tr(_("&Create from size")))
        createButton2.setDefault(True)

        okButton = QPushButton(self.tr(_("&Done")))

        buttonBox = QDialogButtonBox(Qt.Orientation.Horizontal)

        buttonBox.addButton(createButton, QDialogButtonBox.ButtonRole.ActionRole)
        buttonBox.addButton(createButton2, QDialogButtonBox.ButtonRole.ActionRole)
        buttonBox.addButton(okButton, QDialogButtonBox.ButtonRole.ActionRole)

        okButton.clicked.connect(self.accept)
        createButton.clicked.connect(self.createStamp)
        createButton2.clicked.connect(self.createStamp2)

        hLayoutAll = QHBoxLayout()
        hLayoutAll.addLayout(vLayout1)
        hLayoutAll.addLayout(vLayout2)
        hLayoutAll.addLayout(fLayout)

        vLayoutAll = QVBoxLayout()
        vLayoutAll.addLayout(hLayoutAll)
        vLayoutAll.addWidget(buttonBox)
        self.setLayout(vLayoutAll)

        self.populateData(lastStampObj)

    def populateData(self,lastStampObj):
        if lastStampObj and lastStampObj.get('country'):
            target_country  = lastStampObj['country']
        else:
            target_country  = self.get_configured_country()

        #print("target_country:" + target_country )
        # get the list of countries from the Databases available
        self.db = None
        # Liste des pays selon le moteur configuré (.db pour sqlite, .mdb pour Access)
        self.stampCountries = list_countries()

        if not self.stampCountries:
            QMessageBox.warning(self, _("No database"),
                                _("No country database was found in the 'Databases' folder."))
            return

        # Ouvrir directement le pays cible (évite d'ouvrir le 1er puis de changer)
        if target_country not in self.stampCountries:
            target_country = self.stampCountries[0]

        try:
            self.db = DB(target_country)
        except Exception as e:
            QMessageBox.critical(self, _("Database error"), str(e))
            self.db = None
            return

        # Remplir la combo sans déclencher countryClicked pendant l'initialisation
        self.selectedCountryCombo.blockSignals(True)
        self.selectedCountryCombo.addItems(self.stampCountries)
        self.selectedCountryCombo.setCurrentText(target_country)
        self.selectedCountryCombo.blockSignals(False)

        self.currentCountry = target_country
        print("self.currentCountry:"+self.currentCountry)
        # open the first country
        #self.db = DB(self.currentCountry)

        # get the list of availble stamp box from the master db
        retBoxList = self.db.loadBoxList()
        self.pochetteList.clear()
        self.pochetteList.addItems(retBoxList)

        # get the stamp type from the current country open DB
        retStampType = self.db.loadStampType()
        self.stampTypeCombo.clear()
        self.stampTypeCombo.addItems(retStampType)

        if lastStampObj['type'] is not None:
            self.stampTypeCombo.setCurrentText(lastStampObj['type'])

        # get the available years from the current country open DB
        retYearList = self.db.loadYearList(self.stampTypeCombo.currentText())
        self.yearsList.clear()
        self.yearsList.addItems(retYearList)

        if lastStampObj['year'] is not None:
            yearItem = self.yearsList.findItems(lastStampObj['year'], Qt.MatchFlag.MatchExactly)
            if len(yearItem) > 0:
                self.yearsList.setCurrentItem(yearItem[0])
            else:
                self.yearsList.setCurrentRow(0)

        if len(self.yearsList.selectedItems()) < 1:
            self.yearsList.setCurrentRow(0)

        if self.yearsList.currentItem() is None:
            return

        # load all available stamp number for the current year
        retStampNbrList = self.db.loadStampList(self.stampTypeCombo.currentText(), self.yearsList.currentItem().text())

        model = QtGui.QStandardItemModel(self.stampNbrList)
        myIndex = 0
        i = 0
        for it in retStampNbrList:

            myitem = QStandardItem(str(it[1]))
            myitem.setData(it[0], 256)
            model.appendRow(myitem)

            if lastStampObj['nbr'] is not None:
                if str(it[1]) == lastStampObj['nbr']:
                    myIndex = i
            i = i + 1
        self.stampNbrList.setModel(model)
        # Connexion du modèle de sélection pour gérer le clavier et la souris
        self.stampNbrList.selectionModel().currentChanged.connect(self.onStampCurrentChanged)

        if len(self.stampNbrList.selectedIndexes()) < 1:
            self.stampNbrList.setCurrentIndex(self.stampNbrList.model().index(myIndex, 0))


        retitem = self.stampNbrList.model().item(myIndex, 0)
        if retitem is None:
            return
        self.currentStampNbr = retitem.text()

        # get pochette for the current stamp
        stampType = self.stampTypeCombo.currentText()
        stampYear = self.yearsList.currentItem().text()
        stampNbr = retitem.text()
        stampKey = retitem.data(256)

        retPochette = self.db.getPochette(stampNbr, stampType, stampYear, stampKey)

        if len(retPochette) > 0:
            pochetteItem = self.pochetteList.findItems(retPochette[0], Qt.MatchFlag.MatchExactly)

            if len(pochetteItem) > 0:
                self.pochetteList.setCurrentItem(pochetteItem[0])
            else:
                self.pochetteList.setCurrentRow(0)

        self.setStampInfo(retitem)

    def yearChanged(self, year):
        """Callback triggered when active selected year item changes."""
        if year is not None:
            self.yearClicked(year)

    # year has changed, let's retrieve all the stamps for that year
    def yearClicked(self, year):
        """Update stamp list view according to selected year."""
        if year.text() != "" and self.yearsList.currentItem() is not None:
            if self.db is not None:
                # load all available stamp number for the current year
                retStampNbrList = self.db.loadStampList(self.stampTypeCombo.currentText(),
                                                        self.yearsList.currentItem().text())

                model = QtGui.QStandardItemModel(self.stampNbrList)
                for it in retStampNbrList:
                    myitem = QStandardItem(str(it[1]))
                    myitem.setData(it[0], 256)
                    model.appendRow(myitem)

                self.stampNbrList.setModel(model)
                # Connexion du modèle de sélection pour gérer le clavier et la souris
                self.stampNbrList.selectionModel().currentChanged.connect(self.onStampCurrentChanged)

                if len(self.stampNbrList.selectedIndexes()) < 1:
                    self.stampNbrList.setCurrentIndex(self.stampNbrList.model().index(0, 0))

                retitem = self.stampNbrList.model().item(0, 0)
                if retitem is not None:
                    self.currentStampNbr = retitem.text()
                    self.setStampInfo(retitem)

    # stamp has changed let's change the image and all the stamp properties
    def stampClicked(self, index):
        """Update preview image and form fields when a stamp is clicked."""
        retitem = self.stampNbrList.model().item(index.row(), 0)
        if retitem is None:
            return
        self.setStampInfo(retitem)
        self.currentStampNbr = retitem.text()

    def setStampInfo(self, retitem):
        """Fetch stamp information and load image preview from country database."""
        if self.db is not None and retitem is not None and self.yearsList.currentItem() is not None:
            # get pochette for the current stamp
            stampType = self.stampTypeCombo.currentText()
            stampYear = self.yearsList.currentItem().text()
            stampNbr = retitem.text()
            stampKey = retitem.data(256)

            retPochette = self.db.getPochette(stampNbr, stampType, stampYear, stampKey)

            if len(retPochette) > 0:
                print(retPochette[0])
                pochetteItem = self.pochetteList.findItems(retPochette[0], Qt.MatchFlag.MatchExactly)

                if len(pochetteItem) > 0:
                    self.pochetteList.setCurrentItem(pochetteItem[0])
                else:
                    self.pochetteList.setCurrentRow(0)
            else:
                self.pochetteList.setCurrentRow(0)

            # blank stamp info
            self.eWidth.setText("")
            self.eHeight.setText("")
            self.eYear.setText("")
            self.eValue.setText("")
            self.eStampDescription.setPlainText("")
            self.eStampDescription2.setPlainText("")

            # get all stamp info
            retStampInfo = self.db.stampChanged(stampNbr, stampKey)

            if len(retStampInfo) > 0:
                # nbr,year,valuecolor, stampDescription,width, height,sub_nbr,stampDescription1
                # Les champs NULL de la base reviennent en None : on les convertit en ""
                info = ["" if v is None else str(v) for v in retStampInfo]
                self.eWidth.setText(info[4])
                self.eHeight.setText(info[5])
                self.eYear.setText(info[1])
                self.eValue.setText(info[2])
                self.eStampDescription.setPlainText(info[7])
                self.eStampDescription2.setPlainText(info[3])

                stampSubNbr = retStampInfo[6]

                # photoName = self.getPhotoName(str(stampNbr), str(stampType), stampSubNbr)
                # # Chemin portable (Windows / macOS / Linux)
                # photo_path = get_photos_dir() / self.currentCountry / photoName
                # if not photo_path.is_file():
                #     photo_path = get_images_dir() / "blanc.jpg"
                # self.fullPhotoPath = str(photo_path)
                photoName = self.getPhotoName(str(stampNbr), str(stampType), stampSubNbr)  # [cite: 18]
                folder_path = get_photos_dir() / self.currentCountry  # [cite: 18]
                photo_path = folder_path / photoName  # [cite: 18]

                # Si le fichier exact n'est pas trouvé sous Linux, on cherche insensiblement à la casse
                if not photo_path.is_file() and folder_path.is_dir():
                    target_name_lower = photoName.lower()
                    # Recherche du fichier correspondant dans le dossier en ignorant la casse
                    matching_file = next((f for f in folder_path.iterdir() if f.name.lower() == target_name_lower),
                                         None)

                    if matching_file:
                        photo_path = matching_file

                # Si toujours introuvable, fallback sur l'image blanche
                if not photo_path.is_file():  # [cite: 18]
                    photo_path = get_images_dir() / "blanc.jpg"  # [cite: 18]

                self.fullPhotoPath = str(photo_path)  # [cite: 18]
                if self.photo is not None:
                    pix = QPixmap(self.fullPhotoPath)
                    if not pix.isNull():
                        if pix.width() > pix.height():
                            self.photo.setPixmap(pix.scaledToWidth(200))
                        else:
                            self.photo.setPixmap(pix.scaledToHeight(200))

    def countryClicked(self, country):
        """Switch country database connection when country dropdown selection changes."""
        if country != "":
            if self.db is not None:
                try:
                    self.db.OpenCountryDB(country)
                except Exception as e:
                    QMessageBox.critical(self, _("Database error"), str(e))
                    return
                self.currentCountry = country
                # get the stamp type from the current country open DB
                self.stampTypeCombo.clear()
                retStampType = self.db.loadStampType()
                self.stampTypeCombo.addItems(retStampType)

    def stampTypeClicked(self, stampType):
        """Reload available issue years when stamp type selection changes."""
        if stampType != "":
            if self.db is not None:
                # get the available years from the current country open DB
                self.yearsList.clear()
                retYearList = self.db.loadYearList(self.stampTypeCombo.currentText())
                self.yearsList.addItems(retYearList)

                if len(self.yearsList.selectedItems()) < 1 and self.yearsList.count() > 0:
                    self.yearsList.setCurrentRow(0)
                    self.yearsList.currentItem().setSelected(True)
                    #self.yearClicked(self.yearsList.currentItem().text())

    def pochetteClicked(self, item):
        """Callback for pochette list item selection."""
        print("Current pochette %s" % item.text())

    def getPhotoName(self, stampNumber, stampType, stampSubNbr):
        """Generate relative photo image file name based on stamp category prefix."""
        #nbr = ""
        subNbr = ""

        if stampSubNbr is not None:
            subNbr = "-" + str(stampSubNbr)

        type = str(stampNumber)[0:2]


        # Aérien
        if type == "A ":
            nbr = "T01-030-" + stampNumber[2:len(stampNumber)] + subNbr + ".jpg"
        # Bloc feuillet
        elif type == "BF":
            nbr = "T01-080-" + stampNumber[3:len(stampNumber)] + subNbr + ".jpg"
        # Service
        elif type == "S ":
            nbr = "T01-170-" + stampNumber[2:len(stampNumber)] + subNbr + ".jpg"
        # bloc carnet
        elif type == "BC":
            nbr = "T01-000-BC" + stampNumber[3:len(stampNumber)] + subNbr + ".jpg"
        # bande
        elif type == "B ":
            nbr = "T01-000-B" + stampNumber[2:len(stampNumber)] + subNbr + ".jpg"
        # paire
        elif type == "P ":
            nbr = "T01-000-P" + stampNumber[2:len(stampNumber)] + subNbr + ".jpg"
        # préoblitéré
        elif type == "PR":
            nbr = "T01-420-" + stampNumber[3:len(stampNumber)] + subNbr + ".jpg"
        # franchise militaire
        elif type == "FM":
            nbr = "T01-190-" + stampNumber[3:len(stampNumber)] + subNbr + ".jpg"
        # taxe
        elif type == "TA":
            nbr = "T01-270-" + stampNumber[3:len(stampNumber)] + subNbr + ".jpg"
        # croix rouge
        elif type == "CR":
            nbr = "T01-565-" + stampNumber[3:len(stampNumber)] + subNbr + ".jpg"
        # Guerre
        elif type == "GU":
            nbr = "T01-150-" + stampNumber[3:len(stampNumber)] + subNbr + ".jpg"
        # Alsace Lorraine
        elif type == "AL":
            nbr = "T01-110-" + stampNumber[3:len(stampNumber)] + subNbr + ".jpg"
        # Journaux
        elif type == "JN":
            nbr = "T01-160-" + stampNumber[3:len(stampNumber)] + subNbr + ".jpg"
        # Petit colis
        elif type == "PC":
            nbr = "T01-120-" + stampNumber[3:len(stampNumber)] + subNbr + ".jpg"
        # colis postaux
        elif type == "CP":
            nbr = "T01-130-" + stampNumber[3:len(stampNumber)] + subNbr + ".jpg"
        # Fiscaux postaux
        elif type == "FP":
            nbr = "T01-140-" + stampNumber[3:len(stampNumber)] + subNbr + ".jpg"
        # CFA
        elif type == "CF":
            nbr = "T01-180-CF-" + stampNumber[3:len(stampNumber)] + subNbr + ".jpg"

        # colonies
        elif type == "CO":
            nbr = "T01-200-" + stampNumber[3:len(stampNumber)] + subNbr + ".jpg"
        # télégraphe
        elif type == "TL":
            nbr = "T01-210-" + stampNumber[3:len(stampNumber)] + subNbr + ".jpg"
        # telegraphe militaire
        elif type == "MT":
            nbr = "T01-211-" + stampNumber[3:len(stampNumber)] + subNbr + ".jpg"
        # téléphone
        elif type == "TE":
            nbr = "T01-215-" + stampNumber[3:len(stampNumber)] + subNbr + ".jpg"
        # Greve
        elif type == "GR":
            nbr = "T01-220-" + stampNumber[3:len(stampNumber)] + subNbr + ".jpg"
        # Poste Montenegrine
        elif type == "PM":
            nbr = "T01-230-" + stampNumber[3:len(stampNumber)] + subNbr + ".jpg"
        # fictifs
        elif type == "F ":
            nbr = "T01-240-" + stampNumber[2:len(stampNumber)] + subNbr + ".jpg"
        # fictifs
        elif type == "F-":
            nbr = "T01-000-F" + stampNumber[2:len(stampNumber)] + subNbr + ".jpg"
        # bienfaisance
        elif type == "BI":
            nbr = "T01-250-" + stampNumber[2:len(stampNumber)] + subNbr + ".jpg"
        # mandat
        elif type == "MA":
            nbr = "T01-251-" + stampNumber[2:len(stampNumber)] + subNbr + ".jpg"
        # distributeur
        elif type == "DI":
            nbr = "T01-260-" + stampNumber[2:len(stampNumber)] + subNbr + ".jpg"
        # instruction
        #elif type == "CI":
        #    nbr = "T01-250-" + stampNumber[2:len(stampNumber)] + subNbr + ".jpg"
        else:
            #COURS INSTRUCTION
            if stampType == "COURS INSTRUCTION":
                nbr = "T01-252-" + stampNumber + subNbr + ".jpg"
            #préoblitéré
            elif stampType == "Préoblitéré COURS INSTRUCTION":
                nbr = "T01-253-" + stampNumber + subNbr + ".jpg"
            elif stampType == "RECOUVREMENT COURS INSTRUCTION":
                nbr = "T01-254-" + stampNumber + subNbr + ".jpg"
            elif stampType.strip() == "TAXES COURS INSTRUCTION":
                nbr = "T01-255-" + stampNumber + subNbr + ".jpg"
            elif stampType.strip() == "POSTE AERIENNE MILITAIRE":
                nbr = "T01-256-" + stampNumber + subNbr + ".jpg"
            #Poste
            else:
                nbr = "T01-000-" + stampNumber + subNbr + ".jpg"

        return nbr

    def getBoxInfo(self, box):
        """Retrieve box dimensions from database by mount box name."""
        ret = []
        if self.db is not None:
            ret = self.db.getCurrentBox(box)
        return ret

    def createStamp(self):
        """Instantiate stamp graphic item on scene based on mount box dimensions."""
        stampDesc = self.eStampDescription.toPlainText()

        stampValue = self.eValue.text()
        pixmap = ""
        if self.fullPhotoPath is not None:
            pixmap = self.fullPhotoPath

        if self.pochetteList.currentItem() is None:
            return
        ret = self.getBoxInfo(self.pochetteList.currentItem().text())
        if len(ret) < 2:
            return
        width = ret[0]
        height = ret[1]

        stampNbr = self.currentStampNbr

        stamp = Stamp()
        stamp.createStamp(self.scene, str(stampNbr), str(stampValue), str(stampDesc),
                          float(width), float(height), float(0), float(0), pixmap)

    def createStamp2(self):
        """Instantiate stamp graphic item using custom explicit width/height dimensions."""
        stampDesc = self.eStampDescription.toPlainText()

        stampValue = self.eValue.text()
        pixmap = ""
        if self.fullPhotoPath is not None:
            pixmap = self.fullPhotoPath

        #ret = self.getBoxInfo(self.pochetteList.currentItem().text())
        #self.eWidth.setText("")
        #self.eHeight.setText("")
        try:
            width = float(self.eWidth.text().replace(",", "."))
            height = float(self.eHeight.text().replace(",", "."))
        except ValueError:
            QMessageBox.warning(self, _("Invalid size"), _("Width and height must be numbers (mm)."))
            return

        stampNbr = self.currentStampNbr

        stamp = Stamp()
        stamp.createStamp(self.scene, str(stampNbr), str(stampValue), str(stampDesc),
                          float(width), float(height), float(0), float(0), pixmap)