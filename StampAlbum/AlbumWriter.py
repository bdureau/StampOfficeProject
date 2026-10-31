"""
Album Writer
------------
Headless (window-less) album support used by the batch converter:

  * HeadlessAlbum  - a minimal stand-in for MainWindow.Window that exposes the
                     few members the importers need (newPage, getCurrentPageScene,
                     album_metadata), so AlbumEasyImporter and XlsAlbumImporter can
                     run without the editor's main window.
  * save_album()   - writes the pages to a .sta file (gzip-compressed XML) in the
                     same format as MainWindow.saveAlbumToFile, so converted albums
                     open normally in Stamp Album.

Keep save_album() in sync with MainWindow.saveAlbumToFile if the file format changes.

Author: Boris du Reau
"""
import gzip
import os
import platform
import xml.etree.ElementTree as ET
from datetime import datetime

from PyQt6 import QtCore

from Page import Page
from PageBorder import PageBorder

FILE_FORMAT_VERSION = "1.0"     # must match MainWindow.FILE_FORMAT_VERSION


class HeadlessAlbum:
    """Collects the pages created by an importer, without any GUI."""

    def __init__(self, on_new_page=None, border_style=None):
        self.pages = []
        # Border style of the pages ('triple', 'simple', 'greek', 'dentelle');
        # None uses the style configured in Stamp Album
        self.border_style = border_style
        self.album_metadata = {
            "creation_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "author": "",
            "language": "fr",
            "os": f"{platform.system()} {platform.release()}",
            "page_count": 0,
            "stamp_count": 0,
        }
        # Called after each new page (used by the converter to refresh progress and
        # keep the user interface responsive)
        self.on_new_page = on_new_page

    # --- interface used by the importers (same signatures as MainWindow.Window) ---
    def newPage(self, _pageType=None, border=None, paper_format=None,
                margin_size=None, margin_position=None):
        page_type = _pageType if _pageType in ("portrait", "landscape") else "portrait"
        page = Page(page_type, border=border, paper_format=paper_format,
                    border_style=self.border_style,
                    margin_size_mm=margin_size, margin_position=margin_position)
        page.album_language = self.album_metadata.get("language", "fr")
        self.pages.append(page)
        if self.on_new_page is not None:
            self.on_new_page(len(self.pages))
        return page

    def getCurrentPageScene(self):
        return self.pages[-1] if self.pages else None

    # --- helpers ---
    def stamp_count(self) -> int:
        return sum(1 for p in self.pages for it in p.items()
                   if it.parentItem() is None
                   and it.data(0) in ("stampGroup", "richTextStampGroup"))

    def dispose(self):
        """Release the scenes (and their pictures) once the album has been saved."""
        for page in self.pages:
            page.undoStack.clear()
            page.clear()
            page.deleteLater()
        self.pages = []


def pixmap_to_base64(pixmap) -> str:
    """Encode a QPixmap to a Base64 PNG string (same encoding as MainWindow.pixmapToBytes)."""
    if pixmap is None or pixmap.isNull():
        return ""
    ba = QtCore.QByteArray()
    buff = QtCore.QBuffer(ba)
    buff.open(QtCore.QIODevice.OpenModeFlag.WriteOnly)
    if not pixmap.save(buff, "PNG"):
        return ""
    return bytes(ba.toBase64()).decode()


def _num(value) -> str:
    """Box sizes in mm: '28' for whole numbers, '22.5' otherwise (the loader reads float())."""
    v = float(value)
    return str(int(v)) if v.is_integer() else str(round(v, 3))


