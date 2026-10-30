"""
Graphics View Module
--------------------
Handles custom QGraphicsView display, scene scaling, object serialization,
deserialization, and clipboard actions (Copy, Cut, Paste).

Author: Boris du Reau
"""

import importlib
from PyQt6.QtCore import QPointF, Qt, QPoint, QByteArray, QRectF
from PyQt6 import QtCore, QtWidgets, QtGui
from PyQt6.QtWidgets import QGraphicsTextItem, QGraphicsRectItem, QGraphicsPixmapItem, QGraphicsItemGroup
from PyQt6.QtGui import QFont, QTextCursor, QTextBlockFormat, QPen, QColor, QShortcut, QTransform

custom_mimeType = "application/x-qgraphicsitems"

# Offset applied to pasted items (in scene pixels) so they do not overlap the original
PASTE_OFFSET = 20.0


def item_to_ds(it, ds):
    if not isinstance(it, QtWidgets.QGraphicsItem):
        return

    ds.writeQString(it.__class__.__module__)
    ds.writeQString(it.__class__.__name__)

    flags_val = int(it.flags().value) if hasattr(it.flags(), 'value') else int(it.flags())
    ds.writeInt(flags_val)

    ds << it.pos()
    ds.writeQString(str(it.data(0)) if it.data(0) is not None else "")

    if it.__class__.__name__ == "QGraphicsTextItem":
        ds.writeQString(it.toPlainText())
        ds.writeBool(it.font().bold())
        ds.writeBool(it.font().italic())
        ds.writeBool(it.font().strikeOut())
        ds.writeBool(it.font().underline())
        ds.writeInt(it.font().pointSize())

    if it.__class__.__name__ == "QGraphicsItemGroup" and it.data(0) == "stampGroup":
        for child in it.childItems():
            if child.__class__.__name__ == "QGraphicsRectItem":
                ds.writeQString(child.__class__.__name__)
                ds << child.boundingRect()
                ds << child.pos()
                ds.writeInt(child.pen().width())
                ds << child.pen().color()
                ds.writeInt(int(child.data(1)) if child.data(1) else 0)
                ds.writeInt(int(child.data(2)) if child.data(2) else 0)

            if child.__class__.__name__ == "QGraphicsTextItem":
                ds.writeQString(child.__class__.__name__)
                ds.writeQString(child.toPlainText())
                ds << child.pos()
                font = child.font()
                ds.writeBool(font.bold())
                ds.writeBool(font.italic())
                ds.writeBool(font.strikeOut())
                ds.writeBool(font.underline())
                ds.writeInt(font.pointSize())

            if child.__class__.__name__ == "QGraphicsPixmapItem":
                ds.writeQString(child.__class__.__name__)
                ds.writeQVariant(child.pixmap())
                ds << child.pos()

    ds.writeFloat(it.opacity())
    ds.writeFloat(it.rotation())
    ds.writeFloat(it.scale())

    if isinstance(it, QtWidgets.QAbstractGraphicsShapeItem):
        ds << it.brush() << it.pen()
    if isinstance(it, QtWidgets.QGraphicsPathItem):
        ds << it.path()

