"""
Delegates Module
----------------
Contains custom item delegates for table editing.
"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QStyledItemDelegate, QComboBox


class TypeDelegate(QStyledItemDelegate):
    """Délégué permettant d'afficher une QComboBox éditable dans la colonne Type du tableau."""

    def __init__(self, parent=None, main_window=None):
        super().__init__(parent)
        self.main_window = main_window

    def createEditor(self, parent, option, index):
        """Crée l'éditeur QComboBox éditable lors du double-clic sur la cellule."""
        combo = QComboBox(parent)
        combo.setEditable(True)

        if self.main_window and self.main_window.db_adapter:
            combo.addItems(self.main_window.db_adapter.load_types())

        return combo

    def setEditorData(self, editor, index):
        """Initialise la valeur de la QComboBox avec le texte actuel de la cellule."""
        current_text = index.model().data(index, Qt.ItemDataRole.DisplayRole)
        editor.setCurrentText(str(current_text or ""))

    def setModelData(self, editor, model, index):
        """Applique la modification dans le tableau et enregistre le changement."""
        new_text = editor.currentText().strip()
        model.setData(index, new_text, Qt.ItemDataRole.EditRole)

        if self.main_window:
            self.main_window.edit_type.setCurrentText(new_text)
            self.main_window._on_apply_record_edit()