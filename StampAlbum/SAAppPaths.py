"""
App Paths Module
----------------
Single entry point for application file paths, configuration loading,
and listing available country database files.

Compatible with PyInstaller/cx_Freeze frozen executables (sys.frozen).

Author: Boris du Reau
"""
import configparser
import sys
from pathlib import Path

CONFIG_FILE_NAME = "stamp_album.cfg"


def get_app_dir_old() -> Path:
    """Application directory (the directory containing the executable if frozen)."""
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def get_app_dir() -> Path:
    """
        Root application directory.

        - In frozen executable mode (sys.frozen): returns the directory containing the binary.
        - In Python script mode (.py in a subfolder like StampAlbum/):
          traverses up to the parent directory if it contains any of the resource folders.
    """
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).resolve().parent

    script_dir = Path(__file__).resolve().parent
    parent_dir = script_dir.parent

    # Check if any of the primary resource folders exist in the parent directory
    if any((parent_dir / folder).exists() for folder in ["Databases", "Images", "Photos", "docs", "Help"]):
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


CONFIG_ENCODING = "utf-8"


def read_config_into(parser: configparser.RawConfigParser, path: Path = None) -> configparser.RawConfigParser:
    """
        Load configuration file content into the provided configparser instance.

        The file is typically written in UTF-8, but legacy versions wrote it using
        the Windows default codepage (cp1252, where '©' is the single byte 0xA9).
        We try UTF-8 first, followed by cp1252: both encodings remain readable.
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
    # Last resort fallback: never crash startup due to an unreadable character
    with open(path, "r", encoding=CONFIG_ENCODING, errors="replace") as f:
        parser.read_file(f, source=str(path))
    return parser


def read_config() -> configparser.RawConfigParser:
    """Read stamp_album.cfg (returns an empty parser if file does not exist)."""
    return read_config_into(configparser.RawConfigParser())


def get_config_value(option: str, default: str = "") -> str:
    """Return an option value from the [CONF] section, or the default value."""
    parser = read_config()
    if parser.has_option('CONF', option):
        return parser.get('CONF', option)
    return default


def get_db_type() -> str:
    """'sqlite' (default) or 'Access'."""
    return get_config_value("database type", "sqlite")


def get_db_extension(db_type: str = None) -> str:
    """Return database file extension based on configured engine."""
    db_type = db_type or get_db_type()
    return ".db" if db_type.lower() == "sqlite" else ".mdb"


def list_countries(db_type: str = None) -> list:
    """
        Sorted list of available country databases found in the Databases/ directory,
        filtering only files matching the configured engine (.db or .mdb).
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
