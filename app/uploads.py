from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from fastapi import UploadFile


MAX_UPLOAD_BYTES = 8 * 1024 * 1024
JPEG_MIME_TYPE = "image/jpeg"
PNG_MIME_TYPE = "image/png"
MediaType = Literal["image/jpeg", "image/png"]


class ImageUploadError(ValueError):
    """La imagen subida no se puede aceptar para lectura."""


class ImageTooLargeError(ImageUploadError):
    """La imagen supera el máximo permitido de 8 MB."""


class UnsupportedImageTypeError(ImageUploadError):
    """El archivo no es un JPEG o PNG válido."""


@dataclass(frozen=True)
class ValidatedImage:
    content: bytes
    media_type: MediaType
    filename: str | None = None


def validate_image_upload(
    content: bytes, media_type: str | None, filename: str | None = None
) -> ValidatedImage:
    if len(content) > MAX_UPLOAD_BYTES:
        raise ImageTooLargeError("La foto supera el límite de 8 MB.")

    normalized_type = (media_type or "").lower().split(";", 1)[0].strip()
    signatures = {
        JPEG_MIME_TYPE: b"\xff\xd8\xff",
        PNG_MIME_TYPE: b"\x89PNG\r\n\x1a\n",
    }
    signature = signatures.get(normalized_type)
    if signature is None or not content.startswith(signature):
        raise UnsupportedImageTypeError("Subí una imagen JPEG o PNG válida.")

    return ValidatedImage(
        content=content,
        media_type=normalized_type,  # type: ignore[arg-type]
        filename=filename,
    )


async def read_image_upload(upload: UploadFile) -> ValidatedImage:
    content = await upload.read(MAX_UPLOAD_BYTES + 1)
    return validate_image_upload(content, upload.content_type, upload.filename)
