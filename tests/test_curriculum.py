from pathlib import Path

import pytest
import yaml

from app.curriculum import CurriculumError, load_unit


UNIT_PATH = Path(__file__).resolve().parents[1] / "curriculum" / "probabilidad_condicional.yml"


def test_loads_probability_conditional_unit() -> None:
    unit = load_unit(UNIT_PATH)

    assert unit["id"] == "probabilidad_condicional"
    assert len(unit["items_opcion_multiple"]) == 5
    assert len(unit["ejercicios_papel"]) == 3
    assert all("resultado_esperado" in exercise for exercise in unit["ejercicios_papel"])


def test_rejects_paper_exercise_without_expected_result(tmp_path: Path) -> None:
    unit = load_unit(UNIT_PATH)
    del unit["ejercicios_papel"][0]["resultado_esperado"]
    invalid_unit = tmp_path / "unidad_incompleta.yml"
    invalid_unit.write_text(
        yaml.safe_dump(unit, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )

    with pytest.raises(CurriculumError, match="resultado_esperado"):
        load_unit(invalid_unit)
