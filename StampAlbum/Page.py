"""
Page Module
-----------
Manages the graphics scene for custom stamp album pages including items,
decorations, borders, rich text items, undo stack history, and print preview.

Author: Boris du Reau
"""
import functools
import gettext
from AppLanguage import get_language
from SAAppPaths import get_config_value
from ResizablePixmapItem import ResizablePixmapItem
from PyQt6.QtCore import Qt, QRectF, QMarginsF
from PyQt6 import QtCore, QtGui
from PyQt6.QtWidgets import (
    QGraphicsScene, QGraphicsTextItem, QGraphicsItemGroup
)
from PyQt6.QtGui import QBrush, QPainter, QPixmap, QFont, QTextCursor, QTextBlockFormat, \
    QPageLayout, QPageSize
from PyQt6.QtPrintSupport import QPrintPreviewDialog, QPrinter
from StampDlg import StampDlg
from TextDlg import TextDlg
from Stamp import Stamp
from EditStampDlg import EditStampDlg
from PageBorder import PageBorder
from PyQt6.QtGui import QUndoStack
from UndoCommands import AddItemCommand, DeleteItemsCommand, MoveCommand

gettext.find("PageDlg")
translate = gettext.translation('PageDlg', localedir='locale', languages=[get_language()], fallback=True)
translate.install()
_ = translate.gettext


