"""
DropImageLabel Module
---------------------
Custom QLabel component that supports drag-and-drop operations
for image files (JPG, PNG, WebP, BMP).
"""

from pathlib import Path
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel
from PyQt6.QtGui import QDragEnterEvent, QDropEvent

# Localization setup
import gettext
from SDAppLanguage import get_language

gettext.find("StampDatabase")
translate = gettext.translation(
    'StampDatabase', localedir='locale', languages=[get_language()], fallback=True
)
translate.install()
_ = translate.gettext

VALID_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


class DropImageLabel(QLabel):
    """QLabel accepting drag-and-drop operations for image files."""

    def __init__(self, main_window, parent=None):
        super().__init__(_("No Photo Available"), parent)
        self.main_window = main_window
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event: QDragEnterEvent):
        """Filters incoming dragged items to accept only local image files."""
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if urls:
                file_path = Path(urls[0].toLocalFile())
                if file_path.suffix.lower() in VALID_IMAGE_EXTENSIONS:
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dropEvent(self, event: QDropEvent):
        """Processes the dropped image file and delegates to the main window."""
        urls = event.mimeData().urls()
        if not urls:
            return

        source_path = Path(urls[0].toLocalFile())
        if not source_path.is_file():
            return

        if hasattr(self.main_window, "handle_dropped_image"):
            self.main_window.handle_dropped_image(source_path)
            event.acceptProposedAction()
        else:
            event.ignore()