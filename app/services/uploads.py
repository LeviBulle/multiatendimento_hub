from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

ALLOWED_UPLOADS = {
    ".jpg": {"image/jpeg"},
    ".jpeg": {"image/jpeg"},
    ".png": {"image/png"},
    ".webp": {"image/webp"},
    ".pdf": {"application/pdf"},
    ".webm": {"audio/webm", "video/webm"},
    ".mp3": {"audio/mpeg", "audio/mp3"},
    ".ogg": {"audio/ogg", "application/ogg"},
}


@dataclass
class StoredUpload:
    original_name: str
    stored_name: str
    mime_type: str
    size_bytes: int


def validate_and_store_upload(upload: UploadFile, max_size_mb: int, upload_dir: Path) -> StoredUpload:
    original_name = Path(upload.filename or "").name
    suffix = Path(original_name).suffix.lower()
    mime_type = upload.content_type or "application/octet-stream"
    if suffix not in ALLOWED_UPLOADS or mime_type not in ALLOWED_UPLOADS[suffix]:
        raise ValueError("Tipo de arquivo nao permitido. Envie JPEG, PNG, WEBP, PDF, WEBM, MP3 ou OGG.")

    max_bytes = max_size_mb * 1024 * 1024
    stored_name = f"{uuid4().hex}{suffix}"
    upload_dir.mkdir(parents=True, exist_ok=True)
    stored_path = upload_dir / stored_name
    size = 0
    with stored_path.open("wb") as output:
        while True:
            chunk = upload.file.read(1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            if size > max_bytes:
                output.close()
                stored_path.unlink(missing_ok=True)
                raise ValueError(f"Arquivo maior que o limite de {max_size_mb} MB.")
            output.write(chunk)

    return StoredUpload(
        original_name=original_name,
        stored_name=stored_name,
        mime_type=mime_type,
        size_bytes=size,
    )