def ds_to_item(ds):
    module_name = ds.readQString()
    class_name = ds.readQString()
    mod = importlib.import_module(module_name)
    it = getattr(mod, class_name)()
    flags = QtWidgets.QGraphicsItem.GraphicsItemFlag(ds.readInt())
    pos = QtCore.QPointF()
    ds >> pos
    it.setData(0, ds.readQString())

    if class_name == "QGraphicsTextItem":
        it.setPlainText(ds.readQString())
        font = QFont()
        font.setBold(ds.readBool())
        font.setItalic(ds.readBool())
        font.setStrikeOut(ds.readBool())
        font.setUnderline(ds.readBool())
        font.setPointSize(ds.readInt())
        it.setFont(font)

    if class_name == "QGraphicsItemGroup" and it.data(0) == "stampGroup":
        class1 = ds.readQString()
        bounding_rect = QtCore.QRectF()
        ds >> bounding_rect
        pos1 = QtCore.QPointF()
        ds >> pos1
        pen = QPen()
        pen.setWidth(ds.readInt())
        penColor = QtGui.QColor()
        ds >> penColor
        pen.setColor(penColor)
        boxW = ds.readInt()
        boxWidth = boxW / (25.4 / 96.0)
        boxH = ds.readInt()
        boxHeight = boxH / (25.4 / 96.0)

        class2 = ds.readQString()
        pos2 = QtCore.QPointF()
        desc = ds.readQString()
        ds >> pos2
        font2 = QFont()
        font2.setBold(ds.readBool())
        font2.setItalic(ds.readBool())
        font2.setStrikeOut(ds.readBool())
        font2.setUnderline(ds.readBool())
        font2.setPointSize(ds.readInt())

        class3 = ds.readQString()
        pos3 = QtCore.QPointF()
        nbr = ds.readQString()
        ds >> pos3
        font3 = QFont()
        font3.setBold(ds.readBool())
        font3.setItalic(ds.readBool())
        font3.setStrikeOut(ds.readBool())
        font3.setUnderline(ds.readBool())
        font3.setPointSize(ds.readInt())

        class4 = ds.readQString()
        pos4 = QtCore.QPointF()
        value = ds.readQString()
        ds >> pos4
        font4 = QFont()
        font4.setBold(ds.readBool())
        font4.setItalic(ds.readBool())
        font4.setStrikeOut(ds.readBool())
        font4.setUnderline(ds.readBool())
        font4.setPointSize(ds.readInt())

        class5 = ds.readQString()
        pos5 = QtCore.QPointF()
        pixmap = ds.readQVariant()
        ds >> pos5

        stampDesc = QGraphicsTextItem(desc)
        stampDesc.setData(0, "stampDesc")
        stampDesc.setPos(pos2.x(), pos2.y())
        stampDesc.setFont(font2)
        stampDesc.setFlags(QGraphicsTextItem.GraphicsItemFlag.ItemIsMovable |
                           QGraphicsTextItem.GraphicsItemFlag.ItemIsSelectable)
        stampDesc.setTextWidth(stampDesc.boundingRect().size().width())
        cursor = stampDesc.textCursor()
        cursor.select(QTextCursor.SelectionType.Document)
        format = QTextBlockFormat()
        format.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cursor.mergeBlockFormat(format)
        cursor.clearSelection()
        stampDesc.setTextCursor(cursor)

        stampBox = QGraphicsRectItem(0, 0, boxWidth, boxHeight)
        stampBox.setPos(pos2.x() + (stampDesc.boundingRect().size().width() / 2) - (boxWidth / 2),
                        pos2.y() + stampDesc.boundingRect().size().height() + 20)

        stampBox.setPen(pen)
        stampBox.setFlags(QGraphicsRectItem.GraphicsItemFlag.ItemIsMovable |
                          QGraphicsRectItem.GraphicsItemFlag.ItemIsSelectable)
        stampBox.setData(0, "stampBox")
        stampBox.setData(1, boxW)
        stampBox.setData(2, boxH)

        if not isinstance(pixmap, QtGui.QPixmap):
            pixmap = QtGui.QPixmap()
        pixmapitem = QGraphicsPixmapItem(pixmap)
        # Image vide (photo introuvable) : éviter la division par zéro
        pix_w = pixmapitem.boundingRect().size().width()
        pix_h = pixmapitem.boundingRect().size().height()
        if pix_w > 0 and pix_h > 0:
            image_scale = min((boxWidth - 4) / pix_w, (boxHeight - 4) / pix_h)
        else:
            image_scale = 1.0
        pixmapitem.setScale(image_scale)

        pixmapitem.setPos(pos2.x() + (stampDesc.boundingRect().size().width() / 2) - (image_scale * pixmapitem.boundingRect().size().width() / 2),
                          pos2.y() + stampDesc.boundingRect().size().height() + 20 + (boxHeight / 2 - (image_scale * pixmapitem.boundingRect().size().height()) / 2))
        pixmapitem.setData(0, "pixmapItem")

        stampNbr = QGraphicsTextItem(nbr)
        stampNbr.setData(0, "stampNbr")
        stampNbr.setFont(font3)

        stampNbr.setFlags(QGraphicsTextItem.GraphicsItemFlag.ItemIsMovable |
                          QGraphicsTextItem.GraphicsItemFlag.ItemIsSelectable)

        stampNbr.setTextWidth(stampNbr.boundingRect().size().width())
        cursor = stampNbr.textCursor()
        cursor.select(QTextCursor.SelectionType.Document)
        format = QTextBlockFormat()
        format.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cursor.mergeBlockFormat(format)
        cursor.clearSelection()
        stampNbr.setTextCursor(cursor)

        stampNbr.setPos(pos2.x() + stampDesc.boundingRect().size().width() / 2 - stampNbr.boundingRect().size().width() / 2,
                        pos2.y() + stampDesc.boundingRect().size().height() + 20 + boxHeight)

        stampValue = QGraphicsTextItem(value)
        stampValue.setData(0, "stampValue")
        stampValue.setFont(font4)
        stampValue.setFlags(QGraphicsTextItem.GraphicsItemFlag.ItemIsMovable |
                            QGraphicsTextItem.GraphicsItemFlag.ItemIsSelectable)

        stampValue.setTextWidth(stampValue.boundingRect().size().width())
        cursor = stampValue.textCursor()
        cursor.select(QTextCursor.SelectionType.Document)
        format = QTextBlockFormat()
        format.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cursor.mergeBlockFormat(format)
        cursor.clearSelection()
        stampValue.setTextCursor(cursor)

        stampValue.setPos(
             pos2.x() + (stampDesc.boundingRect().size().width() / 2) - (stampValue.boundingRect().size().width() / 2),
             pos2.y() + stampDesc.boundingRect().size().height() + 20 + boxHeight +
             stampNbr.boundingRect().size().height() + 0)

        it.addToGroup(stampBox)
        it.addToGroup(stampDesc)
        it.addToGroup(stampNbr)
        it.addToGroup(stampValue)
        it.addToGroup(pixmapitem)
        it.setFlags(QGraphicsItemGroup.GraphicsItemFlag.ItemIsMovable |
                    QGraphicsItemGroup.GraphicsItemFlag.ItemIsSelectable)

    it.setFlags(flags)
    it.setPos(pos)
    it.setOpacity(ds.readFloat())
    it.setRotation(ds.readFloat())
    it.setScale(ds.readFloat())

    if isinstance(it, QtWidgets.QAbstractGraphicsShapeItem):
        pen, brush = QtGui.QPen(), QtGui.QBrush()
        ds >> brush
        ds >> pen
        it.setPen(pen)
        it.setBrush(brush)
    if isinstance(it, QtWidgets.QGraphicsPathItem):
        path = QtGui.QPainterPath()
        ds >> path
        it.setPath(path)

    return it


