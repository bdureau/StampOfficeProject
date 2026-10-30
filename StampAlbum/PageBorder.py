"""
Page Border Module
------------------
Provides customizable page border graphics items for stamp album pages.

Author: Boris du Reau
"""

from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtWidgets import QGraphicsItemGroup, QGraphicsRectItem, QGraphicsPathItem
from PyQt6.QtGui import QPen, QBrush, QColor, QPainterPath


class PageBorder(QGraphicsItemGroup):
    """Graphics item group representing a decorative page border."""
    STYLE_TRIPLE = "triple"  # Classic 3-box border (original default style)
    STYLE_SIMPLE = "simple"  # Clean double frame with an inner fine line
    STYLE_GREEK = "greek"  # Vintage frame with indented decorative corners
    STYLE_DENTELLE = "dentelle"  # Philatelic style (frame with dashed/perforated lines)

    def __init__(self, width: float, height: float, style: str = STYLE_TRIPLE, parent=None):
        """
        Initialize a page border.

        Args:
            width (float): Total outer width of the border (in pixels/DPI).
            height (float): Total outer height of the border (in pixels/DPI).
            style (str): Border style name.
        """
        super().__init__(parent)
        self.width = width
        self.height = height
        self.style = style

        self.setData(0, "borderGroup")
        self.setData(1, width)
        self.setData(2, height)
        self.setData(4, style)  # Store style key identifier ('triple', 'simple', 'greek', 'dentelle')

        self._build_border()

    def _build_border(self):
        """Build graphic sub-items based on the selected style."""
        if self.style == self.STYLE_SIMPLE:
            self._create_simple_border()
        elif self.style == self.STYLE_GREEK:
            self._create_greek_border()
        elif self.style == self.STYLE_DENTELLE:
            self._create_dentelle_border()
        else:
            self._create_triple_border()

    def _create_triple_border(self):
        """Style 1: Traditional triple frame (Thin line - Thick line - Thin line)."""
        # Outer thin box
        b1 = QGraphicsRectItem(0, 0, self.width, self.height)
        b1.setPen(QPen(Qt.GlobalColor.black, 1))
        b1.setData(1, self.width)
        b1.setData(2, self.height)

        # Middle thick box
        w2 = self.width - 10
        h2 = self.height - 10
        b2 = QGraphicsRectItem(0, 0, w2, h2)
        b2.setPen(QPen(Qt.GlobalColor.black, 4))
        b2.setPos(5, 5)
        b2.setData(1, w2)
        b2.setData(2, h2)

        # Inner thin box
        w3 = self.width - 19
        h3 = self.height - 19
        b3 = QGraphicsRectItem(0, 0, w3, h3)
        b3.setPen(QPen(Qt.GlobalColor.black, 1))
        b3.setPos(9, 9)
        b3.setData(1, w3)
        b3.setData(2, h3)

        self.addToGroup(b1)
        self.addToGroup(b2)
        self.addToGroup(b3)

    def _create_simple_border(self):
        """Style 2: Clean and classic double outer frame."""
        # Outer thick border
        b1 = QGraphicsRectItem(0, 0, self.width, self.height)
        b1.setPen(QPen(Qt.GlobalColor.black, 2))
        b1.setData(1, self.width)
        b1.setData(2, self.height)

        # Inner fine fillet
        margin = 6
        w2 = self.width - (margin * 2)
        h2 = self.height - (margin * 2)
        b2 = QGraphicsRectItem(0, 0, w2, h2)
        b2.setPen(QPen(Qt.GlobalColor.black, 1))
        b2.setPos(margin, margin)
        b2.setData(1, w2)
        b2.setData(2, h2)

        self.addToGroup(b1)
        self.addToGroup(b2)

    def _create_greek_border(self):
        """Style 3: Frame with notched/indented corners (vintage exhibition style)."""
        corner_size = 15

        # Main outline path with notched corners
        path = QPainterPath()
        w, h = self.width, self.height
        c = corner_size

        # Top-left corner
        path.moveTo(c, 0)
        path.lineTo(w - c, 0)
        # Top-right
        path.lineTo(w - c, c)
        path.lineTo(w, c)
        path.lineTo(w, h - c)
        # Bottom-right
        path.lineTo(w - c, h - c)
        path.lineTo(w - c, h)
        path.lineTo(c, h)
        # Bottom-left
        path.lineTo(c, h - c)
        path.lineTo(0, h - c)
        path.lineTo(0, c)
        path.lineTo(c, c)
        path.closeSubpath()

        item = QGraphicsPathItem(path)
        item.setPen(QPen(Qt.GlobalColor.black, 2))
        item.setData(1, w)
        item.setData(2, h)
        self.addToGroup(item)

        # Inner fine fillet
        margin = 6
        b_inner = QGraphicsRectItem(margin, margin, w - 2 * margin, h - 2 * margin)
        b_inner.setPen(QPen(Qt.GlobalColor.black, 1))
        b_inner.setData(1, w - 2 * margin)
        b_inner.setData(2, h - 2 * margin)
        self.addToGroup(b_inner)

    def _create_dentelle_border(self):
        """Style 4: Philatelic style with a dashed/perforated inner frame."""
        # Outer solid border
        b1 = QGraphicsRectItem(0, 0, self.width, self.height)
        b1.setPen(QPen(Qt.GlobalColor.black, 2))
        b1.setData(1, self.width)
        b1.setData(2, self.height)

        # Inner dashed border (stamp perforation effect)
        margin = 8
        w2 = self.width - (margin * 2)
        h2 = self.height - (margin * 2)
        b2 = QGraphicsRectItem(0, 0, w2, h2)

        pen_dash = QPen(Qt.GlobalColor.black, 1, Qt.PenStyle.DashLine)
        b2.setPen(pen_dash)
        b2.setPos(margin, margin)
        b2.setData(1, w2)
        b2.setData(2, h2)

        self.addToGroup(b1)
        self.addToGroup(b2)