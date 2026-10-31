"""
Configuration Manager Module
----------------------------
Handles loading, saving, and persisting application settings to INI format.

Author: Boris du Reau
Year: 2026
"""

import configparser
from pathlib import Path
from SCAppLanguage import get_language


class ConfigManager:
    """Manages application settings stored in a Windows-style INI file."""

    def __init__(self, config_file: Path):
        self.config_file = config_file
        self.config = configparser.ConfigParser()
        self.load()

    def load(self):
        """Load configuration from file or apply default values."""
        if self.config_file.exists():
            self.config.read(self.config_file, encoding='utf-8')
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