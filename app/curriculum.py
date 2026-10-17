from pathlib import Path
from typing import Any

import yaml


class CurriculumError(ValueError):
    """Error de lectura o validación de una unidad del temario."""


def load_unit(path: str | Path) -> dict[str, Any]:
    """Carga una unidad YAML y valida los campos necesarios para la v1."""
    source = Path(path)
    try:
        with source.open(encoding="utf-8") as file:
            unit = yaml.safe_load(file)
    except OSError as exc:
        raise CurriculumError(f"No se pudo leer la unidad: {source}") from exc
    except yaml.YAMLError as exc:
        raise CurriculumError(f"El YAML de la unidad no es válido: {source}") from exc

    if not isinstance(unit, dict):
        raise CurriculumError("La unidad tiene que ser un objeto YAML.")

    for field in (
        "id",
        "prerrequisito",
        "explicacion",
        "ejemplo_vida",
        "ejemplo_empresa",
    ):
        if field not in unit or unit[field] is None or unit[field] == "":
            raise CurriculumError(f"Falta el campo obligatorio: {field}.")

    questions = unit.get("items_opcion_multiple")
    if not isinstance(questions, list) or len(questions) != 5:
        raise CurriculumError("La unidad tiene que incluir cinco ítems de opción múltiple.")

    for index, question in enumerate(questions, start=1):
        context = f"items_opcion_multiple[{index - 1}]"
        if not isinstance(question, dict):
            raise CurriculumError(f"{context} tiene que ser un objeto.")
        options = question.get("opciones")
        if not isinstance(options, list) or not options:
            raise CurriculumError(f"{context} tiene que incluir opciones.")
        option_ids = {
            option.get("id")
            for option in options
            if isinstance(option, dict) and option.get("id") is not None
        }
        if question.get("respuesta_correcta") not in option_ids:
            raise CurriculumError(
                f"{context} tiene que señalar una respuesta_correcta presente en las opciones."
            )
        for field in ("id", "pregunta"):
            if field not in question or not question[field]:
                raise CurriculumError(f"Falta {field} en {context}.")

    exercises = unit.get("ejercicios_papel")
    if not isinstance(exercises, list) or len(exercises) != 3:
        raise CurriculumError("La unidad tiene que incluir tres ejercicios de papel.")

    for index, exercise in enumerate(exercises):
        context = f"ejercicios_papel[{index}]"
        if not isinstance(exercise, dict):
            raise CurriculumError(f"{context} tiene que ser un objeto.")
        for field in ("id", "enunciado", "resultado_esperado", "paso_clave"):
            if field not in exercise or exercise[field] is None or exercise[field] == "":
                raise CurriculumError(f"Falta {field} en {context}.")

    return unit


def find_unit_path(filename: str) -> Path:
    """Encuentra una unidad tanto desde el repo como desde la imagen Docker."""
    candidates = (
        Path(__file__).resolve().parent.parent / "curriculum" / filename,
        Path.cwd() / "curriculum" / filename,
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return candidates[0]
