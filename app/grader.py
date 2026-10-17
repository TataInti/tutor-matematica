from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping


DEFAULT_NUMERIC_TOLERANCE = Decimal("0.000000001")
ALLOWED_CONFIDENCE = {"alta", "baja", "ilegible"}
REQUIRED_READING_FIELDS = {
    "legible",
    "transcripcion",
    "resultado",
    "confianza",
    "motivo_si_ilegible",
}


class VisionReadError(ValueError):
    """La salida de visión es inválida o no se puede interpretar como lectura."""


@dataclass(frozen=True)
class VisionReading:
    legible: bool
    transcripcion: str
    resultado: str | None
    confianza: str
    motivo_si_ilegible: str | None


@dataclass(frozen=True)
class GradeOutcome:
    calificado: bool
    correcto: bool | None
    esperado: str
    leido: str | None
    motivo: str | None = None


def parse_vision_response(payload: str | bytes | Mapping[str, Any]) -> VisionReading:
    if isinstance(payload, bytes):
        try:
            payload = payload.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise VisionReadError("La lectura de visión no está codificada en UTF-8.") from exc

    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise VisionReadError("La respuesta de visión no contiene JSON válido.") from exc

    if not isinstance(payload, Mapping):
        raise VisionReadError("La respuesta de visión tiene que ser un objeto JSON.")
    missing = REQUIRED_READING_FIELDS.difference(payload)
    if missing:
        missing_fields = ", ".join(sorted(missing))
        raise VisionReadError(f"Faltan campos en la lectura de visión: {missing_fields}.")

    legible = payload["legible"]
    transcription = payload["transcripcion"]
    confidence = payload["confianza"]
    result = payload["resultado"]
    reason = payload["motivo_si_ilegible"]
    if not isinstance(legible, bool):
        raise VisionReadError("El campo legible tiene que ser booleano.")
    if not isinstance(transcription, str):
        raise VisionReadError("El campo transcripcion tiene que ser texto.")
    if not isinstance(confidence, str) or confidence not in ALLOWED_CONFIDENCE:
        raise VisionReadError("La confianza tiene que ser alta, baja o ilegible.")
    if result is not None and not isinstance(result, (str, int, float)):
        raise VisionReadError("El campo resultado tiene que ser texto o un número.")
    if reason is not None and not isinstance(reason, str):
        raise VisionReadError("El campo motivo_si_ilegible tiene que ser texto o null.")

    result_text = None if result is None else str(result).strip()
    if legible and confidence == "alta" and not result_text:
        raise VisionReadError("La lectura de confianza alta no incluye un resultado.")

    return VisionReading(
        legible=legible,
        transcripcion=transcription,
        resultado=result_text,
        confianza=confidence,
        motivo_si_ilegible=reason,
    )


def _decimal(value: Any) -> Decimal | None:
    if isinstance(value, bool) or value is None:
        return None
    text = unicodedata.normalize("NFKC", str(value)).strip()
    text = re.sub(r"\s+", "", text).replace("−", "-")
    if not text:
        return None

    if text.count("/") == 1:
        numerator_text, denominator_text = text.split("/", 1)
        numerator = _decimal(numerator_text)
        denominator = _decimal(denominator_text)
        if numerator is None or denominator in (None, Decimal(0)):
            return None
        return numerator / denominator
    if "/" in text:
        return None

    if "," in text:
        if "." in text or text.count(",") != 1:
            return None
        text = text.replace(",", ".")
    try:
        return Decimal(text)
    except InvalidOperation:
        return None


def results_match(
    actual: str | int | float,
    expected: str | int | float,
    tolerance: Decimal = DEFAULT_NUMERIC_TOLERANCE,
) -> bool:
    actual_number = _decimal(actual)
    expected_number = _decimal(expected)
    if actual_number is not None and expected_number is not None:
        return abs(actual_number - expected_number) <= tolerance

    normalize = lambda value: re.sub(
        r"\s+", "", unicodedata.normalize("NFKC", str(value)).casefold()
    )
    return normalize(actual) == normalize(expected)


def grade_reading(expected: str | int | float, reading: VisionReading) -> GradeOutcome:
    expected_text = str(expected)
    if not reading.legible or reading.confianza != "alta":
        return GradeOutcome(
            calificado=False,
            correcto=None,
            esperado=expected_text,
            leido=reading.resultado,
            motivo=reading.motivo_si_ilegible or "La lectura no tiene confianza alta.",
        )

    if reading.resultado is None:
        raise VisionReadError("La lectura de confianza alta no incluye un resultado.")
    return GradeOutcome(
        calificado=True,
        correcto=results_match(reading.resultado, expected),
        esperado=expected_text,
        leido=reading.resultado,
    )


def grade_vision_response(
    expected: str | int | float, payload: str | bytes | Mapping[str, Any]
) -> GradeOutcome:
    return grade_reading(expected, parse_vision_response(payload))
