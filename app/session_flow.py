from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Mapping, Protocol, Sequence, cast


Perspective = Literal["vida", "empresa"]
PERSPECTIVE_ORDER: tuple[Perspective, ...] = ("vida", "empresa")
PERSPECTIVE_NAMES: dict[Perspective, str] = {
    "vida": "vida diaria",
    "empresa": "un proyecto de empresa genérico",
}


class TextTutor(Protocol):
    def complete_text(
        self, prompt: str, system_prompt: str | None = None
    ) -> dict[str, Any]: ...


class TutorResponseError(ValueError):
    """La respuesta del tutor no trae texto utilizable."""


@dataclass(frozen=True)
class FailureFeedback:
    texto: str | None
    perspectiva: Perspective | None
    perspectiva_nombre: str | None
    perspectivas_usadas: tuple[Perspective, ...]
    mostrar_paso_clave: bool
    paso_clave: str | None
    modelo_llamado: bool
    otra_perspectiva: bool


def _assistant_text(response: Mapping[str, Any]) -> str:
    try:
        content = response["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise TutorResponseError("El tutor no devolvió un mensaje de texto.") from exc
    if not isinstance(content, str) or not content.strip():
        raise TutorResponseError("El tutor no devolvió un mensaje de texto.")
    return content.strip()


def feedback_after_failure(
    tutor: TextTutor,
    exercise: Mapping[str, Any],
    used_perspectives: Sequence[str] = (),
) -> FailureFeedback:
    """Pide una perspectiva todavía no usada; agotadas ambas, muestra el YAML."""
    statement = exercise.get("enunciado")
    key_step = exercise.get("paso_clave")
    if not isinstance(statement, str) or not statement.strip():
        raise ValueError("El ejercicio necesita un enunciado.")
    if not isinstance(key_step, str) or not key_step.strip():
        raise ValueError("El ejercicio necesita paso_clave.")

    unknown = set(used_perspectives).difference(PERSPECTIVE_ORDER)
    if unknown:
        raise ValueError("Las perspectivas usadas tienen que ser vida o empresa.")
    used: tuple[Perspective, ...] = tuple(
        cast(Perspective, perspective)
        for perspective in PERSPECTIVE_ORDER
        if perspective in used_perspectives
    )
    perspective = cast(
        Perspective | None,
        next(
            (candidate for candidate in PERSPECTIVE_ORDER if candidate not in used),
            None,
        ),
    )

    if perspective is None:
        return FailureFeedback(
            texto=None,
            perspectiva=None,
            perspectiva_nombre=None,
            perspectivas_usadas=used,
            mostrar_paso_clave=True,
            paso_clave=key_step,
            modelo_llamado=False,
            otra_perspectiva=False,
        )

    prompt = (
        f"El alumno volvió a fallar este ejercicio: {statement}\n"
        f"Explicá el paso clave desde la perspectiva de {PERSPECTIVE_NAMES[perspective]}. "
        "Usá una explicación distinta y breve, sin repetir literalmente la anterior. "
        "No des el resultado final. Si usás un ejemplo de empresa, que sea genérico y "
        "sin nombres de clientes reales."
    )
    system_prompt = (
        "Sos un tutor de matemática. Respondé en español rioplatense, con claridad y sin "
        "inventar datos del ejercicio."
    )
    response = tutor.complete_text(prompt, system_prompt=system_prompt)
    if not isinstance(response, Mapping):
        raise TutorResponseError("El tutor no devolvió un objeto de respuesta válido.")

    return FailureFeedback(
        texto=_assistant_text(response),
        perspectiva=perspective,
        perspectiva_nombre=PERSPECTIVE_NAMES[perspective],
        perspectivas_usadas=(*used, perspective),
        mostrar_paso_clave=False,
        paso_clave=None,
        modelo_llamado=True,
        otra_perspectiva=bool(used),
    )
