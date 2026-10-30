"""
Stamp Module
------------
Manages the creation, positioning, rendering, reading, and updating of
grouped stamp items on a QGraphicsScene.

Author: Boris du Reau
"""
import gettext
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QGraphicsRectItem, QGraphicsTextItem, QGraphicsItemGroup, QGraphicsPixmapItem
)
from PyQt6.QtGui import QFont, QPen, QPixmap, QTextCursor, QTextBlockFormat
from AppLanguage import get_language
# Set up gettext localization

gettext.find("Stamp")
translate = gettext.translation('Stamp', localedir='locale', languages=[get_language()], fallback=True)
translate.install()
_ = translate.gettext

class Stamp:
    """Helper class providing methods to generate and modify stamp graphic groups."""
    def __init__(self):
        pass


    def createStamp(self, scene, nbr, value, desc, boxWidth, boxHeight, x, y, picture):
        """
                Load an image file from disk and pass it to createStampPix.

                Args:
                    scene: Active QGraphicsScene instance.
                    nbr (str): Stamp catalogue number.
                    value (str): Nominal value text.
                    desc (str): Description title text.
                    boxWidth (float): Stamp mount width in millimeters.
                    boxHeight (float): Stamp mount height in millimeters.
                    x (float): Scene target X coordinate.
                    y (float): Scene target Y coordinate.
                    picture (str): Path to image asset file.
                """
        pixmap = QPixmap(str(picture)) if picture else QPixmap()

        if pixmap.isNull():
            print(f"Image not found or invalid: {picture}")
        self.createStampPix(scene, nbr, value, desc, boxWidth, boxHeight, x, y, pixmap)

    def createStampPix(self, scene, nbr, value, desc, boxWidth, boxHeight, x, y, pixmap):
        """
        Creates and adds a stamp item group to the scene.

        Args:
            scene: The QGraphicsScene instance.
            nbr (str): Stamp number text.
            value (str): Stamp nominal value text.
            desc (str): Stamp description text.
            boxWidth (float): Width of the stamp mount box in mm.
            boxHeight (float): Height of the stamp mount box in mm.
            x (float): Target X coordinate in the scene.
            y (float): Target Y coordinate in the scene.
            pixmap (QPixmap): Image asset for the stamp.
        """
        # 1. Create description item (Top text)
        stampDesc = QGraphicsTextItem(desc)
        stampDesc.setTextWidth(stampDesc.boundingRect().size().width())

        cursor = stampDesc.textCursor()
        cursor.select(QTextCursor.SelectionType.Document)
        blockFormat = QTextBlockFormat()
        blockFormat.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cursor.mergeBlockFormat(blockFormat)
        cursor.clearSelection()
        stampDesc.setTextCursor(cursor)

        stampDesc.setData(0, "stampDesc")
        stampDesc.setPos(0, 0)
        stampDesc.setFlags(
            QGraphicsTextItem.GraphicsItemFlag.ItemIsMovable |
            QGraphicsTextItem.GraphicsItemFlag.ItemIsSelectable
        )

        # 2. Create rect box item (mm to pixel conversion)
        px_width = boxWidth / (25.4 / 96.0)
        px_height = boxHeight / (25.4 / 96.0)
        stampBox = QGraphicsRectItem(0, 0, px_width, px_height)

        boxPen = QPen()
        boxPen.setWidth(1)
        stampBox.setPen(boxPen)

        stampBox.setFlags(
            QGraphicsRectItem.GraphicsItemFlag.ItemIsMovable |
            QGraphicsRectItem.GraphicsItemFlag.ItemIsSelectable
        )

        # Position box relative to centered description
        box_x = (stampDesc.boundingRect().size().width() / 2) - (px_width / 2)
        box_y = stampDesc.boundingRect().size().height() + 20
        stampBox.setPos(box_x, box_y)
        stampBox.setData(0, "stampBox")
        stampBox.setData(1, boxWidth)
        stampBox.setData(2, boxHeight)

        # 3. Create image pixmap item
        pixmapitem = QGraphicsPixmapItem(pixmap)

        # Calculate scale factor to fit inside the rect box with padding
        if pixmapitem.boundingRect().width() > 0 and pixmapitem.boundingRect().height() > 0:
            scale1 = (stampBox.boundingRect().size().width() - 4) / pixmapitem.boundingRect().size().width()
            scale2 = (stampBox.boundingRect().size().height() - 4) / pixmapitem.boundingRect().size().height()
            image_scale = min(scale1, scale2)
        else:
            image_scale = 1.0

        pixmapitem.setScale(image_scale)

        # Center pixmap inside the box
        pix_x = stampBox.x() + (stampBox.boundingRect().size().width() / 2) - (
                    (image_scale * pixmapitem.boundingRect().size().width()) / 2)
        pix_y = stampBox.y() + (stampBox.boundingRect().size().height() / 2) - (
                    (image_scale * pixmapitem.boundingRect().size().height()) / 2)
        pixmapitem.setPos(pix_x, pix_y)
        pixmapitem.setData(0, "pixmapItem")

        # 4. Create stamp number item (Bottom text 1)
        stampNbr = QGraphicsTextItem(nbr)
        stampNbr.setData(0, "stampNbr")
        stampNbr.setFlags(
            QGraphicsTextItem.GraphicsItemFlag.ItemIsMovable |
            QGraphicsTextItem.GraphicsItemFlag.ItemIsSelectable
        )
        nbr_x = (stampDesc.boundingRect().size().width() / 2) - (stampNbr.boundingRect().size().width() / 2)
        nbr_y = stampDesc.boundingRect().size().height() + 20 + stampBox.boundingRect().size().height()
        stampNbr.setPos(nbr_x, nbr_y)

        # 5. Create stamp value item (Bottom text 2)
        stampValue = QGraphicsTextItem(value)
        stampValue.setData(0, "stampValue")
        stampValue.setFlags(
            QGraphicsTextItem.GraphicsItemFlag.ItemIsMovable |
            QGraphicsTextItem.GraphicsItemFlag.ItemIsSelectable
        )
        val_x = (stampDesc.boundingRect().size().width() / 2) - (stampValue.boundingRect().size().width() / 2)
        val_y = nbr_y + stampNbr.boundingRect().size().height()
        stampValue.setPos(val_x, val_y)

        # 6. Group all items together
        group = QGraphicsItemGroup()
        group.addToGroup(stampBox)
        group.addToGroup(stampDesc)
        group.addToGroup(stampNbr)
        group.addToGroup(stampValue)
        group.addToGroup(pixmapitem)

        group.setFlags(
            QGraphicsItemGroup.GraphicsItemFlag.ItemIsMovable |
            QGraphicsItemGroup.GraphicsItemFlag.ItemIsSelectable
        )
        group.setData(0, "stampGroup")

        # 7. Normalize child positions so group top-left strictly aligns with (0,0)
        children_rect = group.childrenBoundingRect()
        for child in group.childItems():
            child.moveBy(-children_rect.x(), -children_rect.y())

        # 8. Set final absolute position in scene
        group.setPos(x, y)

        if hasattr(scene, 'addItemWithUndo'):
            scene.addItemWithUndo(group, _("Add Stamp"))
        else:
            scene.addItem(group)

    # Create stamp
    # this can be used for old version
    def createStampPixOldVersion(self, scene, nbr, value, desc, boxWidth, boxHeight, x, y, pixmap):
        print("createStampPix")
        stampDesc = QGraphicsTextItem(desc)

        stampDesc.setTextWidth(stampDesc.boundingRect().size().width())

        cursor = stampDesc.textCursor()
        cursor.select(QTextCursor.SelectionType.Document)
        format = QTextBlockFormat()
        format.setAlignment(Qt.AlignmentFlag.AlignCenter)

        cursor.mergeBlockFormat(format)
        cursor.clearSelection()
        stampDesc.setTextCursor(cursor)
        stampDesc.setData(0, "stampDesc")
        stampDesc.setPos(0, 0)

        stampDesc.setFlags(QGraphicsTextItem.GraphicsItemFlag.ItemIsMovable | QGraphicsTextItem.GraphicsItemFlag.ItemIsSelectable)
        print("created desc")

        stampBox = QGraphicsRectItem(0, 0, boxWidth / (25.4 / 96.0), boxHeight / (25.4 / 96.0))

        boxPen = QPen()
        boxPen.setWidth(1)
        stampBox.setPen(boxPen)

        stampBox.setFlags(QGraphicsRectItem.GraphicsItemFlag.ItemIsMovable | QGraphicsRectItem.GraphicsItemFlag.ItemIsSelectable)

        stampBox.setPos((stampDesc.boundingRect().size().width() / 2) - (boxWidth / (25.4 / 96.0) / 2),
                        stampDesc.boundingRect().size().height() + 20)
        stampBox.setData(0, "stampBox")
        stampBox.setData(1, boxWidth)
        stampBox.setData(2, boxHeight)

        pixmapitem = QGraphicsPixmapItem(pixmap)

        #calculate scale
        scale1 = (stampBox.boundingRect().size().width() - 4) / (pixmapitem.boundingRect().size().width())
        scale2 = (stampBox.boundingRect().size().height() - 4) / (pixmapitem.boundingRect().size().height())

        if scale1 < scale2:
            image_scale = scale1
        else:
            image_scale = scale2

        print("image_scale")
        print(image_scale)
        pixmapitem.setScale(image_scale)

        pixmapitem.setPos(stampBox.x() + stampBox.boundingRect().size().width() / 2 - (
                    image_scale * pixmapitem.boundingRect().size().width()) / 2,
                          stampBox.y() + stampBox.boundingRect().size().height() / 2 - (
                    image_scale * pixmapitem.boundingRect().size().height()) / 2)
        pixmapitem.setData(0, "pixmapItem")


        stampNbr = QGraphicsTextItem(nbr)
        stampNbr.setData(0, "stampNbr")
        stampNbr.setFlags(QGraphicsTextItem.GraphicsItemFlag.ItemIsMovable | QGraphicsTextItem.GraphicsItemFlag.ItemIsSelectable)

        stampNbr.setPos(0 + stampDesc.boundingRect().size().width() / 2 - stampNbr.boundingRect().size().width() / 2,
                        stampDesc.boundingRect().size().height() + 20 + stampBox.boundingRect().size().height())


        stampValue = QGraphicsTextItem(value)
        stampValue.setData(0, "stampValue")
        stampValue.setFlags(QGraphicsTextItem.GraphicsItemFlag.ItemIsMovable | QGraphicsTextItem.GraphicsItemFlag.ItemIsSelectable)

        stampValue.setPos(0 + stampDesc.boundingRect().size().width() / 2 - stampValue.boundingRect().size().width() / 2,
                          stampDesc.boundingRect().size().height() + 20 + stampBox.boundingRect().size().height() +
                          stampNbr.boundingRect().size().height() + 0)

        group = QGraphicsItemGroup()
        group.addToGroup(stampBox)
        group.addToGroup(stampDesc)
        group.addToGroup(stampNbr)
        group.addToGroup(stampValue)
        group.addToGroup(pixmapitem)
        group.setFlags(QGraphicsItemGroup.GraphicsItemFlag.ItemIsMovable |
                       QGraphicsItemGroup.GraphicsItemFlag.ItemIsSelectable)
        group.setData(0, "stampGroup")
        group.setPos(x, y)
        scene.addItem(group)

    def readStamp(self, stampItem):
        """
                Extract property text, box dimensions, and pixmap data from a stamp group.

                Args:
                    stampItem: Active QGraphicsItemGroup instance.

                Returns:
                    dict: Dictionary mapping stamp child keys to their corresponding values.
        """
        stampObj = {}
        childrenItems = stampItem.childItems()
        for childItem in childrenItems:
            print(childItem.type().real)
            print(childItem.data(0))
            # 8 is a text item
            # 7 is a pixmap item
            # 3 is a box
            if childItem.type().real == 8:
                print(childItem.toPlainText())
                stampObj[childItem.data(0) + '_text'] = childItem.toPlainText()
            elif childItem.type().real == 7:
                stampObj[childItem.data(0) + '_image'] = childItem.pixmap()
                stampObj[childItem.data(0) + '_width'] = childItem.boundingRect().width()
                stampObj[childItem.data(0) + '_height'] = childItem.boundingRect().height()

            elif childItem.type().real == 3:
                stampObj[childItem.data(0) + '_width'] = childItem.boundingRect().width()
                stampObj[childItem.data(0) + '_height'] = childItem.boundingRect().height()
                stampObj[childItem.data(0) + '_boxWidth'] = int(childItem.data(1))
                stampObj[childItem.data(0) + '_boxHeight'] = int(childItem.data(2))

        print(stampObj)
        return stampObj

    def updateStamp(self, stampItem, stampObj, scene):
        # Retrieve actual top-left scene corner coordinates before deletion
        top_left = stampItem.sceneBoundingRect().topLeft()

        boxWidth = stampObj['stampBox_boxWidth']
        boxHeight = stampObj['stampBox_boxHeight']
        nbr = stampObj['stampNbr_text']
        value = stampObj['stampValue_text']
        desc = stampObj['stampDesc_text']
        pixmap = stampObj['pixmapItem_image']

        undo_stack = getattr(scene, 'undoStack', None)
        if undo_stack is not None:
            # Delete + re-create grouped inside a single macro:
            # pressing Ctrl+Z restores the previous stamp instead of deleting it permanently
            from UndoCommands import DeleteItemsCommand
            undo_stack.beginMacro(_("Edit Stamp"))
            undo_stack.push(DeleteItemsCommand(scene, [stampItem]))
            self.createStampPix(scene, nbr, value, desc, boxWidth, boxHeight, top_left.x(), top_left.y(), pixmap)
            undo_stack.endMacro()
        else:
            scene.removeItem(stampItem)
            self.createStampPix(scene, nbr, value, desc, boxWidth, boxHeight, top_left.x(), top_left.y(), pixmap)

