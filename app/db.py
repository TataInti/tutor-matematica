from pathlib import Path
import sqlite3


DEFAULT_DB_PATH = Path("/data/tutor.db")


def connect_db(db_path: str | Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Abre una conexión persistente a SQLite y prepara su directorio."""
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(path)
