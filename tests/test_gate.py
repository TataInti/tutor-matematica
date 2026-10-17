from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.db import get_database_path, get_known_item_ids, mark_item_known
from app.main import app
from app.pages import DIAGNOSTIC_PATH, DIAGNOSTIC_UNIT_ID, SESSION_PATH


ITEM_IDS = ("alg-01", "alg-02", "alg-03", "alg-04", "alg-05")


@pytest.fixture
def isolated_database(tmp_path: Path):
    db_path = tmp_path / "tutor.db"
    app.dependency_overrides[get_database_path] = lambda: db_path
    try:
        yield db_path
    finally:
        app.dependency_overrides.pop(get_database_path, None)


def test_probability_redirects_to_diagnostic_without_known_items(
    isolated_database: Path,
) -> None:
    with TestClient(app, follow_redirects=False) as client:
        response = client.get(SESSION_PATH)

    assert response.status_code == 307
    assert response.headers["location"] == DIAGNOSTIC_PATH


def test_probability_opens_when_all_five_diagnostic_items_are_known(
    isolated_database: Path,
) -> None:
    for item_id in ITEM_IDS:
        mark_item_known(item_id, DIAGNOSTIC_UNIT_ID, isolated_database)

    with TestClient(app, follow_redirects=False) as client:
        response = client.get(SESSION_PATH)

    assert response.status_code == 200
    assert "Probabilidad condicional" in response.text


def test_wrong_first_answer_shows_step_without_revealing_next_question(
    isolated_database: Path,
) -> None:
    with TestClient(app, follow_redirects=False) as client:
        response = client.post(
            DIAGNOSTIC_PATH,
            data={"item_id": "alg-01", "respuesta": "a"},
        )

    assert response.status_code == 200
    assert "La fracción 12/18 simplificada es:" in response.text
    assert "Dividí numerador y denominador por 6." in response.text
    assert "¿A qué porcentaje equivale la fracción 3/4?" not in response.text
    assert get_known_item_ids(DIAGNOSTIC_UNIT_ID, isolated_database) == set()


def test_correct_first_answer_shows_second_but_not_third_question(
    isolated_database: Path,
) -> None:
    with TestClient(app, follow_redirects=False) as client:
        response = client.post(
            DIAGNOSTIC_PATH,
            data={"item_id": "alg-01", "respuesta": "b"},
        )

    assert response.status_code == 200
    assert "¿A qué porcentaje equivale la fracción 3/4?" in response.text
    assert "Resolvé la ecuación 4x = 1,2" not in response.text
    assert get_known_item_ids(DIAGNOSTIC_UNIT_ID, isolated_database) == {"alg-01"}
