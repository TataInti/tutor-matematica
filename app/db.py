from pathlib import Path
import os
import sqlite3


DEFAULT_DB_PATH = Path("/data/tutor.db")


def connect_db(db_path: str | Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Abre una conexión persistente a SQLite y prepara su directorio."""
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(path)


def get_database_path() -> Path:
    return Path(os.environ.get("DATABASE_PATH", str(DEFAULT_DB_PATH)))


def _ensure_items_sabidos_table(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS items_sabidos (
            item_id TEXT PRIMARY KEY,
            unidad_id TEXT NOT NULL
        )
        """
    )


def get_known_item_ids(
    unidad_id: str, db_path: str | Path = DEFAULT_DB_PATH
) -> set[str]:
    connection = connect_db(db_path)
    try:
        _ensure_items_sabidos_table(connection)
        connection.commit()
        rows = connection.execute(
            "SELECT item_id FROM items_sabidos WHERE unidad_id = ?", (unidad_id,)
        )
        return {row[0] for row in rows}
    finally:
        connection.close()


def mark_item_known(
    item_id: str, unidad_id: str, db_path: str | Path = DEFAULT_DB_PATH
) -> None:
    connection = connect_db(db_path)
    try:
        _ensure_items_sabidos_table(connection)
        connection.execute(
            "INSERT OR IGNORE INTO items_sabidos (item_id, unidad_id) VALUES (?, ?)",
            (item_id, unidad_id),
        )
        connection.commit()
    finally:
        connection.close()
