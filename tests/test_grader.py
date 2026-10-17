from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from app.grader import (
    VisionReadError,
    grade_vision_response,
    parse_vision_response,
    results_match,
)
from app.openrouter import OpenRouterClient
from app.uploads import (
    MAX_UPLOAD_BYTES,
    ImageTooLargeError,
    UnsupportedImageTypeError,
    read_image_upload,
    validate_image_upload,
)


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "vision_ok.json"


def test_decimal_comma_decimal_point_and_fraction_match() -> None:
    assert results_match("0,25", "0.25")
    assert results_match("0.25", "0.25")
    assert results_match("1/4", "0.25")


def test_high_confidence_fixture_is_graded_correctly() -> None:
    reading = parse_vision_response(FIXTURE_PATH.read_text(encoding="utf-8"))
    outcome = grade_vision_response("0.25", reading.__dict__)

    assert outcome.calificado is True
    assert outcome.correcto is True


def test_low_confidence_is_not_graded() -> None:
    payload = {
        "legible": True,
        "transcripcion": "0,25?",
        "resultado": "0,25",
        "confianza": "baja",
        "motivo_si_ilegible": None,
    }

    outcome = grade_vision_response("0.25", payload)

    assert outcome.calificado is False
    assert outcome.correcto is None


def test_illegible_reading_is_not_graded() -> None:
    payload = {
        "legible": False,
        "transcripcion": "",
        "resultado": None,
        "confianza": "ilegible",
        "motivo_si_ilegible": "La hoja está movida.",
    }

    outcome = grade_vision_response("0.25", payload)

    assert outcome.calificado is False
    assert outcome.correcto is None


def test_invalid_model_json_is_a_read_error_not_a_wrong_answer() -> None:
    with pytest.raises(VisionReadError, match="JSON válido"):
        grade_vision_response("0.25", "esto no es JSON")


def test_valid_but_wrong_answer_is_graded_as_incorrect() -> None:
    payload = {
        "legible": True,
        "transcripcion": "0.5",
        "resultado": "0.5",
        "confianza": "alta",
        "motivo_si_ilegible": None,
    }

    outcome = grade_vision_response("0.25", payload)

    assert outcome.calificado is True
    assert outcome.correcto is False


def test_jpeg_and_png_are_accepted_and_other_types_are_rejected() -> None:
    jpeg = validate_image_upload(b"\xff\xd8\xffdata", "image/jpeg")
    png = validate_image_upload(b"\x89PNG\r\n\x1a\ndata", "image/png")

    assert jpeg.media_type == "image/jpeg"
    assert png.media_type == "image/png"
    with pytest.raises(UnsupportedImageTypeError):
        validate_image_upload(b"GIF89a", "image/gif")


def test_oversized_photo_is_rejected_before_http_request() -> None:
    requests = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        return httpx.Response(200, json={})

    client = OpenRouterClient(
        api_key="mock-key",
        vision_model="vision-model-from-test-env",
        transport=httpx.MockTransport(handler),
    )
    oversized = b"\xff\xd8\xff" + b"x" * (MAX_UPLOAD_BYTES - 2)
    try:
        with pytest.raises(ImageTooLargeError):
            client.complete_vision("Leé la respuesta.", oversized, "image/jpeg")
    finally:
        client.close()

    assert requests == 0


@pytest.mark.anyio
async def test_upload_reader_limits_bytes_before_validation() -> None:
    from fastapi import UploadFile
    from io import BytesIO

    upload = UploadFile(
        file=BytesIO(b"\xff\xd8\xff" + b"x" * (MAX_UPLOAD_BYTES - 2)),
        filename="hoja.jpg",
        headers={"content-type": "image/jpeg"},
    )

    with pytest.raises(ImageTooLargeError):
        await read_image_upload(upload)
