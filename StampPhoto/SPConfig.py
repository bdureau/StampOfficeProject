import configparser
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QComboBox, QSpinBox, QDialogButtonBox, QGroupBox
)
from PyQt6.QtCore import Qt


class SPConfigDialog(QDialog):
    """Configuration dialog for StampPhoto allowing users to adjust

    language, JPEG export quality, and target resolutions.
    """

    def __init__(self, config: configparser.ConfigParser, parent=None, tr_func=None):
        super().__init__(parent)
        self.config = config
        self._ = tr_func if tr_func is not None else (lambda text: text)

        self.setWindowTitle(self._("Configuration"))
        self.setModal(True)
        self.setMinimumWidth(380)

        self._init_ui()
        self._load_values()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)

        # General settings group
        general_group = QGroupBox(self._("General Settings"))
        general_layout = QFormLayout(general_group)

        # Language selection combo box
        self.combo_lang = QComboBox()
        self.combo_lang.addItem(self._("English"), "en")
        self.combo_lang.addItem(self._("French"), "fr")
        general_layout.addRow(self._("Language:"), self.combo_lang)

        # JPEG Quality spin box
        self.spin_quality = QSpinBox()
        self.spin_quality.setRange(10, 100)
        self.spin_quality.setSingleStep(5)
        self.spin_quality.setSuffix(" %")
        general_layout.addRow(self._("JPEG Quality:"), self.spin_quality)

        main_layout.addWidget(general_group)

        # Resolutions settings group
        res_group = QGroupBox(self._("Max Width Resolutions (px)"))
        res_layout = QFormLayout(res_group)

        self.spin_low = QSpinBox()
        self.spin_low.setRange(200, 4000)
        self.spin_low.setSingleStep(50)
        res_layout.addRow(self._("Low resolution:"), self.spin_low)

        self.spin_med = QSpinBox()
        self.spin_med.setRange(400, 8000)
        self.spin_med.setSingleStep(100)
        res_layout.addRow(self._("Medium resolution:"), self.spin_med)

        self.spin_high = QSpinBox()
        self.spin_high.setRange(800, 16000)
        self.spin_high.setSingleStep(200)
        res_layout.addRow(self._("High resolution:"), self.spin_high)

        main_layout.addWidget(res_group)

        # Standard dialog action buttons (OK / Cancel)
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box.accepted.connect(self._save_and_accept)
        self.button_box.rejected.connect(self.reject)
        main_layout.addWidget(self.button_box)

    def _load_values(self):
        """Load values from the ConfigParser object into UI controls."""
        current_lang = self.config.get("General", "language", fallback="fr")
        idx = self.combo_lang.findData(current_lang)
        if idx >= 0:
            self.combo_lang.setCurrentIndex(idx)

        quality = int(self.config.get("General", "jpeg_quality", fallback="85"))
        self.spin_quality.setValue(quality)

        self.spin_low.setValue(int(self.config.get("Resolutions", "low_width", fallback="800")))
        self.spin_med.setValue(int(self.config.get("Resolutions", "medium_width", fallback="1600")))
        self.spin_high.setValue(int(self.config.get("Resolutions", "high_width", fallback="2400")))

    def _save_and_accept(self):
        """Save form values back into the ConfigParser instance."""
        if not self.config.has_section("General"):
            self.config.add_section("General")
        if not self.config.has_section("Resolutions"):
            self.config.add_section("Resolutions")

        self.config.set("General", "language", self.combo_lang.currentData())
        self.config.set("General", "jpeg_quality", str(self.spin_quality.value()))
        self.config.set("Resolutions", "low_width", str(self.spin_low.value()))
        self.config.set("Resolutions", "medium_width", str(self.spin_med.value()))
        self.config.set("Resolutions", "high_width", str(self.spin_high.value()))

        self.accept()