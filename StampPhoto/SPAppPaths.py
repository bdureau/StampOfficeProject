"""
SPAppPaths - Application paths of StampPhoto
--------------------------------------------
Single place that finds the folders and files of StampPhoto, both when it
runs from the Python sources and when it is compiled (PyInstaller one-file or
one-folder, cx_Freeze).

Resource folders (Images, locale, Help) are searched, in this order:
  1. the application root folder: the folder of the program (StampPhoto.py or
     StampPhoto.exe) or, when the program sits in a sub-folder, its parent
     folder if it holds Images, locale, Help...;
  2. the folder of the program itself;
  3. the files bundled inside the executable (PyInstaller: sys._MEIPASS).
Folders placed next to the program therefore take precedence over the copy
bundled in the executable: icons, translations or manuals can be updated
without rebuilding.

The configuration file is always written in the application root folder (or
in the user's settings folder when that folder is write-protected), never in
the temporary folder of a one-file executable, which is deleted on exit.

Author: Boris du Reau
Date: 2026-11-01
"""
import os
import sys
from pathlib import Path

# Folders whose presence identifies the application root folder
RESOURCE_FOLDERS = ("Images", "locale", "Help", "Photos", "Databases", "docs")


def is_frozen() -> bool:
    """True when running as a compiled executable."""
    return bool(getattr(sys, "frozen", False))


def get_program_dir() -> Path:
    """Folder of StampPhoto.exe (compiled) or of the Python sources."""
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def get_bundle_dir():
    """Folder of the files bundled in a PyInstaller executable, or None."""
    bundle = getattr(sys, "_MEIPASS", None)
    return Path(bundle) if bundle else None


def get_app_dir() -> Path:
    """Application root folder: the parent of the program folder when it holds
    one of the resource folders (program in a sub-folder), otherwise the
    program folder. Same rule for the sources and for the executable."""
    program_dir = get_program_dir()
    if any((program_dir.parent / folder).is_dir() for folder in RESOURCE_FOLDERS):
        return program_dir.parent
    return program_dir


def resource_dirs(name: str) -> list:
    """Existing folders called `name`, by order of preference (see module doc)."""
    candidates = [get_app_dir() / name, get_program_dir() / name]
    bundle = get_bundle_dir()
    if bundle is not None:
        candidates.append(bundle / name)
    found, seen = [], set()
    for folder in candidates:
        key = os.path.normcase(str(folder.resolve()))
        if key not in seen and folder.is_dir():
            seen.add(key)
            found.append(folder)
    return found


def get_resource_dir(name: str) -> Path:
    """First existing resource folder called `name` (application folder if none)."""
    folders = resource_dirs(name)
    return folders[0] if folders else get_app_dir() / name


def find_resource(folder: str, filename: str):
    """Path of a file of a resource folder (e.g. Images/config.png), or None.
    Each file is searched in every candidate folder, so a partial folder next
    to the program is completed by the copy bundled in the executable."""
    for directory in resource_dirs(folder):
        path = directory / filename
        if path.is_file():
            return path
    return None


def find_program_file(filename: str):
    """A file stored next to the program (e.g. StampPhoto.ico), or None."""
    candidates = [get_program_dir() / filename, get_app_dir() / filename]
    bundle = get_bundle_dir()
    if bundle is not None:
        candidates.append(bundle / filename)
    return next((p for p in candidates if p.is_file()), None)


def get_images_dir() -> Path:
    return get_resource_dir("Images")


def get_help_dir() -> Path:
    return get_resource_dir("Help")


def get_locale_dir(domain: str = "stampphoto", lang: str = None) -> Path:
    """The locale folder that holds the catalogue of the language
    (locale/<lang>/LC_MESSAGES/<domain>.mo), otherwise the first locale folder."""
    folders = resource_dirs("locale")
    if lang:
        for folder in folders:
            if (folder / lang / "LC_MESSAGES" / f"{domain}.mo").is_file():
                return folder
    return folders[0] if folders else get_app_dir() / "locale"


def get_config_path(filename: str) -> Path:
    """Configuration file in the application root folder; in the user's settings
    folder (…/StampPhoto) when the application folder is write-protected,
    e.g. under C:\\Program Files. Never in the temporary folder of a one-file
    executable."""
    path = get_app_dir() / filename
    if os.access(str(path if path.exists() else path.parent), os.W_OK):
        return path
    from PyQt6.QtCore import QStandardPaths
    user_dir = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.GenericConfigLocation))
    user_dir = user_dir / "StampPhoto"
    user_dir.mkdir(parents=True, exist_ok=True)
    return user_dir / filename


def diagnostic_report(domain: str = "stampphoto", lang: str = None, files=()) -> str:
    """Text describing where the resources were found (StampPhoto --diag)."""
    lines = [
        f"Frozen executable: {is_frozen()}",
        f"Program folder:    {get_program_dir()}",
        f"Application root:  {get_app_dir()}",
        f"Bundled files:     {get_bundle_dir() or '-'}",
        "",
    ]
    for name in ("Images", "locale", "Help"):
        found = resource_dirs(name)
        lines.append(f"{name}: " + (" | ".join(str(f) for f in found) if found else "NOT FOUND"))
    if lang:
        mo = get_locale_dir(domain, lang) / lang / "LC_MESSAGES" / f"{domain}.mo"
        lines.append(f"Catalogue ({lang}): {mo if mo.is_file() else 'NOT FOUND (' + str(mo) + ')'}")
    for folder, filename in files:
        path = find_resource(folder, filename) if folder else find_program_file(filename)
        lines.append(f"{(folder + '/') if folder else ''}{filename}: {path or 'NOT FOUND'}")
    return "\n".join(lines)
