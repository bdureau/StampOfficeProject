"""
Application Language Module
---------------------------
Single source of the user interface language of StampCatalogue.

- get_language() reads the language from StampCatalogue.cfg
  (sections [General] or [CONF]).
- _() is the translation function used by every module. It always uses the
  catalogue of the current language, so a text translated after a change of
  language is immediately in the new language.
- set_language() changes the language while the application runs: it loads
  the new gettext catalogue, reloads Qt's own translations (standard buttons
  such as Yes / No) and notifies the registered windows so that they
  retranslate the texts they already display. No restart is needed.

Author: Boris du Reau
Date: 2026-10-31
"""
import configparser
import gettext

from SCAppPaths import get_config_path, get_locale_dir, read_config_into

DOMAIN = "StampCatalogue"
DEFAULT_LANGUAGE = "fr"

_cached_lang = None
_translation = None
_listeners = []
_qt_translator = None


def get_language(force_reload=False) -> str:
    """Return the configured language code ('fr', 'en'...)."""
    global _cached_lang
    if _cached_lang is not None and not force_reload:
        return _cached_lang

    lang = DEFAULT_LANGUAGE
    config_path = get_config_path()
    if config_path.exists():
        config = configparser.ConfigParser()
        try:
            read_config_into(config, config_path)
            if 'General' in config and 'language' in config['General']:
                lang = config['General']['language']
            elif 'CONF' in config and 'language' in config['CONF']:
                lang = config['CONF']['language']
        except Exception:
            pass

    _cached_lang = (lang or DEFAULT_LANGUAGE).strip() or DEFAULT_LANGUAGE
    return _cached_lang


def _load_translation(lang: str):
    return gettext.translation(DOMAIN, localedir=str(get_locale_dir()), languages=[lang], fallback=True)


def _(message: str) -> str:
    """Translate a message into the current language."""
    global _translation
    if _translation is None:
        _translation = _load_translation(get_language())
    return _translation.gettext(message)


def set_language(lang: str):
    """Switch the whole application to another language, without restarting."""
    global _cached_lang, _translation
    _cached_lang = lang
    _translation = _load_translation(lang)
    install_qt_translator()
    for callback in list(_listeners):
        try:
            callback()
        except RuntimeError:
            # The window was deleted without unregistering: forget it
            remove_language_listener(callback)


def add_language_listener(callback):
    """Register a function called after each change of language
    (typically a window's retranslate_ui method)."""
    if callback not in _listeners:
        _listeners.append(callback)


def remove_language_listener(callback):
    if callback in _listeners:
        _listeners.remove(callback)


def install_qt_translator():
    """Load Qt's own translations (standard dialog buttons...) for the current language."""
    global _qt_translator
    from PyQt6.QtCore import QLibraryInfo, QLocale, QTranslator
    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        return
    if _qt_translator is not None:
        app.removeTranslator(_qt_translator)
        _qt_translator = None
    translator = QTranslator(app)
    if translator.load(QLocale(get_language()), "qtbase", "_",
                       QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)):
        app.installTranslator(translator)
        _qt_translator = translator


def translations_in_all_languages(message: str) -> set:
    """The message and its translation in every available catalogue.

    Used to recognise texts that older versions saved in the database in the
    language of the moment (e.g. 'Possédé' as well as 'Owned')."""
    variants = {message}
    locale_dir = get_locale_dir()
    if locale_dir.is_dir():
        for lang_dir in locale_dir.iterdir():
            if (lang_dir / "LC_MESSAGES" / f"{DOMAIN}.mo").is_file():
                variants.add(_load_translation(lang_dir.name).gettext(message))
    return variants
