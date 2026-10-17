from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.curriculum import load_unit
from app.db import get_database_path, mark_item_known
from app.main import app


SESSION_PATH = "/sesion/probabilidad-condicional"
UNIT_PATH = Path(__file__).resolve().parents[1] / "curriculum" / "probabilidad_condicional.yml"
DIAGNOSTIC_ITEM_IDS = ("alg-01", "alg-02", "alg-03", "alg-04", "alg-05")
DIAGNOSTIC_UNIT_ID = "algebra_diagnostico"


@pytest.fixture(autouse=True)
def approved_diagnosis(tmp_path: Path):
    db_path = tmp_path / "tutor.db"
    app.dependency_overrides[get_database_path] = lambda: db_path
    for item_id in DIAGNOSTIC_ITEM_IDS:
        mark_item_known(item_id, DIAGNOSTIC_UNIT_ID, db_path)
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_database_path, None)


def test_session_page_shows_concept_and_multiple_choice_test() -> None:
    with TestClient(app) as client:
        response = client.get(SESSION_PATH)

    assert response.status_code == 200
    assert "Probabilidad condicional" in response.text
    assert "Test rápido" in response.text
    assert response.text.count("<fieldset>") == 5


def test_correct_answer_marks_item_as_known() -> None:
    unit = load_unit(UNIT_PATH)
    first_question = unit["items_opcion_multiple"][0]

    with TestClient(app) as client:
        response = client.post(
            SESSION_PATH,
            data={first_question["id"]: first_question["respuesta_correcta"]},
        )

    assert response.status_code == 200
    assert "Ítem sabido: elegiste la opción correcta." in response.text


def test_two_wrong_answers_do_not_unlock_paper_exercises() -> None:
    unit = load_unit(UNIT_PATH)
    answers = {}
    for index, question in enumerate(unit["items_opcion_multiple"]):
        correct = question["respuesta_correcta"]
        if index < 2:
            answers[question["id"]] = next(
                option["id"] for option in question["opciones"] if option["id"] != correct
            )
        else:
            answers[question["id"]] = correct

    with TestClient(app) as client:
        response = client.post(SESSION_PATH, data=answers)

    assert response.status_code == 200
    assert "todavía no pasás al ejercicio en papel" in response.text
    assert unit["ejercicios_papel"][0]["enunciado"] not in response.text
