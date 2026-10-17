from __future__ import annotations

import base64
import os
from typing import Any

import httpx

from app.uploads import validate_image_upload


CHAT_COMPLETIONS_URL = "https://openrouter.ai/api/v1/chat/completions"


class OpenRouterError(RuntimeError):
    """Base para errores del cliente de OpenRouter."""


class OpenRouterConfigurationError(OpenRouterError):
    """Falta una variable de entorno necesaria para la llamada."""


class OpenRouterKeyRejectedError(OpenRouterError):
    """OpenRouter rechazó la clave (HTTP 401)."""


class OpenRouterAPIError(OpenRouterError):
    """OpenRouter respondió con un estado HTTP de error."""


class OpenRouterRequestError(OpenRouterError):
    """No se pudo completar la solicitud HTTP."""


class OpenRouterResponseError(OpenRouterError):
    """La respuesta de OpenRouter no contiene un objeto JSON válido."""


def build_text_body(
    model: str, prompt: str, system_prompt: str | None = None
) -> dict[str, Any]:
    messages: list[dict[str, Any]] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})
    return {"model": model, "messages": messages}


def build_vision_body(
    model: str,
    prompt: str,
    image_bytes: bytes,
    media_type: str,
    system_prompt: str | None = None,
) -> dict[str, Any]:
    normalized_type = media_type.lower().split(";", 1)[0].strip()
    if normalized_type not in {"image/jpeg", "image/png"}:
        raise ValueError("La visión acepta solamente imágenes JPEG o PNG.")

    image_url = (
        f"data:{normalized_type};base64,"
        f"{base64.b64encode(image_bytes).decode('ascii')}"
    )
    messages: list[dict[str, Any]] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append(
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": image_url}},
            ],
        }
    )
    return {"model": model, "messages": messages}


class OpenRouterClient:
    """Cliente HTTP testeable; por defecto lee los tres valores del entorno."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        tutor_model: str | None = None,
        vision_model: str | None = None,
        transport: httpx.BaseTransport | None = None,
        timeout: float = 45.0,
    ) -> None:
        self._api_key = (
            api_key if api_key is not None else os.getenv("OPENROUTER_API_KEY", "")
        )
        self._tutor_model = (
            tutor_model
            if tutor_model is not None
            else os.getenv("OPENROUTER_TUTOR_MODEL", "")
        )
        self._vision_model = (
            vision_model
            if vision_model is not None
            else os.getenv("OPENROUTER_VISION_MODEL", "")
        )
        self._http = httpx.Client(transport=transport, timeout=timeout)

    def __enter__(self) -> OpenRouterClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def close(self) -> None:
        self._http.close()

    def complete_text(
        self, prompt: str, system_prompt: str | None = None
    ) -> dict[str, Any]:
        model = self._required_model(self._tutor_model, "OPENROUTER_TUTOR_MODEL")
        body = build_text_body(model, prompt, system_prompt)
        return self._post(body)

    def complete_vision(
        self,
        prompt: str,
        image_bytes: bytes,
        media_type: str,
        system_prompt: str | None = None,
        filename: str | None = None,
    ) -> dict[str, Any]:
        image = validate_image_upload(image_bytes, media_type, filename)
        model = self._required_model(self._vision_model, "OPENROUTER_VISION_MODEL")
        body = build_vision_body(
            model, prompt, image.content, image.media_type, system_prompt
        )
        return self._post(body)

    def _required_model(self, model: str, variable_name: str) -> str:
        if not self._api_key or not self._api_key.strip():
            raise OpenRouterConfigurationError(
                "Falta configurar OPENROUTER_API_KEY."
            )
        if not model or not model.strip():
            raise OpenRouterConfigurationError(
                f"Falta configurar {variable_name}."
            )
        return model.strip()

    def _post(self, body: dict[str, Any]) -> dict[str, Any]:
        try:
            response = self._http.post(
                CHAT_COMPLETIONS_URL,
                json=body,
                headers={"Authorization": f"Bearer {self._api_key}"},
            )
        except httpx.RequestError as exc:
            raise OpenRouterRequestError(
                "No se pudo completar la solicitud a OpenRouter."
            ) from exc

        if response.status_code == 401:
            raise OpenRouterKeyRejectedError(
                "OpenRouter rechazó la clave (HTTP 401)."
            )
        if response.is_error:
            raise OpenRouterAPIError(
                f"OpenRouter respondió con HTTP {response.status_code}."
            )
        try:
            result = response.json()
        except ValueError as exc:
            raise OpenRouterResponseError(
                "OpenRouter devolvió una respuesta que no es JSON válido."
            ) from exc
        if not isinstance(result, dict):
            raise OpenRouterResponseError(
                "La respuesta de OpenRouter no es un objeto JSON."
            )
        return result
