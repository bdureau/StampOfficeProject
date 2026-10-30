"""
Thumbnails Dialog Module
------------------------
Provides a contact sheet dialog displaying page thumbnails, allowing users
to visually rearrange album pages using drag-and-drop.

Author: Boris du Reau
"""

import gettext
from PyQt6 import QtCore, QtGui
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QListWidget, QListWidgetItem,
    QListView, QAbstractItemView, QDialogButtonBox
)
from AppLanguage import get_language

gettext.find("ThumbnailsDlg")
translate = gettext.translation('ThumbnailsDlg', localedir='locale', languages=[get_language()], fallback=True)
translate.install()
_ = translate.gettext


class ThumbnailsDlg(QDialog):
    """Dialog displaying a contact sheet to rearrange album pages via drag-and-drop."""

    def __init__(self, tabs, parent=None):
        super().__init__(parent)
        self.tabs = tabs
        self.setWindowTitle(_("Organise pages (Thumdnails)"))
        self.resize(850, 600)

        layout = QVBoxLayout(self)

        # Configure list widget to display items as an icon grid
        self.list_widget = QListWidget()
        self.list_widget.setViewMode(QListView.ViewMode.IconMode)
        self.list_widget.setIconSize(QtCore.QSize(180, 260))
        self.list_widget.setResizeMode(QListView.ResizeMode.Adjust)
        self.list_widget.setMovement(QListView.Movement.Snap)
        self.list_widget.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.list_widget.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.list_widget.setSpacing(15)

        # Apply custom styling for the contact sheet grid
        self.list_widget.setStyleSheet("QListWidget { background-color: #d3d3d3; } "
                                       "QListWidget::item { background-color: white; border: 1px solid #aaa; } "
                                       "QListWidget::item:selected { border: 3px solid #2b6cb0; }")

        # Render and add page thumbnails for each tab
        for i in range(tabs.count()):
            widget = tabs.widget(i)
            view = widget.view
            scene = view.scene()

            # Calculate thumbnail dimensions while preserving aspect ratio
            scene_rect = scene.sceneRect()
            aspect_ratio = scene_rect.width() / scene_rect.height()
            thumb_h = 260
            thumb_w = int(thumb_h * aspect_ratio)

            # Render scene onto a QPixmap image
            pixmap = QtGui.QPixmap(thumb_w, thumb_h)
            pixmap.fill(Qt.GlobalColor.white)

            painter = QtGui.QPainter(pixmap)
            painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
            painter.setRenderHint(QtGui.QPainter.RenderHint.SmoothPixmapTransform)

            target_rect = QtCore.QRectF(0, 0, thumb_w, thumb_h)
            scene.render(painter, target_rect, scene_rect)
            painter.end()

            icon = QtGui.QIcon(pixmap)
            item = QListWidgetItem(icon, f"Page {i + 1}")
            item.setData(Qt.ItemDataRole.UserRole, i)  # Store original index
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.list_widget.addItem(item)

        layout.addWidget(self.list_widget)

        # Standard dialog action buttons
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)

        # Localize button labels
        ok_btn = bb.button(QDialogButtonBox.StandardButton.Ok)
        if ok_btn:
            ok_btn.setText(_("OK"))

        cancel_btn = bb.button(QDialogButtonBox.StandardButton.Cancel)
        if cancel_btn:
            cancel_btn.setText(_("Cancel"))

        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        layout.addWidget(bb)

    def get_new_order(self):
        """Return the list of original page indices in their updated order."""
        new_order = []
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            new_order.append(item.data(Qt.ItemDataRole.UserRole))
        return new_order