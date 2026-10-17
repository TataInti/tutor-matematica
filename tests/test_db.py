from app.db import connect_db


def test_row_survives_closing_and_reopening_database(tmp_path) -> None:
    db_path = tmp_path / "data" / "tutor.db"

    first_connection = connect_db(db_path)
    try:
        first_connection.execute(
            "CREATE TABLE progreso (id INTEGER PRIMARY KEY, valor TEXT NOT NULL)"
        )
        first_connection.execute(
            "INSERT INTO progreso (valor) VALUES (?)", ("persistente",)
        )
        first_connection.commit()
    finally:
        first_connection.close()

    reopened_connection = connect_db(db_path)
    try:
        row = reopened_connection.execute(
            "SELECT valor FROM progreso WHERE id = 1"
        ).fetchone()
    finally:
        reopened_connection.close()

    assert row == ("persistente",)