def build_album_xml(pages, metadata: dict) -> ET.Element:
    """Build the XML tree of an album (same structure as MainWindow.saveAlbumToFile)."""
    root = ET.Element("album", version=FILE_FORMAT_VERSION)

    stamp_count = sum(1 for p in pages for it in p.items()
                      if it.parentItem() is None
                      and it.data(0) in ("stampGroup", "richTextStampGroup"))
    current_os = f"{platform.system()} {platform.release()}"
    creation_date = metadata.get("creation_date") or datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    meta_elem = ET.SubElement(root, "metadata")
    ET.SubElement(meta_elem, "creation_date").text = str(creation_date)
    ET.SubElement(meta_elem, "author").text = str(metadata.get("author", ""))
    ET.SubElement(meta_elem, "os").text = current_os
    ET.SubElement(meta_elem, "page_count").text = str(len(pages))
    ET.SubElement(meta_elem, "stamp_count").text = str(stamp_count)
    ET.SubElement(meta_elem, "language").text = str(metadata.get("language", "fr"))

    for x, scene in enumerate(pages):
        paper_fmt = getattr(scene, "paper_format", "A4")
        page = ET.SubElement(root, "page", name=str(x), type=str(scene.pageType),
                             paper_format=str(paper_fmt))

        for item in scene.items():
            item_type = item.type().real
            if item.parentItem() is not None:
                continue

            if item_type == 8:                                   # text item
                kind = item.data(0) or "textLabel"
                node = ET.SubElement(page, kind)
                if kind == "richTextLabel":
                    ET.SubElement(node, "html_label").text = item.toHtml()
                else:
                    ET.SubElement(node, "label").text = item.toPlainText()
                    font = ET.SubElement(node, "font")
                    ET.SubElement(font, "bold").text = str(item.font().bold())
                    ET.SubElement(font, "underline").text = str(item.font().underline())
                    ET.SubElement(font, "italic").text = str(item.font().italic())
                    ET.SubElement(font, "strikeOut").text = str(item.font().strikeOut())
                    ET.SubElement(font, "pointSize").text = str(item.font().pointSize())
                pos = ET.SubElement(node, "labelPos")
                ET.SubElement(pos, "x").text = str(item.x())
                ET.SubElement(pos, "y").text = str(item.y())

            elif item_type == 7:                                 # free picture
                node = ET.SubElement(page, "imageItem")
                ET.SubElement(node, "pixmapData").text = pixmap_to_base64(item.pixmap())
                pos = ET.SubElement(node, "imagePos")
                ET.SubElement(pos, "x").text = str(item.x())
                ET.SubElement(pos, "y").text = str(item.y())
                ET.SubElement(node, "scale").text = str(item.scale())

            elif item_type == 10 and item.data(0) == "borderGroup":
                border = ET.SubElement(page, "borderGroup")
                border.set("style", str(item.data(4) or PageBorder.STYLE_TRIPLE))
                pos = ET.SubElement(border, "borderPos")
                ET.SubElement(pos, "x").text = str(item.x())
                ET.SubElement(pos, "y").text = str(item.y())
                i = 0
                for child in item.childItems():
                    if child.type().real == 3:
                        i += 1
                        ET.SubElement(border, "width" + str(i)).text = str(child.data(1))
                        ET.SubElement(border, "height" + str(i)).text = str(child.data(2))

            elif item_type == 10 and item.data(0) == "stampGroup":
                stamp = ET.SubElement(page, "stampGroup")
                pos = ET.SubElement(stamp, "stampPos")
                ET.SubElement(pos, "x").text = str(item.x())
                ET.SubElement(pos, "y").text = str(item.y())
                for child in item.childItems():
                    ctype = child.type().real
                    if ctype == 8:
                        ET.SubElement(stamp, child.data(0)).text = child.toPlainText()
                    elif ctype == 7:
                        ET.SubElement(stamp, child.data(0)).text = pixmap_to_base64(child.pixmap())
                    elif ctype == 3:
                        size = ET.SubElement(stamp, child.data(0))
                        ET.SubElement(size, "width").text = str(child.boundingRect().width())
                        ET.SubElement(size, "height").text = str(child.boundingRect().height())
                        ET.SubElement(size, "stampBox_width").text = _num(child.data(1))
                        ET.SubElement(size, "stampBox_height").text = _num(child.data(2))

            elif item_type == 10 and item.data(0) == "richTextStampGroup":
                r_stamp = ET.SubElement(page, "richTextStampGroup")
                pos = ET.SubElement(r_stamp, "stampPos")
                ET.SubElement(pos, "x").text = str(item.x())
                ET.SubElement(pos, "y").text = str(item.y())
                for child in item.childItems():
                    key = str(child.data(0))
                    if key in ("stampDesc", "stampNbr", "stampValue"):
                        node = ET.SubElement(r_stamp, key)
                        ET.SubElement(node, "html").text = child.toHtml()
                    elif key == "pixmapItem":
                        ET.SubElement(r_stamp, "pixmapData").text = pixmap_to_base64(child.pixmap())
                    elif key == "stampBox":
                        box = ET.SubElement(r_stamp, "stampBox")
                        ET.SubElement(box, "width_mm").text = str(child.data(1))
                        ET.SubElement(box, "height_mm").text = str(child.data(2))
    return root


def save_album(pages, file_path: str, metadata: dict = None):
    """Write the pages to a .sta file.

    The file is first written next to the target under a temporary name and then
    renamed, so an interrupted or failed save never leaves a truncated album.
    """
    root = build_album_xml(pages, metadata or {})
    tmp_path = file_path + ".part"
    try:
        with gzip.open(tmp_path, "wb") as f:
            ET.ElementTree(root).write(f)
        os.replace(tmp_path, file_path)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