class RichTextStamp(Stamp):
    """
    Dedicated graphics item group representing an autonomous rich-text stamp.
    Stores and restores full HTML formatting for description, number, and value.
    """

    def __init__(self):
        super().__init__()

    def createRichStampPix(self, scene, nbr_html: str, value_html: str, desc_html: str,
                           boxWidth: float, boxHeight: float, x: float, y: float,
                           pixmap: QPixmap):
        """
        Create and insert a rich text stamp group to the active scene.
        """
        # 1. Description item (Top HTML text)
        stampDesc = QGraphicsTextItem()
        stampDesc.setHtml(desc_html)
        stampDesc.setTextWidth(max(20.0, stampDesc.boundingRect().width()))
        stampDesc.setData(0, "stampDesc")
        stampDesc.setPos(0, 0)
        stampDesc.setFlags(
            QGraphicsTextItem.GraphicsItemFlag.ItemIsMovable |
            QGraphicsTextItem.GraphicsItemFlag.ItemIsSelectable
        )

        # 2. Rect mount box item (conversion mm -> px à 96 DPI)
        px_width = boxWidth / (25.4 / 96.0)
        px_height = boxHeight / (25.4 / 96.0)
        stampBox = QGraphicsRectItem(0, 0, px_width, px_height)

        boxPen = QPen()
        boxPen.setWidth(1)
        stampBox.setPen(boxPen)
        stampBox.setFlags(
            QGraphicsRectItem.GraphicsItemFlag.ItemIsMovable |
            QGraphicsRectItem.GraphicsItemFlag.ItemIsSelectable
        )

        # Center the mount box below the description text
        box_x = (stampDesc.boundingRect().width() / 2.0) - (px_width / 2.0)
        box_y = stampDesc.boundingRect().height() + 20.0
        stampBox.setPos(box_x, box_y)
        stampBox.setData(0, "stampBox")
        stampBox.setData(1, boxWidth)
        stampBox.setData(2, boxHeight)

        # 3. Image pixmap
        pixmapitem = QGraphicsPixmapItem(pixmap)
        if pixmapitem.boundingRect().width() > 0 and pixmapitem.boundingRect().height() > 0:
            scale1 = (stampBox.boundingRect().width() - 4.0) / pixmapitem.boundingRect().width()
            scale2 = (stampBox.boundingRect().height() - 4.0) / pixmapitem.boundingRect().height()
            image_scale = min(scale1, scale2)
        else:
            image_scale = 1.0

        pixmapitem.setScale(image_scale)
        pix_x = stampBox.x() + (stampBox.boundingRect().width() / 2.0) - ((image_scale * pixmapitem.boundingRect().width()) / 2.0)
        pix_y = stampBox.y() + (stampBox.boundingRect().height() / 2.0) - ((image_scale * pixmapitem.boundingRect().height()) / 2.0)
        pixmapitem.setPos(pix_x, pix_y)
        pixmapitem.setData(0, "pixmapItem")

        # 4. Stamp number item (Bottom text 1)
        stampNbr = QGraphicsTextItem()
        stampNbr.setHtml(nbr_html)
        stampNbr.setTextWidth(max(20.0, stampNbr.boundingRect().width()))
        stampNbr.setData(0, "stampNbr")
        stampNbr.setFlags(
            QGraphicsTextItem.GraphicsItemFlag.ItemIsMovable |
            QGraphicsTextItem.GraphicsItemFlag.ItemIsSelectable
        )
        nbr_x = (stampDesc.boundingRect().width() / 2.0) - (stampNbr.boundingRect().width() / 2.0)
        nbr_y = box_y + stampBox.boundingRect().height()
        stampNbr.setPos(nbr_x, nbr_y)

        # 5. Nominal value item (Bottom text 2)
        stampValue = QGraphicsTextItem()
        stampValue.setHtml(value_html)
        stampValue.setTextWidth(max(20.0, stampValue.boundingRect().width()))
        stampValue.setData(0, "stampValue")
        stampValue.setFlags(
            QGraphicsTextItem.GraphicsItemFlag.ItemIsMovable |
            QGraphicsTextItem.GraphicsItemFlag.ItemIsSelectable
        )
        val_x = (stampDesc.boundingRect().width() / 2.0) - (stampValue.boundingRect().width() / 2.0)
        val_y = nbr_y + stampNbr.boundingRect().height()
        stampValue.setPos(val_x, val_y)

        # 6. Group all items together under dedicated type
        group = QGraphicsItemGroup()
        group.addToGroup(stampBox)
        group.addToGroup(stampDesc)
        group.addToGroup(stampNbr)
        group.addToGroup(stampValue)
        group.addToGroup(pixmapitem)

        group.setFlags(
            QGraphicsItemGroup.GraphicsItemFlag.ItemIsMovable |
            QGraphicsItemGroup.GraphicsItemFlag.ItemIsSelectable
        )
        # Distinct identifier from 'stampGroup'
        group.setData(0, "richTextStampGroup")

        # 7. Normalize coordinates
        children_rect = group.childrenBoundingRect()
        for child in group.childItems():
            child.moveBy(-children_rect.x(), -children_rect.y())

        group.setPos(x, y)

        if hasattr(scene, 'addItemWithUndo'):
            scene.addItemWithUndo(group, _("Add Rich Text Stamp"))
        else:
            scene.addItem(group)

        return group

    def readRichStamp(self, stampItem):
        """
        Extract HTML text elements, dimensions, and pixmap data from a richTextStampGroup.
        """
        obj = {
            'stampDesc_html': '',
            'stampNbr_html': '',
            'stampValue_html': '',
            'stampBox_boxWidth': 25.0,
            'stampBox_boxHeight': 30.0,
            'pixmapItem_image': QPixmap()
        }

        for child in stampItem.childItems():
            key = str(child.data(0))
            if key == "stampDesc":
                obj['stampDesc_html'] = child.toHtml()
            elif key == "stampNbr":
                obj['stampNbr_html'] = child.toHtml()
            elif key == "stampValue":
                obj['stampValue_html'] = child.toHtml()
            elif key == "stampBox":
                obj['stampBox_boxWidth'] = float(child.data(1))
                obj['stampBox_boxHeight'] = float(child.data(2))
            elif key == "pixmapItem":
                obj['pixmapItem_image'] = child.pixmap()

        return obj

    def updateRichStamp(self, stampItem, scene, nbr_html: str, value_html: str,
                        desc_html: str, boxWidth: float, boxHeight: float, pixmap: QPixmap):
        """
        Replace an existing rich text stamp with updated parameters under Undo history.
        """
        top_left = stampItem.sceneBoundingRect().topLeft()
        undo_stack = getattr(scene, 'undoStack', None)

        if undo_stack is not None:
            from UndoCommands import DeleteItemsCommand
            undo_stack.beginMacro(_("Edit Rich Text Stamp"))
            undo_stack.push(DeleteItemsCommand(scene, [stampItem]))
            self.createRichStampPix(
                scene, nbr_html, value_html, desc_html,
                boxWidth, boxHeight, top_left.x(), top_left.y(), pixmap
            )
            undo_stack.endMacro()
        else:
            scene.removeItem(stampItem)
            self.createRichStampPix(
                scene, nbr_html, value_html, desc_html,
                boxWidth, boxHeight, top_left.x(), top_left.y(), pixmap
            )


