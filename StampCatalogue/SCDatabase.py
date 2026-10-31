"""
Database Access Module
----------------------
Manages central user collections and reads country catalogue databases using SQLite.

Author: Boris du Reau
Year: 2026
"""

import sqlite3
from pathlib import Path
import gettext
from SCAppLanguage import get_language

# Localization setup
gettext.find("StampCatalogue")
translate = gettext.translation(
    'StampCatalogue', localedir='locale', languages=[get_language()], fallback=True
)
translate.install()
_ = translate.gettext


class CollectionManagerDB:
    """Manages the central 'collections.db' storing user collections and owned stamps."""

    def __init__(self, db_dir: Path):
        self.db_path = db_dir / "collections.db"
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()
        self._init_db()

    def _init_db(self):
        """Initialize central tables if they do not exist."""
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS collections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                country TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS collection_items (
                collection_id INTEGER NOT NULL,
                stamp_nbr TEXT NOT NULL,
                status TEXT NOT NULL,
                condition TEXT,
                quantity INTEGER DEFAULT 1,
                purchase_price REAL DEFAULT 0.0,
                notes TEXT,
                PRIMARY KEY (collection_id, stamp_nbr),
                FOREIGN KEY (collection_id) REFERENCES collections(id) ON DELETE CASCADE
            );
        """)
        self.conn.commit()

    def get_collections(self):
        """Fetch all user collections."""
        self.cursor.execute("SELECT id, name, country FROM collections ORDER BY name ASC")
        return self.cursor.fetchall()

    def create_collection(self, name: str, country: str) -> int:
        """Create a new collection linked to a specific country."""
        self.cursor.execute("INSERT INTO collections (name, country) VALUES (?, ?)", (name, country))
        self.conn.commit()
        return self.cursor.lastrowid

    def delete_collection(self, collection_id: int):
        """Delete a collection and all associated stamp items."""
        self.cursor.execute("DELETE FROM collections WHERE id = ?", (collection_id,))
        self.cursor.execute("DELETE FROM collection_items WHERE collection_id = ?", (collection_id,))
        self.conn.commit()

    def save_item(self, collection_id: int, stamp_nbr: str, status: str, condition: str,
                  quantity: int, price: float, notes: str):
        """Insert or update a stamp record inside a collection."""
        query = """
            INSERT INTO collection_items (collection_id, stamp_nbr, status, condition, quantity, purchase_price, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(collection_id, stamp_nbr) DO UPDATE SET
                status = excluded.status,
                condition = excluded.condition,
                quantity = excluded.quantity,
                purchase_price = excluded.purchase_price,
                notes = excluded.notes;
        """
        self.cursor.execute(query, (collection_id, str(stamp_nbr), status, condition, quantity, price, notes))
        self.conn.commit()

    def remove_item(self, collection_id: int, stamp_nbr: str):
        """Remove a stamp from a collection."""
        self.cursor.execute("DELETE FROM collection_items WHERE collection_id = ? AND stamp_nbr = ?",
                            (collection_id, str(stamp_nbr)))
        self.conn.commit()

    def get_collection_items(self, collection_id: int):
        """Fetch all saved items for a given collection ID."""
        self.cursor.execute("""
            SELECT stamp_nbr, status, condition, quantity, purchase_price, notes 
            FROM collection_items WHERE collection_id = ?
        """, (collection_id,))
        return {row[0]: row[1:] for row in self.cursor.fetchall()}

    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()


class CountryCatalogueDB:
    """Read-only database manager for country-specific stamp catalogues."""

    def __init__(self, country: str, db_dir: Path):
        self.country = country
        self.db_path = db_dir / f"{country}.db"

        # Open in read-only mode using SQLite URI
        uri = f"file:{self.db_path.as_posix()}?mode=ro"
        self.conn = sqlite3.connect(uri, uri=True)
        self.cursor = self.conn.cursor()

    def load_types(self):
        """Load unique categories/types for the current country."""
        self.cursor.execute("SELECT DISTINCT type FROM Stamp_List WHERE type IS NOT NULL ORDER BY type ASC")
        return [row[0] for row in self.cursor.fetchall()]

    def load_years(self):
        """Load unique issue years for the current country."""
        self.cursor.execute("SELECT DISTINCT year FROM Stamp_List WHERE year IS NOT NULL ORDER BY year ASC")
        return [row[0] for row in self.cursor.fetchall()]

    def get_stamps(self, stamp_type=None, year=None, search_nbr=None):
        """Query stamps from catalogue with optional filters."""
        query = """
            SELECT nbr, year, type, valuecolor, stampDescription, key, sub_nbr
            FROM Stamp_List
            WHERE 1=1
        """
        params = []

        if stamp_type and stamp_type != _("All"):
            query += " AND type = ?"
            params.append(stamp_type)

        if year and year != _("All"):
            query += " AND year = ?"
            params.append(year)

        if search_nbr:
            query += " AND nbr LIKE ?"
            params.append(f"%{search_nbr}%")

        query += " ORDER BY sequence, ascii_seq, nbr ASC"
        self.cursor.execute(query, params)
        return self.cursor.fetchall()

    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()