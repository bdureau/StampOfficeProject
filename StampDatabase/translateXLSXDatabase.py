"""
translateXLSXDatabase Module
----------------------------
Handles translation of XLSX catalogue files with rate-limit recovery
and multi-engine fallback (GoogleTranslator + MyMemoryTranslator).
"""

from pathlib import Path
import time
import pandas as pd
from deep_translator import GoogleTranslator, MyMemoryTranslator

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QComboBox, QFileDialog, QMessageBox,
    QProgressDialog, QDialogButtonBox
)

import gettext
from SDAppLanguage import get_language

gettext.find("translateXLSXDatabase")
translate = gettext.translation(
    'translateXLSXDatabase', localedir='locale', languages=[get_language()], fallback=True
)
translate.install()
_ = translate.gettext

# Table de correspondance vers les identifiants supportés par MyMemory
MYMEMORY_LANG_MAP = {
    "en": "en-GB",
    "fr": "fr-FR",
    "de": "de-DE",
    "es": "es-ES",
    "it": "it-IT",
    "nl": "nl-NL"
}


class TranslationWorker(QThread):
    progress_changed = pyqtSignal(int, str)
    finished_success = pyqtSignal(str, int, int)
    failed = pyqtSignal(str)

    def __init__(self, input_file: str, output_file: str, target_language: str):
        super().__init__()
        self.input_file = input_file
        self.output_file = output_file
        self.target_language = target_language
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def _translate_single(self, text: str, google_inst, mymemory_inst) -> str:
        """Tente de traduire un texte via Google, avec bascule transparente sur MyMemory si bloqué."""
        # 1. Tentative avec Google
        if google_inst is not None:
            try:
                res = google_inst.translate(text)
                if res and res.strip():
                    return res.strip()
            except Exception as e:
                err_str = str(e).lower()
                if "too many requests" in err_str or "server error" in err_str:
                    time.sleep(2.0)

        # 2. Repli vers MyMemory
        if mymemory_inst is not None:
            try:
                res = mymemory_inst.translate(text)
                if res and res.strip():
                    return res.strip()
            except Exception:
                pass

        return text

    def run(self):
        try:
            df = pd.read_excel(self.input_file)
        except Exception as e:
            self.failed.emit(f"{_('Error reading file:')} {str(e)}")
            return

        target_names = ["valuecolor", "stampDescription1", "stampDescription"]
        cols_to_translate = [c for c in target_names if c in df.columns]

        if not cols_to_translate:
            if len(df.columns) >= 7:
                cols_to_translate = [df.columns[4], df.columns[5], df.columns[6]]
            else:
                self.failed.emit(_("The Excel file must contain at least 7 columns (A to G)."))
                return

        # 1. Extraire les entrées textuelles uniques à traduire
        unique_texts_set = set()
        for col_name in cols_to_translate:
            for cell_value in df[col_name]:
                if pd.notna(cell_value):
                    text = str(cell_value).strip()
                    # Ignorer les valeurs vides, purement numériques ou trop courtes
                    if text and not text.isdigit() and len(text) > 1:
                        unique_texts_set.add(text)

        unique_texts = sorted(list(unique_texts_set))
        total_unique = len(unique_texts)

        if total_unique == 0:
            df.to_excel(self.output_file, index=False)
            self.finished_success.emit(self.output_file, 0, 0)
            return

        # 2. Initialisation des moteurs de traduction
        try:
            google_translator = GoogleTranslator(source='fr', target=self.target_language)
        except Exception:
            google_translator = None

        try:
            mm_src = MYMEMORY_LANG_MAP.get("fr", "fr-FR")
            mm_tgt = MYMEMORY_LANG_MAP.get(self.target_language, "en-GB")
            mymemory_translator = MyMemoryTranslator(source=mm_src, target=mm_tgt)
        except Exception:
            mymemory_translator = None

        translation_map = {}
        success_count = 0
        fail_count = 0

        # 3. Traduction terme à terme avec cache mémoire
        for idx, text in enumerate(unique_texts, start=1):
            if self._is_cancelled:
                return

            translated = self._translate_single(text, google_translator, mymemory_translator)
            translation_map[text] = translated

            if translated.strip().lower() != text.strip().lower():
                success_count += 1
            else:
                fail_count += 1

            self.progress_changed.emit(
                idx,
                f"{_('Translating entries...')} ({idx}/{total_unique})"
            )
            # Petite temporisation pour respecter le quota réseau
            time.sleep(0.35)

        # 4. Reporter les traductions dans le tableau Excel
        for col_name in cols_to_translate:
            df[col_name] = df[col_name].apply(
                lambda val: translation_map.get(str(val).strip(), val) if pd.notna(val) else ""
            )

        try:
            df.to_excel(self.output_file, index=False)
            self.finished_success.emit(self.output_file, success_count, fail_count)
        except Exception as e:
            self.failed.emit(f"{_('Error saving Excel file:')} {str(e)}")