class GraphicsView(QtWidgets.QGraphicsView):
    """Custom QGraphicsView with dynamic scaling and clipboard support."""

    zoomChanged = QtCore.pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setScene(parent)

        # Enable smooth anti-aliased rendering during scaling
        self.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        self.setRenderHint(QtGui.QPainter.RenderHint.SmoothPixmapTransform)

        # Enable horizontal and vertical scrollbars when scene overflows viewport
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        # Background color for the area outside the page
        self.setBackgroundBrush(QtGui.QBrush(QtGui.QColor("#a0a0a0")))

        self.current_zoom = 1.0

        QShortcut(
            QtGui.QKeySequence(QtGui.QKeySequence.StandardKey.Copy),
            self,
            activated=self.copy_items
        )
        QShortcut(
             QtGui.QKeySequence(QtGui.QKeySequence.StandardKey.Paste),
             self,
             activated=self.paste_items,
        )

        # Allow drag and drop on the view
        self.setAcceptDrops(True)


    def drawBackground(self, painter: QtGui.QPainter, rect: QtCore.QRectF):
        """Draw a white page rectangle over a dark grey workspace background."""
        # 1. Fill the viewport background with dark grey
        painter.fillRect(rect, QtGui.QColor("#808080"))

        scene = self.scene()
        if scene:
            scene_rect = scene.sceneRect()

            # 2. Draw a subtle drop shadow under the page
            shadow_rect = scene_rect.translated(4, 4)
            painter.fillRect(shadow_rect, QtGui.QColor("#404040"))

            # 3. Use the scene backgroundBrush (white or grid) instead of a fixed white
            painter.fillRect(scene_rect, scene.backgroundBrush())

            # 4. Draw a fine grey border around the white page
            painter.setPen(QtGui.QPen(QtGui.QColor("#b0b0b0"), 1))
            painter.drawRect(scene_rect)

    def setZoomFactor(self, factor: float):
        """Set viewport zoom factor bounded between 25% (0.25) and 200% (2.0)."""
        factor = max(0.25, min(2.0, factor))

        # Avoid any unnecessary re-execution
        if abs(self.current_zoom - factor) < 0.001:
            return

        self.current_zoom = factor

        # Apply transformation
        t = QTransform()
        t.scale(factor, factor)
        self.setTransform(t)

        self.zoomChanged.emit(int(factor * 100))

    def getZoomFactor(self) -> float:
        return self.current_zoom

    @QtCore.pyqtSlot()
    def copy_items(self):
        mimedata = QtCore.QMimeData()
        ba = QtCore.QByteArray()
        ds = QtCore.QDataStream(ba, QtCore.QIODevice.OpenModeFlag.WriteOnly)
        for it in self.scene().selectedItems():
            item_to_ds(it, ds)

        mimedata.setData(custom_mimeType, ba)
        clipboard = QtGui.QGuiApplication.clipboard()
        clipboard.setMimeData(mimedata)

    @QtCore.pyqtSlot()
    def paste_items(self):
        clipboard = QtGui.QGuiApplication.clipboard()
        mimedata = clipboard.mimeData()
        if mimedata.hasFormat(custom_mimeType):
            ba = mimedata.data(custom_mimeType)
            ds = QtCore.QDataStream(ba)
            scene = self.scene()

            pasted = []
            while not ds.atEnd():
                it = ds_to_item(ds)
                it.moveBy(PASTE_OFFSET, PASTE_OFFSET)
                pasted.append(it)
            if not pasted:
                return

            # A single Ctrl+Z undoes the entire paste operation
            has_undo = hasattr(scene, "undoStack") and hasattr(scene, "addItemWithUndo")
            if has_undo:
                scene.undoStack.beginMacro("Paste")
            for it in pasted:
                if has_undo:
                    scene.addItemWithUndo(it, "Paste")
                else:
                    scene.addItem(it)
            if has_undo:
                scene.undoStack.endMacro()

            # Select pasted items to allow immediate movement
            scene.clearSelection()
            for it in pasted:
                it.setSelected(True)

    def mouseDoubleClickEvent_old(self, event: QtGui.QMouseEvent):
        """Intercept double clicks at the viewport level before Qt unselects text items."""
        scene_pos = self.mapToScene(event.pos())

        # Retrieve ALL items under cursor to avoid inadvertently grabbing the border
        items_under_cursor = self.scene().items(scene_pos)

        target_item = None
        for item in items_under_cursor:
            # Ignore page borders and background when searching for a clickable item
            top_item = item
            while top_item.parentItem() is not None:
                top_item = top_item.parentItem()

            data_type = str(top_item.data(0)) if top_item.data(0) is not None else ""
            if data_type != "borderGroup":
                target_item = top_item
                break  # Found a priority element (text, stamp, image...)

        # If no priority item is found, take the first one if available
        if not target_item and items_under_cursor:
            target_item = items_under_cursor[0]
            while target_item.parentItem() is not None:
                target_item = target_item.parentItem()

        if target_item:
            data_type = str(target_item.data(0)) if target_item.data(0) is not None else ""
            if data_type != "borderGroup":
                if hasattr(self.scene(), "editObject"):
                    self.scene().editObject(target_item)
                    event.accept()
                    return

        super().mouseDoubleClickEvent(event)

    def mouseDoubleClickEvent(self, event: QtGui.QMouseEvent):
        """Intercept double clicks at the viewport level before Qt unselects text items."""
        scene_pos = self.mapToScene(event.pos())
        items_under_cursor = self.scene().items(scene_pos)

        target_item = None
        for item in items_under_cursor:
            top_item = item
            while top_item.parentItem() is not None:
                top_item = top_item.parentItem()

            data_type = str(top_item.data(0)) if top_item.data(0) is not None else ""
            if data_type != "borderGroup":
                target_item = top_item
                break

        if target_item:
            if hasattr(self.scene(), "editObject"):
                self.scene().editObject(target_item)
                event.accept()
                return

        super().mouseDoubleClickEvent(event)

    def dragEnterEvent(self, event: QtGui.QDragEnterEvent):
        """Accept drag if contents contain a valid image file."""
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                ext = url.toLocalFile().lower()
                if ext.endswith(('.png', '.jpg', '.jpeg', '.bmp', '.webp', '.tiff', '.tif')):
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dragMoveEvent(self, event: QtGui.QDragMoveEvent):
        """Maintain drag authorization while hovering."""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QtGui.QDropEvent):
        """Drop the image onto the scene at mouse position."""
        if event.mimeData().hasUrls():
            scene_pos = self.mapToScene(event.position().toPoint())
            dropped = False
            for url in event.mimeData().urls():
                file_path = url.toLocalFile()
                if file_path.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.webp', '.tiff', '.tif')):
                    scene = self.scene()
                    if hasattr(scene, "addImageAt"):
                        scene.addImageAt(file_path, scene_pos.x(), scene_pos.y())
                        dropped = True
            if dropped:
                event.acceptProposedAction()
                return
        event.ignore()

