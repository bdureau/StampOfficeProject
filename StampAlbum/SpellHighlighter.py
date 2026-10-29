"""
SpellHighlighter Module
-----------------------
Custom QSyntaxHighlighter using pyspellchecker to highlight
spelling errors in real-time with a red wavy underline.
"""

import re
from PyQt6.QtGui import QSyntaxHighlighter, QTextCharFormat, QColor
from spellchecker import SpellChecker

WORD_PATTERN = re.compile(r"\b[^\W\d_]+\b")


class SpellHighlighter(QSyntaxHighlighter):
    """Underlines misspelled words dynamically using pyspellchecker."""

    def __init__(self, parent_document, language="fr"):
        super().__init__(parent_document)
        self.language = language
        self.spell = None
        self.known_cache = set()
        self.misspelled_cache = set()

        # Format de soulignement rouge type correcteur orthographique
        self.error_format = QTextCharFormat()
        self.error_format.setUnderlineColor(QColor("#e53e3e"))
        self.error_format.setUnderlineStyle(QTextCharFormat.UnderlineStyle.SpellCheckUnderline)

        self.set_language(language)

    def set_language(self, lang_code: str):
        """Met à jour le dictionnaire utilisé ('fr', 'en', 'de', 'es', etc.)."""
        # pyspellchecker accepte les codes 2 lettres (fr, en, es, de, pt, ru, it)
        lang = (lang_code or "fr").lower()
        if lang not in ["fr", "en", "de", "es", "it", "pt", "ru"]:
            lang = "fr"

        self.language = lang
        self.known_cache.clear()
        self.misspelled_cache.clear()

        try:
            self.spell = SpellChecker(language=self.language)
        except Exception as e:
            print(f"[SpellHighlighter] Error loading dictionary for '{self.language}': {e}")
            self.spell = None

        self.rehighlight()

    def highlightBlock(self, text: str):
        if not self.spell or not text.strip():
            return

        for match in WORD_PATTERN.finditer(text):
            word = match.group()
            # On ignore les mots de moins de 2 lettres
            if len(word) < 2:
                continue

            word_lower = word.lower()

            if word_lower in self.known_cache:
                continue

            if word_lower in self.misspelled_cache:
                self.setFormat(match.start(), len(word), self.error_format)
                continue

            # Vérification via pyspellchecker
            if word_lower not in self.spell:
                self.misspelled_cache.add(word_lower)
                self.setFormat(match.start(), len(word), self.error_format)
            else:
                self.known_cache.add(word_lower)