from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from typing import Literal

from fastapi import UploadFile
from PIL import Image, ImageOps, UnidentifiedImageError


MAX_UPLOAD_BYTES = 8 * 1024 * 1024
MAX_IMAGE_SIDE = 1600
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
    # El tamaño se verifica antes de decodificar o redimensionar la imagen.
    if len(content) > MAX_UPLOAD_BYTES:
        raise ImageTooLargeError("La foto supera el límite de 8 MB.")

    normalized_type = (media_type or "").lower().split(";", 1)[0].strip()
    signatures = {
        JPEG_MIME_TYPE: (b"\xff\xd8\xff", "JPEG"),
        PNG_MIME_TYPE: (b"\x89PNG\r\n\x1a\n", "PNG"),
    }
    signature_and_format = signatures.get(normalized_type)
    if signature_and_format is None:
        raise UnsupportedImageTypeError("Subí una imagen JPEG o PNG válida.")
    signature, expected_format = signature_and_format
    if not content.startswith(signature):
        raise UnsupportedImageTypeError("Subí una imagen JPEG o PNG válida.")

    try:
        with Image.open(BytesIO(content)) as original:
            if original.format != expected_format:
                raise UnsupportedImageTypeError(
                    "El contenido no coincide con el formato declarado."
                )
            original.load()
            if max(original.size) <= MAX_IMAGE_SIDE:
                return ValidatedImage(
                    content=content,
                    media_type=normalized_type,  # type: ignore[arg-type]
                    filename=filename,
                )

            image = ImageOps.exif_transpose(original)
            image.thumbnail(
                (MAX_IMAGE_SIDE, MAX_IMAGE_SIDE),
                Image.Resampling.LANCZOS,
            )
            output = BytesIO()
            if expected_format == "JPEG":
                if image.mode not in {"RGB", "L"}:
                    image = image.convert("RGB")
                image.save(output, format="JPEG", quality=90, optimize=True)
            else:
                image.save(output, format="PNG", optimize=True)
    except UnsupportedImageTypeError:
        raise
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as exc:
        raise UnsupportedImageTypeError("Subí una imagen JPEG o PNG válida.") from exc

    return ValidatedImage(
        content=output.getvalue(),
        media_type=normalized_type,  # type: ignore[arg-type]
        filename=filename,
    )


async def read_image_upload(upload: UploadFile) -> ValidatedImage:
    content = await upload.read(MAX_UPLOAD_BYTES + 1)
    return validate_image_upload(content, upload.content_type, upload.filename)