class GuideLineItem(QtWidgets.QGraphicsLineItem):
    """Non-printable visual marker (guideline), movable along a single axis."""

    def __init__(self, orientation, pos_val):
        super().__init__()
        self.orientation = orientation
        self.setData(0, "guideLine")

        # Guideline style (dashed cyan)
        pen = QtGui.QPen(QtGui.QColor(0, 200, 255, 200), 1.5, Qt.PenStyle.DashLine)
        pen.setCosmetic(True)  # Always remains thin regardless of zoom level
        self.setPen(pen)
        self.setZValue(1000)  # Always above other items

        self.setFlags(QtWidgets.QGraphicsItem.GraphicsItemFlag.ItemIsMovable |
                      QtWidgets.QGraphicsItem.GraphicsItemFlag.ItemIsSelectable |
                      QtWidgets.QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges)

        # Arbitrary pseudo-infinite dimensions
        if orientation == Qt.Orientation.Horizontal:
            self.setLine(-10000, 0, 10000, 0)
            self.setPos(0, pos_val)
            self.setCursor(Qt.CursorShape.SplitVCursor)
        else:
            self.setLine(0, -10000, 0, 10000)
            self.setPos(pos_val, 0)
            self.setCursor(Qt.CursorShape.SplitHCursor)

    def itemChange(self, change, value):
        """Constrain movement on the opposite axis."""
        if change == QtWidgets.QGraphicsItem.GraphicsItemChange.ItemPositionChange:
            new_pos = value
            if self.orientation == Qt.Orientation.Horizontal:
                return QtCore.QPointF(self.pos().x(), new_pos.y())
            else:
                return QtCore.QPointF(new_pos.x(), self.pos().y())
        return super().itemChange(change, value)

    def shape(self):
        """Enlarge hit-test area to grab the line more easily with the mouse."""
        path = QtGui.QPainterPath()
        if self.orientation == Qt.Orientation.Horizontal:
            path.addRect(-10000, -5, 20000, 10)
        else:
            path.addRect(-5, -10000, 10, 20000)
        return path


