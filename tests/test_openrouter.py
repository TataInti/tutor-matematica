from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path

import httpx
import pytest
from PIL import Image

from app.openrouter import (
    CHAT_COMPLETIONS_URL,
    OpenRouterClient,
    OpenRouterConfigurationError,
    OpenRouterKeyRejectedError,
    build_text_body,
    build_vision_body,
)


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "vision_ok.json"


def make_jpeg_bytes() -> bytes:
    image = Image.new("RGB", (64, 64), color=(40, 120, 180))
    stream = BytesIO()
    image.save(stream, format="JPEG")
    return stream.getvalue()


def test_text_body_has_no_image_content() -> None:
    body = build_text_body("model-from-test-env", "Explicá la fórmula.")

    assert body["model"] == "model-from-test-env"
    assert body["messages"] == [{"role": "user", "content": "Explicá la fórmula."}]
    assert "image_url" not in json.dumps(body)


def test_vision_body_uses_base64_data_url() -> None:
    body = build_vision_body(
        "vision-model-from-test-env", "Leé el resultado.", b"abc", "image/jpeg"
    )

    content = body["messages"][0]["content"]
    assert content[1] == {
        "type": "image_url",
        "image_url": {"url": "data:image/jpeg;base64,YWJj"},
    }


def test_text_request_uses_environment_model_and_mock_http(monkeypatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "mock-key")
    monkeypatch.setenv("OPENROUTER_TUTOR_MODEL", "text-model-from-test-env")
    monkeypatch.setenv("OPENROUTER_VISION_MODEL", "vision-model-from-test-env")
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["authorization"] = request.headers.get("authorization")
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"choices": [{"message": {"content": "Listo."}}]})

    with OpenRouterClient(transport=httpx.MockTransport(handler)) as client:
        response = client.complete_text("Explicá probabilidad condicional.")

    assert captured["url"] == CHAT_COMPLETIONS_URL
    assert captured["authorization"] == "Bearer mock-key"
    assert captured["body"]["model"] == "text-model-from-test-env"
    assert "image_url" not in json.dumps(captured["body"])
    assert response["choices"][0]["message"]["content"] == "Listo."


def test_vision_request_sends_fixture_content_through_mock_http(monkeypatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "mock-key")
    monkeypatch.setenv("OPENROUTER_VISION_MODEL", "vision-model-from-test-env")
    fixture_text = FIXTURE_PATH.read_text(encoding="utf-8")
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": fixture_text}}]},
        )

    with OpenRouterClient(transport=httpx.MockTransport(handler)) as client:
        response = client.complete_vision(
            "Leé el resultado escrito.", make_jpeg_bytes(), "image/jpeg"
        )

    assert captured["body"]["model"] == "vision-model-from-test-env"
    image_content = captured["body"]["messages"][0]["content"][1]
    assert image_content["image_url"]["url"].startswith("data:image/jpeg;base64,")
    assert json.loads(response["choices"][0]["message"]["content"]) == json.loads(
        fixture_text
    )


def test_401_is_a_key_error_and_not_a_grading_result() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": {"message": "unauthorized"}})

    with OpenRouterClient(
        api_key="mock-key",
        tutor_model="model-from-test-env",
        transport=httpx.MockTransport(handler),
    ) as client:
        with pytest.raises(OpenRouterKeyRejectedError, match="HTTP 401"):
            client.complete_text("No se llama a la red real.")


def test_missing_key_fails_before_mock_transport_is_called(monkeypatch) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setenv("OPENROUTER_TUTOR_MODEL", "text-model-from-test-env")
    requests = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        return httpx.Response(200, json={})

    with OpenRouterClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(OpenRouterConfigurationError, match="OPENROUTER_API_KEY"):
            client.complete_text("No se manda nada.")

    assert requests == 0
