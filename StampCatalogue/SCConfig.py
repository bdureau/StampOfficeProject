"""
Configuration Manager Module
----------------------------
Handles loading, saving, and persisting the application settings
(language, database type) in the INI file StampCatalogue.cfg.

Author: Boris du Reau
Date: 2026-10-31
"""

import configparser
from pathlib import Path

from SCAppLanguage import get_language
from SCAppPaths import read_config_into


class ConfigManager:
    """Manages application settings stored in a Windows-style INI file."""

    def __init__(self, config_file: Path):
        self.config_file = config_file
        self.config = configparser.ConfigParser()
        self.load()

    def load(self):
        """Load configuration from file or apply default values."""
        if self.config_file.exists():
            # UTF-8 first, then cp1252 for files written by older versions
            read_config_into(self.config, self.config_file)
        else:
            self._set_defaults()
            self.save()

    def _set_defaults(self):
        """Set fallback default settings."""
        self.config['General'] = {
            'language': get_language(),
            'db_type': 'SQLite'
        }

    def get_language(self) -> str:
        """Return configured application language code."""
        return self.config.get('General', 'language', fallback=get_language())

    def get_db_type(self) -> str:
        """Return configured database backend type."""
        return self.config.get('General', 'db_type', fallback='SQLite')

    def set_settings(self, language: str, db_type: str):
        """Update and save application configuration."""
        if 'General' not in self.config:
            self.config['General'] = {}
        self.config['General']['language'] = language
        self.config['General']['db_type'] = db_type
        self.save()

    def save(self):
        """Write current settings to disk."""
        with open(self.config_file, 'w', encoding='utf-8') as f:
            self.config.write(f)