class RulerWidget(QtWidgets.QWidget):
    """Millimeter ruler that dynamically adjusts to zoom and scrolling."""

    def __init__(self, view, orientation, parent=None):
        super().__init__(parent)
        self.view = view
        self.orientation = orientation
        if self.orientation == Qt.Orientation.Horizontal:
            self.setFixedHeight(20)
        else:
            self.setFixedWidth(20)

        self.setMouseTracking(True)
        # Refresh rulers on viewport scroll
        self.view.verticalScrollBar().valueChanged.connect(self.update)
        self.view.horizontalScrollBar().valueChanged.connect(self.update)

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.fillRect(self.rect(), QtGui.QColor("#f4f4f4"))
        painter.setPen(Qt.GlobalColor.black)
        painter.setFont(QtGui.QFont("Sans", 7))

        viewport_rect = self.view.viewport().rect()
        scale = self.view.transform().m11()
        px_per_mm = 96.0 / 25.4

        if self.orientation == Qt.Orientation.Horizontal:
            start_scene = self.view.mapToScene(viewport_rect.topLeft()).x()
            end_scene = self.view.mapToScene(viewport_rect.topRight()).x()
        else:
            start_scene = self.view.mapToScene(viewport_rect.topLeft()).y()
            end_scene = self.view.mapToScene(viewport_rect.bottomLeft()).y()

        mm_start = int(start_scene / px_per_mm) - 1
        mm_end = int(end_scene / px_per_mm) + 1

        for mm in range(mm_start, mm_end):
            scene_pos = mm * px_per_mm

            if self.orientation == Qt.Orientation.Horizontal:
                screen_pos = self.view.mapFromScene(QtCore.QPointF(scene_pos, 0)).x()
            else:
                screen_pos = self.view.mapFromScene(QtCore.QPointF(0, scene_pos)).y()

            if mm % 10 == 0:
                length = 10
                if self.orientation == Qt.Orientation.Horizontal:
                    painter.drawText(int(screen_pos + 2), 10, str(mm))
                else:
                    painter.save()
                    painter.translate(10, int(screen_pos - 2))
                    painter.rotate(-90)
                    painter.drawText(0, 0, str(mm))
                    painter.restore()
            elif mm % 5 == 0:
                length = 7
            else:
                length = 4

            if self.orientation == Qt.Orientation.Horizontal:
                painter.drawLine(int(screen_pos), 20 - length, int(screen_pos), 20)
            else:
                painter.drawLine(20 - length, int(screen_pos), 20, int(screen_pos))

    def mousePressEvent(self, event):
        """Create a new guideline on the scene upon clicking the ruler."""
        if event.button() == Qt.MouseButton.LeftButton:
            # Retrieve visual viewport origin in scene coordinates
            scene_pt = self.view.mapToScene(0, 0)

            if self.orientation == Qt.Orientation.Horizontal:
                guide = GuideLineItem(Qt.Orientation.Horizontal, scene_pt.y() + 10)
            else:
                guide = GuideLineItem(Qt.Orientation.Vertical, scene_pt.x() + 10)

            self.view.scene().addItem(guide)
            self.view.scene().clearSelection()
            guide.setSelected(True)
            self.view.scene().update()
