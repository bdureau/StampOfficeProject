"""
App Paths Module
----------------
Single place for the application paths (root folder, databases, photos,
images, help, translations), for reading the configuration file and for
listing the available country databases.

Works both from the Python sources and from an executable built with
PyInstaller/cx_Freeze (sys.frozen).

Author: Boris du Reau
Date: 2026-10-31
"""
import configparser
import sys
from pathlib import Path

CONFIG_FILE_NAME = "StampCatalogue.cfg"
CONFIG_ENCODING = "utf-8"

# Folders whose presence identifies the application root folder
_RESOURCE_FOLDERS = ["Databases", "Images", "Photos", "docs", "Help", "locale"]


def get_app_dir_old() -> Path:
    """Application folder (folder of the .exe when the application is compiled)."""
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def get_app_dir() -> Path:
    """
    Root folder of the application.

    - Executable (sys.frozen): the folder that contains the executable.
    - Python script (.py in a sub-folder such as StampCatalogue/): the parent
      folder when it contains one of the resource folders, otherwise the
      script folder.
    """
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).resolve().parent

    script_dir = Path(__file__).resolve().parent
    parent_dir = script_dir.parent

    # Go up one level if one of the main resource folders lives there
    if any((parent_dir / folder).exists() for folder in _RESOURCE_FOLDERS):
        return parent_dir

    return script_dir


def get_config_path() -> Path:
    return get_app_dir() / CONFIG_FILE_NAME


def get_db_dir() -> Path:
    return get_app_dir() / "Databases"


def get_photos_dir() -> Path:
    return get_app_dir() / "Photos"


def get_images_dir() -> Path:
    return get_app_dir() / "Images"


def get_help_dir() -> Path:
    return get_app_dir() / "Help"


def get_locale_dir() -> Path:
    """Folder of the gettext catalogues (locale/<lang>/LC_MESSAGES/StampCatalogue.mo).

    Looked up in the application root folder first, then next to the sources,
    then in the current folder (previous behaviour)."""
    for candidate in (get_app_dir() / "locale", Path(__file__).resolve().parent / "locale"):
        if candidate.is_dir():
            return candidate
    return Path("locale")


def read_config_into(parser: configparser.RawConfigParser, path: Path = None) -> configparser.RawConfigParser:
    """
    Load the configuration file into the given parser.

    The file is written in UTF-8, but older versions wrote it with the default
    Windows encoding (cp1252, where "©" is byte 0xA9). UTF-8 is tried first,
    then cp1252, so both formats remain readable.
    """
    path = path or get_config_path()
    if not path.exists():
        return parser

    for encoding in (CONFIG_ENCODING, "cp1252"):
        try:
            with open(path, "r", encoding=encoding) as f:
                parser.read_file(f, source=str(path))
            return parser
        except UnicodeDecodeError:
            parser.clear()
    # Last resort: never prevent the application from starting because of one character
    with open(path, "r", encoding=CONFIG_ENCODING, errors="replace") as f:
        parser.read_file(f, source=str(path))
    return parser


def read_config() -> configparser.RawConfigParser:
    """Read StampCatalogue.cfg (returns an empty parser if the file does not exist)."""
    return read_config_into(configparser.RawConfigParser())


def get_config_value(option: str, default: str = "") -> str:
    """Return an option of the [CONF] section, or the default value."""
    parser = read_config()
    if parser.has_option('CONF', option):
        return parser.get('CONF', option)
    return default


def get_db_type() -> str:
    """'sqlite' (default) or 'Access'."""
    return get_config_value("database type", "sqlite")


def get_db_extension(db_type: str = None) -> str:
    """Extension of the database files for the configured engine."""
    db_type = db_type or get_db_type()
    return ".db" if db_type.lower() == "sqlite" else ".mdb"


def list_countries(db_type: str = None) -> list:
    """
    Sorted list of the countries available in the Databases/ folder,
    keeping only the files of the configured engine (.db or .mdb).
    """
    db_dir = get_db_dir()
    if not db_dir.is_dir():
        return []

    ext = get_db_extension(db_type)
    countries = [
        f.stem for f in db_dir.iterdir()
        if f.is_file() and f.suffix.lower() == ext and f.stem.lower() != "master"
    ]
    return sorted(countries, key=str.lower)
