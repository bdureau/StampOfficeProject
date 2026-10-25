"""
DatabaseAdapter Module
----------------------
Handles read/write operations and schema management for country Databases (SQLite or MS Access).
"""

import sqlite3
from pathlib import Path

try:
    import pyodbc
    HAS_PYODBC = True
except ImportError:
    HAS_PYODBC = False

import gettext
from SDAppLanguage import get_language

gettext.find("StampDatabase")
translate = gettext.translation(
    'StampDatabase', localedir='locale', languages=[get_language()], fallback=True
)
translate.install()
_ = translate.gettext


def test_ms_access_support() -> bool:
    """Check if pyodbc module is loaded and MS Access ODBC drivers are functional."""
    if not HAS_PYODBC:
        return False
    try:
        drivers = pyodbc.drivers()
        return any("Microsoft Access Driver" in driver for driver in drivers)
    except Exception:
        return False


class CountryDatabaseAdapter:
    """Handles read/write operations for country Databases (SQLite or MS Access)."""

    DB_INFO_COLUMNS = ["Author", "Country", "Description", "Version", "Catalogue", "Language"]

    def __init__(self, country: str, db_dir: Path, db_type: str = "sqlite"):
        self.country = country
        self.db_dir = db_dir
        self.db_type = db_type.lower()
        self.conn = None
        self.cursor = None

        self._connect()
        self.ensure_db_schema()

    def _connect(self):
        """Establish database connection based on type."""
        if self.db_type == "sqlite":
            db_path = self.db_dir / f"{self.country}.db"
            self.conn = sqlite3.connect(db_path)
            self.cursor = self.conn.cursor()
        else:
            if not test_ms_access_support():
                raise RuntimeError("MS Access support is unavailable or drivers are missing.")
            db_path = self.db_dir / f"{self.country}.mdb"
            conn_str = f"Driver={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={db_path};"
            self.conn = pyodbc.connect(conn_str)
            self.cursor = self.conn.cursor()

    def execute_query(self, query: str, params: tuple = ()):
        """Execute parameterized query."""
        self.cursor.execute(query, params)
        return self.cursor

    def ensure_db_schema(self):
        """Ensure Stamp_List and db_info tables exist for a functional database."""
        if self.db_type == "sqlite":
            self.execute_query("""
                CREATE TABLE IF NOT EXISTS Stamp_List (
                    key TEXT PRIMARY KEY,
                    nbr TEXT,
                    year TEXT,
                    type TEXT,
                    valuecolor TEXT,
                    stampDescription1 TEXT,
                    stampDescription TEXT,
                    width TEXT,
                    height TEXT,
                    sequence TEXT,
                    ascii_seq TEXT,
                    sub_nbr TEXT
                )
            """)

        existing_cols = self.get_db_info_existing_columns()
        if existing_cols is None:
            if self.db_type == "sqlite":
                self.execute_query("""
                    CREATE TABLE IF NOT EXISTS db_info (
                        Author TEXT,
                        Country TEXT,
                        Description TEXT,
                        Version TEXT,
                        Catalogue TEXT,
                        Language TEXT
                    )
                """)
                self.execute_query("""
                    INSERT INTO db_info (Author, Country, Description, Version, Catalogue, Language)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, ("Boris du Reau", self.country, f"{self.country} Stamp Catalogue", "1.0", "Yvert", "fr"))
                self.commit()

    def get_db_info_existing_columns(self):
        """Return existing column names for db_info, or None if table does not exist."""
        try:
            if self.db_type == "sqlite":
                res = self.execute_query("PRAGMA table_info(db_info)")
                rows = res.fetchall()
                if not rows:
                    return None
                return [row[1] for row in rows]
            else:
                res = self.execute_query("SELECT * FROM db_info WHERE 1=0")
                return [column[0] for column in res.description]
        except Exception:
            return None

    def get_db_info(self):
        """Fetch metadata dictionary and missing column list for db_info."""
        existing_cols = self.get_db_info_existing_columns()
        if not existing_cols:
            return {}, list(self.DB_INFO_COLUMNS)

        missing_cols = [c for c in self.DB_INFO_COLUMNS if c not in existing_cols]
        valid_cols = [c for c in self.DB_INFO_COLUMNS if c in existing_cols]

        if not valid_cols:
            return {}, list(self.DB_INFO_COLUMNS)

        query = f"SELECT {', '.join(valid_cols)} FROM db_info"
        try:
            res = self.execute_query(query)
            row = res.fetchone()
            if row:
                info_data = dict(zip(valid_cols, row))
            else:
                info_data = {}
        except Exception:
            info_data = {}

        return info_data, missing_cols

    def update_db_info(self, info_dict):
        """Update existing db_info columns."""
        existing_cols = self.get_db_info_existing_columns()
        if not existing_cols:
            return

        valid_updates = {k: v for k, v in info_dict.items() if k in existing_cols}
        if not valid_updates:
            return

        res = self.execute_query("SELECT COUNT(*) FROM db_info")
        count = res.fetchone()[0]

        if count == 0:
            cols = list(valid_updates.keys())
            vals = list(valid_updates.values())
            placeholders = ", ".join(["?"] * len(vals))
            query = f"INSERT INTO db_info ({', '.join(cols)}) VALUES ({placeholders})"
            self.execute_query(query, tuple(vals))
        else:
            set_clause = ", ".join([f"{k} = ?" for k in valid_updates.keys()])
            vals = list(valid_updates.values())
            query = f"UPDATE db_info SET {set_clause}"
            self.execute_query(query, tuple(vals))

        self.commit()

    def load_types(self):
        """Fetch distinct stamp categories."""
        res = self.execute_query("SELECT DISTINCT type FROM Stamp_List WHERE type IS NOT NULL ORDER BY type ASC")
        return [row[0] for row in res.fetchall() if row[0] is not None]

    def load_years(self):
        """Fetch distinct issue years."""
        res = self.execute_query("SELECT DISTINCT year FROM Stamp_List WHERE year IS NOT NULL ORDER BY year ASC")
        return [row[0] for row in res.fetchall() if row[0] is not None]

    def get_stamps(self, stamp_type=None, year=None, search_nbr=None):
        """Query catalogue stamps based on filters."""
        query = """
            SELECT key, nbr, year, type, valuecolor, stampDescription1, stampDescription, width, height, sequence, ascii_seq, sub_nbr
            FROM Stamp_List
            WHERE 1=1
        """
        params = []

        if stamp_type and stamp_type != _("All"):
            query += " AND type = ?"
            params.append(stamp_type)

        if year and year != _("All"):
            query += " AND year = ?"
            params.append(str(year))

        if search_nbr:
            query += " AND nbr LIKE ?"
            params.append(f"%{search_nbr}%")

        query += " ORDER BY sequence, ascii_seq, nbr ASC"
        res = self.execute_query(query, tuple(params))
        return res.fetchall()

    def update_stamp(self, key, nbr, year, stype, valcolor, desc1, desc, width, height, sequence, ascii_seq, sub_nbr):
        """Update an existing stamp record in catalogue."""
        query = """
            UPDATE Stamp_List
            SET nbr = ?, year = ?, type = ?, valuecolor = ?, stampDescription1 = ?, stampDescription = ?, width = ?, height = ?, sequence = ?, ascii_seq = ?, sub_nbr = ?
            WHERE key = ?
        """
        self.execute_query(query, (
            str(nbr), str(year), str(stype), str(valcolor), str(desc1), str(desc), str(width), str(height), str(sequence),
            str(ascii_seq), str(sub_nbr), key))

    def insert_stamp(self, stamp_data):
        """Insert a new stamp record into catalogue."""
        key, nbr, year, stype, valcolor, desc1, desc, width, height, sequence, ascii_seq, sub_nbr = stamp_data
        query = """
            INSERT INTO Stamp_List (key, nbr, year, type, valuecolor, stampDescription1, stampDescription, width, height, sequence, ascii_seq, sub_nbr)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        self.execute_query(query, (
            str(key), str(nbr), str(year), str(stype), str(valcolor), str(desc1), str(desc), str(width), str(height), str(sequence),
            str(ascii_seq), str(sub_nbr)))

    def delete_stamp(self, key):
        """Delete a stamp record by key."""
        query = "DELETE FROM Stamp_List WHERE key = ?"
        self.execute_query(query, (str(key),))

    def key_exists(self, key):
        """Check if a primary key already exists in Stamp_List."""
        res = self.execute_query("SELECT COUNT(*) FROM Stamp_List WHERE key = ?", (str(key),))
        return res.fetchone()[0] > 0

    def get_max_key(self):
        """Get max integer key from Stamp_List to generate new unique key."""
        res = self.execute_query("SELECT MAX(CAST(key AS INTEGER)) FROM Stamp_List")
        row = res.fetchone()
        if row and row[0] is not None:
            return int(row[0])
        return 0

    def commit(self):
        """Commit changes to database."""
        if self.conn:
            self.conn.commit()

    def close(self):
        """Close connection."""
        if self.conn:
            self.conn.close()