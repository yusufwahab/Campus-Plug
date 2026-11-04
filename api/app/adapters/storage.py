"""File storage adapter. LocalStorage is the TEST implementation (files on disk under uploads/).

Production uses Supabase Storage: public bucket listing-images, private bucket identity-docs with short-lived links.
"""

import secrets
from pathlib import Path
from typing import Protocol

from fastapi import HTTPException

UPLOAD_ROOT = Path(__file__).resolve().parent.parent.parent / "uploads"
MAX_BYTES = 5 * 1024 * 1024

# Magic bytes are checked instead of trusting the client-supplied content type.
_SIGNATURES = {b"\xff\xd8\xff": ("jpg", "image/jpeg"), b"\x89PNG\r\n\x1a\n": ("png", "image/png")}


def sniff_image(data: bytes) -> tuple[str, str]:
    for magic, kind in _SIGNATURES.items():
        if data.startswith(magic):
            return kind
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp", "image/webp"
    raise HTTPException(422, "Upload a JPEG, PNG or WebP image.")


class Storage(Protocol):
    def save_public(self, data: bytes, ext: str) -> str: ...
    def save_private(self, data: bytes, ext: str) -> str: ...
    def read_private(self, path: str) -> bytes: ...


class LocalStorage:
    """TEST ADAPTER: stores files on local disk. Public files are served from /uploads."""

    def __init__(self, root: Path = UPLOAD_ROOT) -> None:
        self.root = root

    def _write(self, folder: str, data: bytes, ext: str) -> str:
        target = self.root / folder
        target.mkdir(parents=True, exist_ok=True)
        name = f"{secrets.token_urlsafe(16)}.{ext}"
        (target / name).write_bytes(data)
        return f"{folder}/{name}"

    def save_public(self, data: bytes, ext: str) -> str:
        return self._write("public", data, ext)

    def save_private(self, data: bytes, ext: str) -> str:
        return self._write("private", data, ext)

    def read_private(self, path: str) -> bytes:
        resolved = (self.root / path).resolve()
        if not str(resolved).startswith(str((self.root / "private").resolve())):
            raise HTTPException(404, "File not found")
        return resolved.read_bytes()


def get_storage() -> Storage:
    # SupabaseStorage is selected here once SUPABASE_URL and the service key exist (docs/OWNER_ACTIONS.md).
    return LocalStorage()


def public_url(path: str) -> str:
    return f"/uploads/{path.removeprefix('public/')}" if path.startswith("public/") else path