class TranslateDialog(QDialog):
    """Dialog allowing user to choose the input XLSX file and target language."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(_("Translate XLSX Catalogue"))
        self.resize(480, 160)

        layout = QVBoxLayout(self)

        file_layout = QHBoxLayout()
        self.edit_path = QLineEdit()
        self.edit_path.setPlaceholderText(_("Select .xlsx file..."))
        self.edit_path.setReadOnly(True)
        btn_browse = QPushButton(_("Browse..."))
        btn_browse.clicked.connect(self._browse_file)
        file_layout.addWidget(self.edit_path)
        file_layout.addWidget(btn_browse)
        layout.addLayout(file_layout)

        lang_layout = QHBoxLayout()
        lang_layout.addWidget(QLabel(_("Target Language:")))
        self.combo_lang = QComboBox()
        self.combo_lang.addItem(_("English"), "en")
        self.combo_lang.addItem(_("French"), "fr")
        self.combo_lang.addItem(_("German"), "de")
        self.combo_lang.addItem(_("Spanish"), "es")
        self.combo_lang.addItem(_("Italian"), "it")
        self.combo_lang.addItem(_("Dutch"), "nl")
        lang_layout.addWidget(self.combo_lang)
        layout.addLayout(lang_layout)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        ok_btn = buttons.button(QDialogButtonBox.StandardButton.Ok)
        if ok_btn:
            ok_btn.setText(_("OK"))
        cancel_btn = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        if cancel_btn:
            cancel_btn.setText(_("Cancel"))
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _browse_file(self):
        file_path, _filter = QFileDialog.getOpenFileName(
            self, _("Select Excel File"), "", "Excel Files (*.xlsx);;All Files (*)"
        )
        if file_path:
            self.edit_path.setText(file_path)

    def _validate_and_accept(self):
        if not self.edit_path.text().strip():
            QMessageBox.warning(self, _("Warning"), _("Please select a file to translate."))
            return
        self.accept()

    def get_settings(self):
        in_path = Path(self.edit_path.text().strip())
        lang_code = self.combo_lang.currentData()
        out_path = in_path.parent / f"{in_path.stem}_{lang_code}{in_path.suffix}"
        return str(in_path), str(out_path), lang_code


def translate_xlsx_interactive(parent_window):
    """Entry point: prompts dialog, tracks unique texts count, and runs worker thread."""
    dialog = TranslateDialog(parent_window)
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return

    input_file, output_file, lang_code = dialog.get_settings()

    try:
        df_preview = pd.read_excel(input_file)
        target_names = ["valuecolor", "stampDescription1", "stampDescription"]
        cols = [c for c in target_names if c in df_preview.columns]
        if not cols and len(df_preview.columns) >= 7:
            cols = [df_preview.columns[4], df_preview.columns[5], df_preview.columns[6]]

        unique_count = len({
            str(val).strip()
            for c in cols
            for val in df_preview[c]
            if pd.notna(val) and str(val).strip() and not str(val).strip().isdigit() and len(str(val).strip()) > 1
        })
    except Exception as e:
        QMessageBox.critical(parent_window, _("Error"), f"{_('Could not read Excel file:')}\n{str(e)}")
        return

    progress = QProgressDialog(_("Preparing translation..."), _("Cancel"), 0, max(unique_count, 1), parent_window)
    progress.setWindowTitle(_("Translating File"))
    progress.setWindowModality(Qt.WindowModality.WindowModal)
    progress.setMinimumDuration(0)
    progress.setAutoClose(False)
    progress.setAutoReset(False)
    progress.setValue(0)

    worker = TranslationWorker(input_file, output_file, lang_code)

    def on_progress(val, text):
        progress.setValue(val)
        progress.setLabelText(text)

    def on_success(out_path, success_count, fail_count):
        progress.close()
        msg = f"{_('Translated file successfully saved as:')}\n{out_path}\n\n"
        msg += f"{_('Entries translated:')} {success_count}\n"
        if fail_count > 0:
            msg += f"{_('Entries unchanged or untranslated:')} {fail_count}"
        QMessageBox.information(parent_window, _("Translation Complete"), msg)

    def on_fail(err):
        progress.close()
        QMessageBox.critical(parent_window, _("Translation Error"), err)

    worker.progress_changed.connect(on_progress)
    worker.finished_success.connect(on_success)
    worker.failed.connect(on_fail)
    progress.canceled.connect(worker.cancel)

    worker.start()
    progress.exec()