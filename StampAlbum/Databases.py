"""
Database Access Module
----------------------
Handles database connections and queries for both the master database
(stamp boxes, global settings, messages) and country-specific Databases
(stamp catalogues, series, types, and issues).

Supports SQLite and Microsoft Access (via PyODBC).

Author: Boris du Reau
"""
import sqlite3
from pathlib import Path

from SAAppPaths import get_app_dir, get_db_dir, get_db_type

# pyodbc is only required for Microsoft Access: we do not enforce it in sqlite mode
try:
    import pyodbc
except ImportError:  # pragma: no cover
    pyodbc = None


class DB:
    """Manages database connections and query operations for master and country Databases."""
    def __init__(self, country: str):
        self.country = country

        # Define portable system paths using pathlib
        self.base_dir = get_app_dir()
        self.db_dir = get_db_dir()

        # Load database engine preference from configuration file
        self.dbtype = get_db_type()

        # Initialize connection and cursor instances
        self.con_master = None
        self.con_country = None
        self.dbCurMaster = None
        self.dbCurCountry = None

        self._init_db_connections(country)

    def get_app_dir(self) -> Path:
        """Return the base directory path, compatible with PyInstaller frozen executables."""
        return get_app_dir()

    def _is_sqlite(self) -> bool:
        return self.dbtype.lower() == "sqlite"

    def _connect_sqlite(self, path: Path):
        # sqlite3.connect silently creates an empty file if the path does not exist:
        # we check first to provide a clear error message.
        if not path.is_file():
            raise FileNotFoundError(f"Database not found: {path}")
        return sqlite3.connect(path)

    def _connect_access(self, path: Path):
        if pyodbc is None:
            raise RuntimeError(_("pyodbc is required to open Microsoft Access Databases"))
        if not path.is_file():
            raise FileNotFoundError(f"Database not found: {path}")
        return pyodbc.connect(f"Driver={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={path};")

    def _init_db_connections(self, country: str):
        """Establish connections to master and selected country Databases based on configuration."""
        if self._is_sqlite():
            self.con_master = self._connect_sqlite(self.db_dir / "master.db")
        else:
            self.con_master = self._connect_access(self.db_dir / "master.mdb")
        self.dbCurMaster = self.con_master.cursor()

        self.OpenCountryDB(country)

    def OpenCountryDB(self, country: str):
        """Close existing country connection and open a new country database."""
        if self.dbCurCountry:
            self.dbCurCountry.close()
        if self.con_country:
            self.con_country.close()

        if self._is_sqlite():
            self.con_country = self._connect_sqlite(self.db_dir / f"{country}.db")
        else:
            self.con_country = self._connect_access(self.db_dir / f"{country}.mdb")
        self.dbCurCountry = self.con_country.cursor()
        self.country = country

    def DBExecute(self, cursor, statement: str, params: tuple = ()):
        """Execute a SQL statement using parameterized queries to prevent SQL injection."""
        cursor.execute(statement, params)
        return cursor

    def loadBoxList(self):
        """Retrieve all available stamp mount box names ordered by dimension."""
        query = "SELECT pochette FROM StampBox ORDER BY lx, ly ASC"
        res = self.DBExecute(self.dbCurMaster, query)
        return [row[0] for row in res.fetchall()]

    def getCurrentBox(self, SelectedBox: str):
        """Get width (lx) and height (ly) dimensions for a selected stamp box name."""
        query = "SELECT lx, ly FROM StampBox WHERE pochette = ?"
        res = self.DBExecute(self.dbCurMaster, query, (SelectedBox,))
        row = res.fetchone()
        return [row[0], row[1]] if row else []

    def loadStampType(self):
        """Retrieve distinct stamp category types from the active country catalogue."""
        query = (
            "SELECT DISTINCT type FROM Stamp_List WHERE type IS NOT NULL ORDER"
            " BY type ASC"
        )
        res = self.DBExecute(self.dbCurCountry, query)
        return [row[0] for row in res.fetchall() if row[0] is not None]

    def loadStampList(self, stampType: str, year: str):
        """Load stamp keys and catalogue numbers filtered by stamp category and issue year."""
        query = """
            SELECT key, nbr FROM Stamp_list 
            WHERE type = ? AND year = ? 
            ORDER BY sequence, ascii_seq, nbr, year ASC
        """
        res = self.DBExecute(self.dbCurCountry, query, (stampType, year))
        return [[row[0], row[1]] for row in res.fetchall() if row[0] is not None]

    def getMinYearForType(self, stampType: str):
        """Find the earliest available issue year for a given stamp type."""
        query = (
            "SELECT DISTINCT year FROM Stamp_List WHERE type = ? AND year IS NOT"
            " NULL ORDER BY year ASC"
        )
        res = self.DBExecute(self.dbCurCountry, query, (stampType,))
        row = res.fetchone()
        return row[0] if row else ""

    def loadYearList(self, stampType: str):
        """Retrieve all unique issue years for a specified stamp category."""
        query = """
            SELECT DISTINCT year FROM Stamp_list 
            WHERE type = ? AND year IS NOT NULL 
            ORDER BY year ASC
        """
        res = self.DBExecute(self.dbCurCountry, query, (stampType,))
        return [row[0] for row in res.fetchall()]

    def getStampSubNbr(self, Key):
        """Get sub-number designations associated with a specific stamp record key."""
        query = "SELECT sub_nbr FROM stamp_list WHERE Key = ?"
        res = self.DBExecute(self.dbCurCountry, query, (Key,))
        return [row[0] for row in res.fetchall()]

    def getPochette(self, stampNbr, stampType, stampYear, stampKey):
        """Find matching stamp mount box dimensions based on stamp width and height."""
        query1 = """
            SELECT width, height FROM stamp_list 
            WHERE type = ? AND year = ? AND nbr = ? AND key = ?
        """
        res = self.DBExecute(
            self.dbCurCountry,
            query1,
            (str(stampType), str(stampYear), str(stampNbr), stampKey),
        )
        row = res.fetchone()

        width = row[0] if row and row[0] else "0"
        height = row[1] if row and row[1] else "0"

        query2 = "SELECT pochette FROM StampBox WHERE lx = ? AND ly = ?"
        res2 = self.DBExecute(self.dbCurMaster, query2, (width, height))
        ret = [r[0] for r in res2.fetchall()]

        if not ret:
            ret.append("Pochette 30x41")
        return ret

    def stampChanged(self, stampNbr, Key):
        """Fetch full details for a selected stamp record."""
        query = """
            SELECT nbr, year, valuecolor, stampDescription, width, height, sub_nbr, stampDescription1 
            FROM stamp_list
            WHERE nbr = ? AND Key = ?
        """
        res = self.DBExecute(self.dbCurCountry, query, (str(stampNbr), Key))
        row = res.fetchone()
        return list(row) if row else []

    def getMessage(self, msgLanguage: str, msgCode):
        """Fetch system UI message strings from master database by language and code."""
        query = (
            "SELECT message_text, message_type FROM messages WHERE"
            " message_language = ? AND message_code = ?"
        )
        res = self.DBExecute(
            self.dbCurMaster, query, (msgLanguage, str(msgCode))
        )
        return [row[0] for row in res.fetchall()]

    def getTranslation(self, msgLanguage: str, msgCode):
        """Fetch localized text translations from master database."""
        query = (
            "SELECT msg_text FROM translations WHERE msg_language = ? AND"
            " msg_code = ?"
        )
        res = self.DBExecute(
            self.dbCurMaster, query, (msgLanguage, str(msgCode))
        )
        return [row[0] for row in res.fetchall()]

    def close(self):
        """Explicitly close all active master and country database connections."""
        if self.con_country:
            self.con_country.close()
        if self.con_master:
            self.con_master.close()