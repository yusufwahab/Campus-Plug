"""File storage adapter. LocalStorage is the TEST implementation (files on disk under uploads/).

Production uses Cloudinary (STORAGE_PROVIDER=cloudinary): listing and chat photos are public assets; identity documents
and dispute evidence are stored as private assets that are never reachable by URL, only through our API with a short-lived link.
"""

import hashlib
import logging
import re
import secrets
import time
from pathlib import Path
from typing import Any, Protocol

import httpx
from fastapi import HTTPException

from app.config import get_settings

logger = logging.getLogger("campusplug.storage")

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
    def delete_public(self, path: str) -> None: ...


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

    def delete_public(self, path: str) -> None:
        resolved = (self.root / path).resolve()
        if str(resolved).startswith(str((self.root / "public").resolve())):
            resolved.unlink(missing_ok=True)


class CloudinaryStorage:
    """Real storage through Cloudinary's upload API (https://cloudinary.com/documentation/image_upload_api_reference).

    Mock-tested only: it has never talked to a real Cloudinary account (docs/OWNER_ACTIONS.md).
    Public photos keep their delivery URL in the database. Private files are stored as type "private", and the database
    keeps `cld-private/<id>.<ext>`; they are fetched with a signed, short-lived download request made by the server.
    """

    API = "https://api.cloudinary.com/v1_1"
    TIMEOUT = 25.0

    def __init__(self, cloud_name: str, api_key: str, api_secret: str) -> None:
        self.cloud, self.key, self.secret = cloud_name, api_key, api_secret

    def _sign(self, params: dict[str, Any]) -> str:
        # Cloudinary signs the sorted "key=value" pairs joined with "&", with the API secret appended, using SHA-1.
        to_sign = "&".join(f"{k}={params[k]}" for k in sorted(params) if params[k] not in (None, ""))
        return hashlib.sha1((to_sign + self.secret).encode()).hexdigest()  # noqa: S324 (the algorithm Cloudinary requires)

    def _upload(self, data: bytes, ext: str, *, kind: str) -> dict[str, Any]:
        public_id = f"campusplug/{kind}/{secrets.token_urlsafe(16)}"
        params: dict[str, Any] = {
            "public_id": public_id,
            "timestamp": int(time.time()),
            "type": "upload" if kind == "public" else "private",
        }
        form = {**params, "api_key": self.key, "signature": self._sign(params)}
        try:
            res = httpx.post(
                f"{self.API}/{self.cloud}/image/upload", data=form, files={"file": (f"upload.{ext}", data)}, timeout=self.TIMEOUT
            )
        except httpx.HTTPError:
            logger.error("cloudinary upload failed: network error")
            raise HTTPException(502, "We could not store that image. Please try again.") from None
        if res.status_code >= 300:
            logger.error("cloudinary upload failed: status=%s", res.status_code)
            raise HTTPException(502, "We could not store that image. Please try again.")
        return res.json()  # type: ignore[no-any-return]

    def save_public(self, data: bytes, ext: str) -> str:
        return str(self._upload(data, ext, kind="public")["secure_url"])

    def save_private(self, data: bytes, ext: str) -> str:
        stored = self._upload(data, ext, kind="private")
        return f"cld-private/{stored['public_id'].rsplit('/', 1)[-1]}.{stored.get('format') or ext}"

    def read_private(self, path: str) -> bytes:
        match = re.fullmatch(r"cld-private/([A-Za-z0-9_-]{8,64})\.(jpg|png|webp)", path)
        if match is None:
            raise HTTPException(404, "File not found")
        name, fmt = match.groups()
        params: dict[str, Any] = {
            "public_id": f"campusplug/private/{name}",
            "format": fmt,
            "type": "private",
            "timestamp": int(time.time()),
        }
        query = {**params, "api_key": self.key, "signature": self._sign(params)}
        try:
            res = httpx.get(f"{self.API}/{self.cloud}/image/download", params=query, timeout=self.TIMEOUT)
        except httpx.HTTPError:
            raise HTTPException(502, "We could not load that file. Please try again.") from None
        if res.status_code == 404:
            raise HTTPException(404, "File not found")
        if res.status_code >= 300:
            logger.error("cloudinary download failed: status=%s", res.status_code)
            raise HTTPException(502, "We could not load that file. Please try again.")
        return res.content

    def delete_public(self, path: str) -> None:
        marker = "/image/upload/"
        if not path.startswith("https://res.cloudinary.com/") or marker not in path:
            return
        parts = [p for p in path.split(marker, 1)[1].split("/") if not (p.startswith("v") and p[1:].isdigit())]  # drop the version
        public_id = "/".join(parts).rsplit(".", 1)[0]
        params = {"public_id": public_id, "timestamp": int(time.time()), "type": "upload"}
        form = {**params, "api_key": self.key, "signature": self._sign(params)}
        try:
            httpx.post(f"{self.API}/{self.cloud}/image/destroy", data=form, timeout=self.TIMEOUT)
        except httpx.HTTPError:
            logger.error("cloudinary delete failed: network error")  # best effort: the database row is already gone


def get_storage() -> Storage:
    s = get_settings()
    if s.storage_provider == "cloudinary" and s.cloudinary_cloud_name and s.cloudinary_api_key and s.cloudinary_api_secret:
        return CloudinaryStorage(s.cloudinary_cloud_name, s.cloudinary_api_key, s.cloudinary_api_secret)
    return LocalStorage()


def public_url(path: str) -> str:
    if path.startswith("https://res.cloudinary.com/") and "/image/upload/" in path:
        # Let Cloudinary pick the best format and quality for each browser.
        return path.replace("/image/upload/", "/image/upload/f_auto,q_auto/", 1)
    return f"/uploads/{path.removeprefix('public/')}" if path.startswith("public/") else path
