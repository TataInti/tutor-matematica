from __future__ import annotations

from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.curriculum import find_unit_path, load_unit
from app.session_flow import FailureFeedback, feedback_after_failure


class MockTutor:
    def __init__(self) -> None:
        self.calls: list[dict[str, str | None]] = []

    def complete_text(
        self, prompt: str, system_prompt: str | None = None
    ) -> dict[str, Any]:
        self.calls.append({"prompt": prompt, "system_prompt": system_prompt})
        return {
            "choices": [
                {"message": {"content": f"Pista simulada número {len(self.calls)}."}}
            ]
        }


def _paper_exercise() -> dict[str, Any]:
    unit = load_unit(find_unit_path("probabilidad_condicional.yml"))
    return unit["ejercicios_papel"][0]


def test_second_failure_uses_perspective_not_used_in_first_feedback() -> None:
    tutor = MockTutor()
    exercise = _paper_exercise()

    first = feedback_after_failure(tutor, exercise)
    second = feedback_after_failure(tutor, exercise, first.perspectivas_usadas)

    assert first.perspectiva == "vida"
    assert second.perspectiva == "empresa"
    assert second.otra_perspectiva is True
    assert "proyecto de empresa genérico" in (tutor.calls[1]["prompt"] or "")
    assert len(tutor.calls) == 2


def test_third_failure_shows_yaml_step_without_calling_tutor() -> None:
    tutor = MockTutor()
    exercise = _paper_exercise()
    used = ("vida", "empresa")

    feedback = feedback_after_failure(tutor, exercise, used)

    assert feedback.modelo_llamado is False
    assert feedback.mostrar_paso_clave is True
    assert feedback.paso_clave == exercise["paso_clave"]
    assert tutor.calls == []

    template_dir = Path(__file__).resolve().parents[1] / "app" / "templates"
    environment = Environment(
        loader=FileSystemLoader(template_dir),
        autoescape=select_autoescape(["html"]),
    )
    template = environment.get_template("sesion.html")
    unit = load_unit(find_unit_path("probabilidad_condicional.yml"))
    rendered = template.render(
        unidad=unit,
        respuestas={},
        resultados=None,
        feedback=feedback,
    )

    assert "Paso clave" in rendered
    assert exercise["paso_clave"] in rendered
