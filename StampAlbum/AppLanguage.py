from SAAppPaths import get_config_value

_cached_lang = None


def get_language():
    """Read the language from the configuration file only once at startup."""
    global _cached_lang
    if _cached_lang is not None:
        return _cached_lang

    # Default language: "fr" (fault-tolerant reading UTF-8 / cp1252 via AppPaths)
    _cached_lang = get_config_value('language', "fr")
    return _cached_lang