def undoable_move(text):
    """
        Decorator for alignment / distribution / centering functions:
        records item positions prior to operation and pushes a single MoveCommand
        onto the history stack for items that actually moved.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            items = [it for it in self.selectedItems() if it.parentItem() is None]
            before = {it: it.pos() for it in items}
            result = func(self, *args, **kwargs)
            moved = [it for it in items if it.pos() != before[it]]
            if moved:
                self.undoStack.push(MoveCommand(moved, [before[it] for it in moved], text))
            return result
        return wrapper
    return decorator


class Page(QGraphicsScene):
    """Custom QGraphicsScene representing a single stamp album page."""

    def __init__(self, pageType="portrait", border=None, paper_format=None,
                 border_style=None, margin_size_mm=None, margin_position=None, parent=None):
        super(Page, self).__init__(parent)
        self.pageType = pageType

        # Set page background color to plain white
        self.setBackgroundBrush(QBrush(Qt.GlobalColor.white))

        # Undo/Redo history stack for the current page scene
        self.undoStack = QUndoStack(self)
        self.mouse_press_positions = {}

        if not paper_format:
            paper_format = self.get_configured_paper_format()

        self.paper_format = paper_format

        # Load margin settings from parameters or configuration
        if margin_size_mm is None:
            try:
                margin_size_mm = float(get_config_value('margin size', "19"))
            except ValueError:
                margin_size_mm = 19.0
        self.margin_size_mm = margin_size_mm

        if margin_position is None:
            margin_position = get_config_value('margin position', "left").lower()
        self.margin_position = margin_position

        if self.paper_format == "Letter":
            self.page_width_mm = 215.9
            self.page_height_mm = 279.4
        else:
            self.page_width_mm = 210.0
            self.page_height_mm = 297.0

        # Convert mm to pixels (dpi = 96)
        px_w = self.page_width_mm / (25.4 / 96.0)
        px_h = self.page_height_mm / (25.4 / 96.0)

        style = border_style if border_style else self.get_configured_border_style()

        if self.pageType == "portrait":
            self.setSceneRect(0, 0, px_w, px_h)
            if border:
                border_w = (self.page_width_mm - 33.0) / (25.4 / 96.0)
                border_h = (self.page_height_mm - 25.0) / (25.4 / 96.0)
                margin_px = self.margin_size_mm / (25.4 / 96.0)
                if self.margin_position == "right":
                    margin_l = px_w - border_w - margin_px
                else:
                    margin_l = margin_px
                self.addBorder(border_w, border_h, margin_l, 0, 0, 0, style)
        else:
            self.setSceneRect(0, 0, px_h, px_w)
            if border:
                border_w = (self.page_height_mm - 25.0) / (25.4 / 96.0)
                border_h = (self.page_width_mm - 33.0) / (25.4 / 96.0)
                margin_px = self.margin_size_mm / (25.4 / 96.0)
                margin_l = ((px_h - border_w) / 2.0)
                self.addBorder(border_w, border_h, margin_l, 0, margin_px, 0, style)

        self.gridOn = False
        self.album_language = "fr"

    def addImageAt(self, fileName, x, y):
        """Create and place an image at exact scene coordinates with Undo support."""
        if fileName:
            pixmap = QPixmap(fileName)
            if not pixmap.isNull():
                pixmapitem = ResizablePixmapItem(pixmap)
                pixmapitem.setPos(x, y)
                self.addItemWithUndo(pixmapitem, _("Add Image"))

    def changePageSetup(self, page_type: str, paper_format: str, border_style: str,
                        margin_size_mm: float = None, margin_position: str = None):
        """Update page dimensions, orientation, margins, and recreate the border frame."""
        self.pageType = page_type
        self.paper_format = paper_format

        if margin_size_mm is not None:
            self.margin_size_mm = margin_size_mm
        if margin_position is not None:
            self.margin_position = margin_position

        if self.paper_format == "Letter":
            self.page_width_mm = 215.9
            self.page_height_mm = 279.4
        else:
            self.page_width_mm = 210.0
            self.page_height_mm = 297.0

        px_w = self.page_width_mm / (25.4 / 96.0)
        px_h = self.page_height_mm / (25.4 / 96.0)

        if self.pageType == "portrait":
            self.setSceneRect(0, 0, px_w, px_h)
        else:
            self.setSceneRect(0, 0, px_h, px_w)

        old_border = next((it for it in self.items() if it.data(0) == "borderGroup"), None)
        if old_border:
            self.removeItem(old_border)

        w_mm, h_mm = self.page_width_mm, self.page_height_mm
        margin_px = self.margin_size_mm / (25.4 / 96.0)

        if self.pageType == "portrait":
            border_w = (w_mm - 33.0) / (25.4 / 96.0)
            border_h = (h_mm - 25.0) / (25.4 / 96.0)
            if self.margin_position == "right":
                margin_l = px_w - border_w - margin_px
            else:
                margin_l = margin_px
            self.addBorder(border_w, border_h, margin_l, 0, 0, 0, border_style)
        else:
            border_w = (h_mm - 25.0) / (25.4 / 96.0)
            border_h = (w_mm - 33.0) / (25.4 / 96.0)
            margin_l = ((px_h - border_w) / 2.0)
            self.addBorder(border_w, border_h, margin_l, 0, margin_px, 0, border_style)

        self.update()

    def get_configured_paper_format(self) -> str:
        """Read default paper format from configuration file."""
        return get_config_value('paper format', "A4")

    def apply_page_layout(self, printer):
        """
        Apply paper format, orientation, and zero margins matching this page
        to the QPrinter (A4 or Letter, portrait or landscape).
        """
        size_id = QPageSize.PageSizeId.Letter if self.paper_format == "Letter" else QPageSize.PageSizeId.A4
        orientation = (QPageLayout.Orientation.Portrait if self.pageType == "portrait"
                       else QPageLayout.Orientation.Landscape)
        layout = QPageLayout(QPageSize(size_id), orientation, QMarginsF(0, 0, 0, 0),
                             QPageLayout.Unit.Millimeter)
        printer.setPageLayout(layout)

    def hiddenGuides(self):
        """Deselect all items and hide guidelines; return the list to restore."""
        for item in self.selectedItems():
            item.setSelected(False)
        guides = [it for it in self.items() if it.data(0) == "guideLine"]
        for g in guides:
            g.hide()
        return guides

    def renderToPrinter(self, painter, printer):
        """Render the entire page onto the painter at printer resolution."""
        scale = printer.resolution() / 96.0
        source = QtCore.QRectF(0, 0, self.width(), self.height())
        target = QRectF(0, 0, source.width() * scale, source.height() * scale)

        # Save current background brush
        saved_brush = self.backgroundBrush()

        guides = self.hiddenGuides()
        try:
            # Force pure white background for printing
            self.setBackgroundBrush(QBrush(Qt.GlobalColor.white))
            self.render(painter, target, source)
        finally:
            # Restore background (with grid if active) and show guidelines again
            self.setBackgroundBrush(saved_brush)
            for g in guides:
                g.show()

    def addItemNative(self, item):
        """Add item directly to scene without pushing an Undo command."""
        if item.scene() != self:
            super().addItem(item)

    def removeItemNative(self, item):
        """Remove item directly from scene without pushing an Undo command."""
        if item.scene() == self:
            super().removeItem(item)

    def addItemWithUndo(self, item, text="Add Item"):
        """Add item to scene and record in Undo stack."""
        if item.parentItem() is None:
            if item.scene() != self:
                super().addItem(item)
            cmd = AddItemCommand(self, item, text)
            self.undoStack.push(cmd)
        else:
            self.addItemNative(item)

    def addItem(self, item):
        """Override addItem to add item natively without triggering infinite recursion during setup."""
        if item.scene() != self:
            super().addItem(item)

    def removeItems(self):
        """Remove selected top-level items and record operation in Undo stack."""
        items = [it for it in self.selectedItems() if it.parentItem() is None]
        if items:
            cmd = DeleteItemsCommand(self, items)
            self.undoStack.push(cmd)

    def getPageName(self):
        return ""

    def get_configured_border_style(self) -> str:
        """Read default border style from configuration file."""
        return get_config_value('type encadrement', PageBorder.STYLE_TRIPLE)

    def addBorder(self, boxWidth, boxHeight, margin_left, margin_right, margin_top, margin_bottom, style=None):
        """Add a decorative border to the page using PageBorder class."""
        if not style:
            style = PageBorder.STYLE_TRIPLE

        border = PageBorder(boxWidth, boxHeight, style=style)

        if margin_top != 0:
            final_y = margin_top
        else:
            scene_h = self.sceneRect().height() if self.sceneRect().isValid() else self.height()
            final_y = (scene_h - border.boundingRect().height()) / 2.0

        border.setPos(float(margin_left), float(final_y))
        self.addItem(border)

    def addTextLabel(self, text, x=20, y=20, font=None, align=Qt.AlignmentFlag.AlignCenter, labelType="textLabel"):
        """Add a text label to the page with alignment and font attributes."""
        textLabel = QGraphicsTextItem(text)
        textLabel.setData(0, labelType)

        # If no font is specified, load default font from configuration
        if font is None:
            default_font_family = get_config_value('default font', 'Arial')
            font = QFont(default_font_family, 10)  # Apply configured font family

        textLabel.setFont(font)
        textLabel.setTextWidth(textLabel.boundingRect().size().width())

        cursor = textLabel.textCursor()
        cursor.select(QTextCursor.SelectionType.Document)
        format = QTextBlockFormat()
        format.setAlignment(align)
        cursor.mergeBlockFormat(format)
        cursor.clearSelection()
        textLabel.setTextCursor(cursor)

        textLabel.setPos(x, y)

        textLabel.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        textLabel.setFlags(
            QGraphicsTextItem.GraphicsItemFlag.ItemIsMovable |
            QGraphicsTextItem.GraphicsItemFlag.ItemIsSelectable
        )

        self.addItemWithUndo(textLabel, _("Add Text"))

    def addRichText(self, html_content="", x=50, y=50, label_type="richTextLabel"):
        """Add a rich-text block supporting HTML content."""
        text_item = QGraphicsTextItem()
        text_item.setData(0, label_type)

        if html_content:
            text_item.setHtml(html_content)
        else:
            default_font_family = get_config_value('default font', 'Sans-Serif')
            text_item.setHtml(
                f"<p style='font-family:{default_font_family}; font-size:12pt;'>Double-click to edit rich text...</p>"
            )

        # -1 disables fixed line-wrapping width, letting the text expand horizontally
        text_item.setTextWidth(-1)
        text_item.setPos(x, y)

        text_item.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        text_item.setFlags(
            QGraphicsTextItem.GraphicsItemFlag.ItemIsMovable |
            QGraphicsTextItem.GraphicsItemFlag.ItemIsSelectable
        )

        if hasattr(self, 'addItemWithUndo'):
            self.addItemWithUndo(text_item, _("Add Rich Text"))
        else:
            self.addItem(text_item)

        return text_item


    def editRichText(self, item):
        """Open the rich text dialog editor for an existing text block."""
        try:
            from RichTextDlg import RichTextDlg
            # Retrieve language stored on the page, with safe fallback to 'fr'
            lang = getattr(self, "album_language", "fr")
            dlg = RichTextDlg(item, album_language=lang)
            if dlg.exec() == 1:
                item.setHtml(dlg.get_html())
        except Exception as e:
            print(f"Error editing rich text: {e}")

    def clearPage(self):
        """Remove all items from the current page (annulable avec Ctrl+Z)."""
        items = [it for it in self.items() if it.parentItem() is None]
        if items:
            self.undoStack.push(DeleteItemsCommand(self, items, _("Clear page")))


    def editObject(self, item=None):
        """Edit currently selected scene item or the item passed directly."""
        top_item = item

        if top_item is None:
            items = self.selectedItems()
            if len(items) != 1:
                return
            top_item = items[0]
            while top_item.parentItem() is not None:
                top_item = top_item.parentItem()

        if top_item is None:
            return

        try:
            raw_data = top_item.data(0)
            data_type = str(raw_data) if raw_data is not None else ""

            # 1. Ignore page borders
            if data_type == "borderGroup":
                return

            # 2. Case of Rich Text Stamp (RichTextStamp)
            if data_type == "richTextStampGroup":
                from RichTextStampDlg import RichTextStampDlg
                dlg = RichTextStampDlg(scene=self, stampItem=top_item)
                dlg.exec()
                return

            # 3. Case of standalone rich text block (MUST BE EVALUATED BEFORE SIMPLE TEXTS)
            if data_type == "richTextLabel":
                self.editRichText(top_item)
                return

            # 4. Case of traditional stamp
            elif data_type == "stampGroup" or top_item.type() == 10:
                self.editStamp(top_item)
                return

            # 5. Simple text labels
            elif (
                    data_type in ["textLabel", "labelPageNbr", "labelCopyRight", "labelYear"]
                    or isinstance(top_item, QGraphicsTextItem)
                    or top_item.type() == 8
            ):
                self.editLabel(top_item)
                return

        except Exception as e:
            print(f"Error during item editing: {e}")

    def printObjectDebugInfo(self):
        """Print debug information for selected scene items."""
        items = self.selectedItems()
        nbrOfItems = len(items)

        if nbrOfItems > 1:
            print("more than one item selected")
            return

        if nbrOfItems == 0:
            print("no items selected")
            return

        for item in items:
            itemType = item.type().real
            if itemType == 10:
                print(item.data(0))
                print("stamp")
                print(item.pos().x())
                print(item.pos().y())
            elif itemType == 8:
                print("text label")

    def editLabel(self, item):
        """Edit a standard text item using TextDlg."""
        dlg = TextDlg(item)
        res = dlg.exec()
        if res == 1:
            text = dlg.eTXT.toPlainText()
            font = dlg.eTXT.font()
            item.setPlainText(text)
            item.setFont(font)
            textLabel = QGraphicsTextItem(text)
            textLabel.setFont(font)

            item.setTextWidth(textLabel.boundingRect().size().width())

            cursor = item.textCursor()
            cursor.select(QTextCursor.SelectionType.Document)
            format = QTextBlockFormat()

            align = dlg.eTXT.alignment()
            format.setAlignment(align)
            cursor.mergeBlockFormat(format)
            cursor.clearSelection()
            item.setTextCursor(cursor)

            item.setFlags(QGraphicsTextItem.GraphicsItemFlag.ItemIsMovable |
                          QGraphicsTextItem.GraphicsItemFlag.ItemIsSelectable)

    def editStamp(self, stampItem):
        """Edit stamp group attributes using EditStampDlg."""
        stamp = Stamp()
        stampObj = stamp.readStamp(stampItem)
        dlg = EditStampDlg(stampObj)
        res = dlg.exec()
        if res == 1:
            stampObj['stampDesc_text'] = dlg.eTitle.toPlainText()
            stampObj['stampNbr_text'] = dlg.eNbr.text()
            stampObj['stampValue_text'] = dlg.eValue.toPlainText()

            if dlg.pochetteList.currentItem() is None:
                return
            ret = dlg.getBoxInfo(dlg.pochetteList.currentItem().text())
            if len(ret) < 2:
                return
            width = ret[0]
            stampObj['stampBox_boxWidth'] = width
            height = ret[1]
            stampObj['stampBox_boxHeight'] = height
            # Full-resolution pixmap (not the 200px thumbnail displayed in dialog)
            stampObj['pixmapItem_image'] = dlg.getPixmap()

            stamp.updateStamp(stampItem, stampObj, self)

    def printPagePDF(self, fileName2):
        """Export current page as a PDF file."""
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
        printer.setOutputFileName(fileName2)
        # Apply layout format (A4/Letter), orientation, and margins BEFORE creating QPainter
        self.apply_page_layout(printer)

        p = QPainter(printer)
        self.renderToPrinter(p, printer)
        p.end()

    def printPreview(self):
        """Display print preview for the current page."""
        previewDialog = QPrintPreviewDialog()
        previewDialog.printer().setResolution(QPrinter.PrinterMode.HighResolution.value)
        previewDialog.printer().setOutputFormat(QPrinter.OutputFormat.PdfFormat)
        self.apply_page_layout(previewDialog.printer())

        previewDialog.paintRequested.connect(self.createPreview)
        previewDialog.exec()

    def createPreview(self, printer):
        """Render scene page preview for QPrintPreviewDialog."""
        p = QPainter(printer)
        self.renderToPrinter(p, printer)
        p.end()

    def printPage(self):
        print("Print page")

    def drawGid(self):
        pixmap = QPixmap(10, 10)
        painter = QPainter()
        pixmap.fill(Qt.GlobalColor.transparent)
        painter.begin(pixmap)
        painter.setPen(Qt.GlobalColor.gray)
        painter.drawLine(0, 0, 10, 0)
        painter.drawLine(0, 0, 0, 10)
        return pixmap

    def groupItem(self):
        sceneItems = self.items()
        for items in sceneItems:
            items.setSelected(True)

        group = self.createItemGroup(sceneItems)
        group.setFlags(
            QGraphicsItemGroup.GraphicsItemFlag.ItemIsMovable | QGraphicsItemGroup.GraphicsItemFlag.ItemIsSelectable)

    def newStamp(self, lastStampObj):
        """Create and place a new stamp item from StampDlg."""
        dlg = StampDlg(lastStampObj, self)
        res = dlg.exec()

        if res == 1:
            stampNbr = dlg.currentStampNbr
            lastStampObj['year'] = dlg.eYear.text()
            lastStampObj['type'] = dlg.stampTypeCombo.currentText()
            lastStampObj['country'] = dlg.currentCountry
            lastStampObj['nbr'] = stampNbr
            return lastStampObj

    def newLabel(self):
        """Prompt user for text and place a standard label."""
        textLabel = QGraphicsTextItem("")
        textLabelFont = textLabel.font()
        textLabelFont.setPointSize(10)
        textLabel.setFont(textLabelFont)

        dlg = TextDlg(textLabel)
        res = dlg.exec()

        if res == 1:
            text = dlg.eTXT.toPlainText()
            font = dlg.eTXT.font()
            align = dlg.eTXT.alignment()
            self.addTextLabel(text, 50, 50, font, align)

    def _get_bottom_footer_y(self, offset_above_border=18.0) -> float:
        """
            Compute optimal Y position for footer (copyright, page number)
            so that it sits slightly above the lower edge of the border frame.
        """
        border_item = next((it for it in self.items() if it.data(0) == "borderGroup"), None)
        if border_item:
            # Retrieve exact bottom edge of border/frame
            border_bottom = border_item.sceneBoundingRect().bottom()
            return border_bottom - offset_above_border
        else:
            # Fall back to scene height if border is not present
            px_h = self.sceneRect().height()
            return px_h - 50.0

    def newCopyRight(self):
        """Add a copyright footer to the page."""
        text = get_config_value('copyright', "CopyRight © Boris du Reau 2003-2026")

        font = QFont()
        font.setPointSize(6)

        # Dynamic calculation of Y and X positions relative to the border
        y_pos = self._get_bottom_footer_y(offset_above_border=28.0)

        border_item = next((it for it in self.items() if it.data(0) == "borderGroup"), None)
        if border_item:
            x_pos = border_item.sceneBoundingRect().left() + 10.0
        else:
            x_pos = 80.0 if self.pageType == "portrait" else 60.0

        self.addTextLabel(text, x_pos, y_pos, font, Qt.AlignmentFlag.AlignLeft, "labelCopyRight")

    def newPageNbr(self):
        """Prompt user and create a page number label."""
        textLabel = QGraphicsTextItem("")
        textLabelFont = textLabel.font()
        textLabelFont.setPointSize(8)
        textLabel.setFont(textLabelFont)

        dlg = TextDlg(textLabel)
        res = dlg.exec()

        if res == 1:
            text = dlg.eTXT.toPlainText()
            font = dlg.eTXT.font()
            align = dlg.eTXT.alignment()
            self.addPageNbr(text, font, align)

    def addPageNbr(self, pageName, font, align=Qt.AlignmentFlag.AlignLeft):
        """Position page number label at the bottom right inside the border frame."""
        textLabel = QGraphicsTextItem(pageName)
        textLabel.setFont(font)
        textWidth = textLabel.boundingRect().size().width()

        y_pos = self._get_bottom_footer_y(offset_above_border=28.0)

        border_item = next((it for it in self.items() if it.data(0) == "borderGroup"), None)
        if border_item:
            # Calculate X position relative to right edge of border
            border_right = border_item.sceneBoundingRect().right()
            x_pos = border_right - textWidth - 10.0
        else:
            px_w = self.sceneRect().width()
            x_pos = px_w - 60.0 - textWidth

        self.addTextLabel(pageName, x_pos, y_pos, font, align, "labelPageNbr")

    def addPageYear(self):
        """Prompt user for year and place a header year label."""
        textLabel = QGraphicsTextItem("")
        textLabelFont = textLabel.font()
        textLabelFont.setPointSize(10)
        textLabelFont.setBold(True)
        textLabel.setFont(textLabelFont)

        dlg = TextDlg(textLabel)
        res = dlg.exec()

        if res == 1:
            text = dlg.eTXT.toPlainText()
            font = dlg.eTXT.font()
            align = dlg.eTXT.alignment()
            self.addYear(text, font, align)

    def addYear(self, year, font, align):
        """Position year header label at top center inside/above the border frame."""
        textLabel = QGraphicsTextItem(year)
        textLabel.setFont(font)
        textWidth = textLabel.boundingRect().size().width()

        border_item = next((it for it in self.items() if it.data(0) == "borderGroup"), None)
        if border_item:
            border_rect = border_item.sceneBoundingRect()
            x_pos = border_rect.left() + (border_rect.width() - textWidth) / 2.0
            y_pos = border_rect.top() + 10.0
        else:
            px_w = self.sceneRect().width()
            x_pos = (px_w - textWidth) / 2.0
            y_pos = 80.0

        self.addTextLabel(year, x_pos, y_pos, font, align, "labelYear")
    @undoable_move("Align Top")
    def alignTop(self):
        topY = 0.0
        if self.countSelectedItems() > 1:
            for it in self.items():
                if topY == 0.0 and it.isSelected() and it.parentItem() is None:
                    topY = it.y()
                if it.y() < topY and it.isSelected() and it.parentItem() is None:
                    topY = it.y()

            for it2 in self.items():
                if it2.isSelected() and it2.parentItem() is None:
                    it2.setPos(it2.x(), topY)

    @undoable_move("Align Bottom")
    def alignBottom(self):
        topY = 0.0
        if self.countSelectedItems() > 1:
            for it in self.items():
                if (it.y() + it.boundingRect().size().height()) > topY and it.isSelected() and it.parentItem() is None:
                    topY = it.y() + it.boundingRect().size().height()

            for it2 in self.items():
                if it2.isSelected() and it2.parentItem() is None:
                    it2.setPos(it2.x(), topY - it2.boundingRect().height())

    @undoable_move("Align Left")
    def alignLeft(self):
        topX = self.sceneRect().width()
        if self.countSelectedItems() > 1:
            for it in self.items():
                if topX == 0:
                    topX = it.x()
                if it.x() < topX and it.isSelected() and it.parentItem() is None:
                    topX = it.x()
            for it2 in self.items():
                if it2.isSelected() and it2.parentItem() is None:
                    it2.setPos(topX, it2.y())

    @undoable_move("Align Right")
    def alignRight(self):
        topX = 0.0
        if self.countSelectedItems() > 1:
            for it in self.items():
                if (it.x() + it.boundingRect().size().width()) > topX and it.isSelected() and it.parentItem() is None:
                    topX = (it.x() + it.boundingRect().size().width())
            for it2 in self.items():
                if it2.isSelected() and it2.parentItem() is None:
                    it2.setPos(topX - it2.boundingRect().size().width(), it2.y())


    @undoable_move("Distribute Horizontally")
    def distributeHorizontally(self):
        """Evenly distribute horizontal space between selected items."""
        items = [it for it in self.selectedItems() if it.parentItem() is None]
        if len(items) < 3:
            return

        # Sort items left-to-right by their left bounding edge
        items.sort(key=lambda it: it.sceneBoundingRect().left())

        min_x = items[0].sceneBoundingRect().left()
        max_x = items[-1].sceneBoundingRect().right()

        total_items_width = sum(it.sceneBoundingRect().width() for it in items)
        available_space = max_x - min_x - total_items_width

        # Distance spacing between each item
        space = available_space / (len(items) - 1)

        current_left = min_x
        for it in items:
            rect = it.sceneBoundingRect()
            dx = current_left - rect.left()
            it.setPos(it.x() + dx, it.y())
            current_left += rect.width() + space

    @undoable_move("Distribute Vertically")
    def distributeVertically(self):
        # Safety check: requires at least 3 items to distribute vertically
        if self.countSelectedItems() < 3:
            return

        itemLength = 0
        minY = 0
        maxY = 0
        nbrItems = 0
        posY = []

        for it in self.items():
            if it.isSelected() and it.parentItem() is None:
                nbrItems += 1
                if minY == 0:
                    minY = it.y()
                if it.y() < minY:
                    minY = it.y()
                if (it.y() + it.boundingRect().size().height()) > maxY:
                    maxY = it.y() + it.boundingRect().size().height()

                posY.append(it.y())
                itemLength += it.boundingRect().size().height()

        if nbrItems > 2 and (nbrItems - 1) > 0:
            space = (maxY - minY - itemLength) / (nbrItems - 1)
            posY.sort()
            nextY = minY
            for py in posY:
                for i in self.items():
                    if i.isSelected() and i.parentItem() is None and py == i.y():
                        i.setPos(i.x(), nextY)
                        nextY += i.boundingRect().size().height() + space

    @undoable_move("Center Horizontally")
    def centerHorizontally(self):
        """Center each selected item horizontally relative to page or border frame."""
        selected_items = [it for it in self.selectedItems() if it.parentItem() is None]
        if not selected_items:
            return

        border_item = next((it for it in self.items() if str(it.data(0)) == "borderGroup"), None)
        if border_item:
            b_rect = border_item.sceneBoundingRect()
            center_x = b_rect.left() + b_rect.width() / 2.0
        else:
            center_x = self.sceneRect().width() / 2.0

        for it in selected_items:
            rect = it.sceneBoundingRect()
            # Offset needed to align the item center with the target horizontal center
            dx = center_x - (rect.left() + rect.width() / 2.0)
            it.setPos(it.x() + dx, it.y())
    @undoable_move("Center Horizontally")
    def centerHorizontally_old(self):
        if self.countSelectedItems() > 0:
            for it in self.items():
                if it.isSelected() and it.parentItem() is None:
                    centerPage = self.sceneRect().width() / 2
                    if it.type().real == 8:
                        centerItem = it.boundingRect().width() / 2
                        it.setPos((centerPage - centerItem), it.y())
                    elif it.type().real == 10 and it.data(0) == "stampGroup":
                        stampItems = it.childItems()
                        for stampItem in stampItems:
                            if stampItem.type().real == 3:
                                if stampItem.x() < 0:
                                    centerItem = (it.boundingRect().width() / 2) + stampItem.x()
                                    it.setPos((centerPage - centerItem), it.y())
                                else:
                                    centerItem = it.boundingRect().width() / 2
                                    it.setPos((centerPage - centerItem), it.y())

    @undoable_move("Center Vertically")
    def centerVertically(self):
        if self.countSelectedItems() > 0:
            for it in self.items():
                if it.isSelected() and it.parentItem() is None:
                    centerPage = self.sceneRect().height() / 2
                    centerItem = it.boundingRect().height() / 2
                    it.setPos(it.x(), centerPage - centerItem)

    def countSelectedItems(self):
        selected = 0
        for it in self.items():
            if it.isSelected():
                selected += 1
        return selected

    def addImage(self, fileName):
        if fileName:
            pixmap = QPixmap(fileName)
            if not pixmap.isNull():
                pixmapitem = ResizablePixmapItem(pixmap)
                pixmapitem.setPos(50, 50)
                self.addItemWithUndo(pixmapitem, _("Add Image"))

    def mouseDoubleClickEvent(self, event):
        """Fallback double-click handling if not caught by GraphicsView."""
        item = self.itemAt(event.scenePos(), QtGui.QTransform())
        if item:
            top_item = item
            while top_item.parentItem() is not None:
                top_item = top_item.parentItem()

            event.accept()
            self.editObject(top_item)
        else:
            super().mouseDoubleClickEvent(event)

    def mousePressEvent(self, event):
        """Handle single and multi-selection via Ctrl+Click and drag initialization."""
        scene_pos = event.scenePos()
        self._press_scene_pos = scene_pos
        items_under_cursor = self.items(scene_pos)

        # 1. Identify primary item under cursor (ignoring border frame)
        target_item = None
        for item in items_under_cursor:
            top_item = item
            while top_item.parentItem() is not None:
                top_item = top_item.parentItem()
            data_type = str(top_item.data(0)) if top_item.data(0) is not None else ""
            if data_type != "borderGroup":
                target_item = top_item
                break

        is_ctrl = bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)
        self._single_click_item = None

        if event.button() == Qt.MouseButton.LeftButton:
            if is_ctrl:
                # Ctrl held down: toggle selection status
                if target_item is not None:
                    target_item.setSelected(not target_item.isSelected())

                self.mouse_press_positions = {
                    it: it.pos() for it in self.selectedItems() if it.parentItem() is None
                }
                event.accept()
                return  # Prevent Qt from interfering with child items

            else:
                # Normal left click without Ctrl
                if target_item is not None:
                    if not target_item.isSelected():
                        # Si l'objet n'était pas sélectionné, il devient le seul sélectionné
                        self.clearSelection()
                        target_item.setSelected(True)
                    else:
                        # Already selected among others: retain selection for group dragging,
                        # but track item in case it's a stationary click
                        if len(self.selectedItems()) > 1:
                            self._single_click_item = target_item
                else:
                    # Click on empty background or border frame: clear selection
                    self.clearSelection()

        # Save initial positions for Undo command (MoveCommand)
        self.mouse_press_positions = {
            item: item.pos() for item in self.selectedItems() if item.parentItem() is None
        }
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)

        # If an item within a multi-selection was clicked without dragging,
        # narrow selection down to only that item
        if hasattr(self, '_single_click_item') and self._single_click_item is not None:
            if hasattr(self, '_press_scene_pos'):
                drag_distance = (event.scenePos() - self._press_scene_pos).manhattanLength()
                if drag_distance < 4:
                    self.clearSelection()
                    self._single_click_item.setSelected(True)
            self._single_click_item = None

        # Record moved items in the Undo stack
        moved_items = []
        old_positions = []

        for item, old_pos in self.mouse_press_positions.items():
            if hasattr(item, 'is_resizing') and item.is_resizing:
                continue

            if item.pos() != old_pos:
                moved_items.append(item)
                old_positions.append(old_pos)

        if moved_items:
            cmd = MoveCommand(moved_items, old_positions)
            self.undoStack.push(cmd)

        self.mouse_press_positions.clear()

    def autoArrangeStamps_old(self):
        """Organise les timbres par ordre de numéro sans chevauchement ni dépassement de bordure."""
        # 1. Sélectionner les timbres à organiser
        selected_stamps = [
            it for it in self.selectedItems()
            if it.parentItem() is None and it.data(0) == "stampGroup"
        ]
        stamps = selected_stamps if len(selected_stamps) > 1 else [
            it for it in self.items()
            if it.parentItem() is None and it.data(0) == "stampGroup"
        ]

        if not stamps:
            return

        # Sauvegarder les positions d'origine pour la fonction "Undo" (Ctrl+Z)
        old_positions = [it.pos() for it in stamps]

        # 2. Tri intelligent par numéro de timbre (se suivant)
        def get_stamp_number_key(stamp):
            """Extrait le texte du numéro de timbre pour un tri naturel (ex: 1, 2, 10 au lieu de 1, 10, 2)."""
            nbr_item = next((c for c in stamp.childItems() if c.data(0) == "stampNbr"), None)
            text = nbr_item.toPlainText().strip() if nbr_item else ""

            # Découpage du numéro pour trier correctement les chiffres et lettres (ex: "T01-12", "12a")
            import re
            parts = re.split(r'(\d+)', text)
            return [int(p) if p.isdigit() else p.lower() for p in parts if p]

        stamps.sort(key=get_stamp_number_key)

        # 3. Déterminer la zone limite (cadre interne) de la bordure
        border_item = next((it for it in self.items() if it.data(0) == "borderGroup"), None)
        if border_item:
            border_rect = border_item.sceneBoundingRect()
            padding = 10.0  # Marge de sécurité interne
            min_x_limit = border_rect.left() + padding
            max_x_limit = border_rect.right() - padding
            min_y_limit = border_rect.top() + padding
            max_y_limit = border_rect.bottom() - padding
        else:
            px_w = self.sceneRect().width()
            px_h = self.sceneRect().height()
            min_x_limit = 50.0
            max_x_limit = px_w - 50.0
            min_y_limit = 100.0
            max_y_limit = px_h - 100.0

        available_w = max(100.0, max_x_limit - min_x_limit)

        # 4. Paramètres d'espacement minimal
        h_spacing = 20.0  # Marge horizontale entre deux timbres
        v_spacing = 25.0  # Marge verticale entre deux rangées

        # 5. Découpage automatique des timbres en rangées sans chevauchement horizontal
        rows = []
        current_row = []
        current_row_w = 0.0

        for stamp in stamps:
            stamp_w = stamp.boundingRect().width()

            # Vérifier si l'ajout du timbre dépasse la largeur maximale disponible
            if current_row and (current_row_w + h_spacing + stamp_w > available_w):
                rows.append(current_row)
                current_row = [stamp]
                current_row_w = stamp_w
            else:
                if current_row:
                    current_row_w += h_spacing + stamp_w
                else:
                    current_row_w = stamp_w
                current_row.append(stamp)

        if current_row:
            rows.append(current_row)

        # 6. Placement et centrage des rangées dans la page
        row_heights = [max(s.boundingRect().height() for s in row) for row in rows]
        total_block_h = sum(row_heights) + (len(rows) - 1) * v_spacing

        # Centrer verticalement le groupe complet de rangées
        current_y = min_y_limit + max(0.0, (max_y_limit - min_y_limit - total_block_h) / 2.0)

        for i, row in enumerate(rows):
            total_stamps_w = sum(s.boundingRect().width() for s in row)
            actual_row_w = total_stamps_w + (len(row) - 1) * h_spacing

            # Centrer chaque rangée horizontalement à l'intérieur des bordures
            current_x = min_x_limit + max(0.0, (available_w - actual_row_w) / 2.0)

            # Alignement vertical sur les poches (stampBox)
            box_offsets = []
            for stamp in row:
                box = next((c for c in stamp.childItems() if c.data(0) == "stampBox"), None)
                box_offsets.append(box.y() if box else 0.0)

            target_box_offset = max(box_offsets) if box_offsets else 0.0

            for j, stamp in enumerate(row):
                y_adjust = target_box_offset - box_offsets[j]

                target_x = current_x - stamp.boundingRect().x()
                target_y = current_y + y_adjust - stamp.boundingRect().y()

                # Clamping / Sécurité stricte anti-débordement
                stamp_w = stamp.boundingRect().width()
                stamp_h = stamp.boundingRect().height()

                final_x = max(min_x_limit, min(target_x, max_x_limit - stamp_w))
                final_y = max(min_y_limit, min(target_y, max_y_limit - stamp_h))

                stamp.setPos(final_x, final_y)
                current_x += stamp_w + h_spacing

            current_y += row_heights[i] + v_spacing

        # 7. Enregistrer le déplacement global dans l'historique d'annulation (Undo)
        moved_items = []
        old_moved_positions = []
        for it, old_pos in zip(stamps, old_positions):
            if it.pos() != old_pos:
                moved_items.append(it)
                old_moved_positions.append(old_pos)

        if moved_items:
            cmd = MoveCommand(moved_items, old_moved_positions)
            self.undoStack.push(cmd)

    def autoArrangeStamps(self):
        """Arrange stamps by stamp number, aligning rows relative to the stamp images."""
        # 1. Filter stamps to arrange (supports both stampGroup and richTextStampGroup)
        valid_types = {"stampGroup", "richTextStampGroup"}
        selected_stamps = [
            it for it in self.selectedItems()
            if it.parentItem() is None and str(it.data(0)) in valid_types
        ]
        stamps = selected_stamps if len(selected_stamps) > 1 else [
            it for it in self.items()
            if it.parentItem() is None and str(it.data(0)) in valid_types
        ]

        if not stamps:
            return

        # Save initial positions for the Undo stack (Ctrl+Z)
        old_positions = [it.pos() for it in stamps]

        # 2. Natural sequential sorting by stamp number (e.g., 1, 2, 10 instead of 1, 10, 2)
        def get_stamp_number_key(stamp):
            nbr_item = next((c for c in stamp.childItems() if str(c.data(0)) == "stampNbr"), None)
            if nbr_item:
                text = nbr_item.toPlainText().strip() if hasattr(nbr_item, "toPlainText") else ""
            else:
                text = ""

            import re
            parts = re.split(r'(\d+)', text)
            return [int(p) if p.isdigit() else p.lower() for p in parts if p]

        stamps.sort(key=get_stamp_number_key)

        # 3. Retrieve bounding boundaries from the page border or scene
        border_item = next((it for it in self.items() if it.data(0) == "borderGroup"), None)
        if border_item:
            border_rect = border_item.sceneBoundingRect()
            padding = 10.0  # Internal safety padding
            min_x_limit = border_rect.left() + padding
            max_x_limit = border_rect.right() - padding
            min_y_limit = border_rect.top() + padding
            max_y_limit = border_rect.bottom() - padding
        else:
            px_w = self.sceneRect().width()
            px_h = self.sceneRect().height()
            min_x_limit = 50.0
            max_x_limit = px_w - 50.0
            min_y_limit = 100.0
            max_y_limit = px_h - 100.0

        available_w = max(100.0, max_x_limit - min_x_limit)

        # 4. Spacing configuration
        h_spacing = 20.0
        v_spacing = 25.0

        # 5. Row distribution without horizontal overflow
        rows = []
        current_row = []
        current_row_w = 0.0

        for stamp in stamps:
            stamp_w = stamp.boundingRect().width()
            if current_row and (current_row_w + h_spacing + stamp_w > available_w):
                rows.append(current_row)
                current_row = [stamp]
                current_row_w = stamp_w
            else:
                if current_row:
                    current_row_w += h_spacing + stamp_w
                else:
                    current_row_w = stamp_w
                current_row.append(stamp)

        if current_row:
            rows.append(current_row)

        # 6. Helper function to inspect the stamp image position and dimensions
        def get_image_info(stamp):
            """
            Return the Y offset and height of the image relative to the stamp group.
            Falls back to stampBox if no valid image is found.
            """
            img_item = next((c for c in stamp.childItems() if str(c.data(0)) == "pixmapItem"), None)
            if img_item and hasattr(img_item, "pixmap") and not img_item.pixmap().isNull():
                h = img_item.boundingRect().height() * img_item.scale()
                return img_item.y(), h

            box_item = next((c for c in stamp.childItems() if str(c.data(0)) == "stampBox"), None)
            if box_item:
                return box_item.y(), box_item.boundingRect().height()

            return 0.0, stamp.boundingRect().height()

        # Compute total required block height
        row_heights = [max(s.boundingRect().height() for s in row) for row in rows]
        total_block_h = sum(row_heights) + (len(rows) - 1) * v_spacing

        # Global vertical centering
        current_y = min_y_limit + max(0.0, (max_y_limit - min_y_limit - total_block_h) / 2.0)

        # 7. Row-by-row placement with vertical alignment centered on images
        for i, row in enumerate(rows):
            total_stamps_w = sum(s.boundingRect().width() for s in row)
            actual_row_w = total_stamps_w + (len(row) - 1) * h_spacing
            current_x = min_x_limit + max(0.0, (available_w - actual_row_w) / 2.0)

            # Compute vertical center coordinates for all images in the row
            img_centers = []
            for stamp in row:
                img_y, img_h = get_image_info(stamp)
                img_centers.append(img_y + (img_h / 2.0))

            target_img_center = max(img_centers) if img_centers else 0.0

            for stamp in row:
                img_y, img_h = get_image_info(stamp)
                stamp_img_center = img_y + (img_h / 2.0)

                # Vertical delta to align image centers across the row
                y_adjust = target_img_center - stamp_img_center

                target_x = current_x - stamp.boundingRect().x()
                target_y = current_y + y_adjust - stamp.boundingRect().y()

                stamp_w = stamp.boundingRect().width()
                stamp_h = stamp.boundingRect().height()

                # Boundary clamping to prevent overflowing outside the border
                final_x = max(min_x_limit, min(target_x, max_x_limit - stamp_w))
                final_y = max(min_y_limit, min(target_y, max_y_limit - stamp_h))

                stamp.setPos(final_x, final_y)
                current_x += stamp_w + h_spacing

            current_y += row_heights[i] + v_spacing

        # 8. Record the aggregated position changes into the Undo stack
        moved_items = []
        old_moved_positions = []
        for it, old_pos in zip(stamps, old_positions):
            if it.pos() != old_pos:
                moved_items.append(it)
                old_moved_positions.append(old_pos)

        if moved_items:
            cmd = MoveCommand(moved_items, old_moved_positions)
            self.undoStack.push(cmd)

    def clearGuides(self):
        """Remove all guidelines from the page."""
        guides = [it for it in self.items() if it.data(0) == "guideLine"]
        for g in guides:
            self.removeItem(g)

    def replaceBorder_old(self, new_style):
        """Remplace la bordure existante par un nouveau style, ou en crée une si elle n'existe pas."""
        old_border = None

        # Chercher la bordure actuelle sur la page
        for item in self.items():
            if item.data(0) == "borderGroup":
                old_border = item
                break

        if old_border:
            # Récupérer les dimensions et la position de l'ancienne bordure
            w = old_border.data(1)
            h = old_border.data(2)
            pos = old_border.pos()

            # Suppression + ajout regroupés : un seul Ctrl+Z restaure l'ancienne bordure
            self.undoStack.beginMacro(_("Change bordure"))
            self.undoStack.push(DeleteItemsCommand(self, [old_border]))
            new_border = PageBorder(w, h, style=new_style)
            new_border.setPos(pos)
            self.addItemWithUndo(new_border, _("Change bordure"))
            self.undoStack.endMacro()
        else:
            # Si aucune bordure n'était présente, on en génère une standard
            # format de CETTE page (et non celui de la configuration)
            w_mm, h_mm = self.page_width_mm, self.page_height_mm

            if self.pageType == "portrait":
                border_w = (w_mm - 33.0) / (25.4 / 96.0)
                border_h = (h_mm - 25.0) / (25.4 / 96.0)
                margin_l = 19.0 / (25.4 / 96.0)
                self.addBorder(border_w, border_h, margin_l, 0, 0, 0, new_style)
            else:
                border_w = (h_mm - 25.0) / (25.4 / 96.0)
                border_h = (w_mm - 33.0) / (25.4 / 96.0)
                margin_l = (((h_mm / (25.4 / 96.0)) - border_w) / 2)
                margin_t = 19.0 / (25.4 / 96.0)
                self.addBorder(border_w, border_h, margin_l, 0, margin_t, 0, new_style)

    def replaceBorder(self, new_style):
        """Replace existing border with a new style, or create one if none exists."""
        old_border = None

        # Search for current border item on the page
        for item in self.items():
            if item.data(0) == "borderGroup":
                old_border = item
                break

        if old_border:
            # Retrieve dimensions and coordinates of previous border
            w = old_border.data(1)
            h = old_border.data(2)
            pos = old_border.pos()

            # Group deletion + addition: a single Ctrl+Z restores the previous border
            self.undoStack.beginMacro(_("Change bordure"))
            self.undoStack.push(DeleteItemsCommand(self, [old_border]))
            new_border = PageBorder(w, h, style=new_style)
            new_border.setPos(pos)
            self.addItemWithUndo(new_border, _("Change bordure"))
            self.undoStack.endMacro()
        else:
            # Generate a default border using THIS page's dimensions if none exists
            w_mm, h_mm = self.page_width_mm, self.page_height_mm

            if self.pageType == "portrait":
                border_w = (w_mm - 33.0) / (25.4 / 96.0)
                border_h = (h_mm - 25.0) / (25.4 / 96.0)
                margin_l = 19.0 / (25.4 / 96.0)
                self.addBorder(border_w, border_h, margin_l, 0, 0, 0, new_style)
            else:
                border_w = (h_mm - 25.0) / (25.4 / 96.0)
                border_h = (w_mm - 33.0) / (25.4 / 96.0)
                margin_l = (((h_mm / (25.4 / 96.0)) - border_w) / 2)
                margin_t = 19.0 / (25.4 / 96.0)
                self.addBorder(border_w, border_h, margin_l, 0, margin_t, 0, new_style)