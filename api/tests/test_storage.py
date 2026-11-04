import hashlib

import httpx
import pytest
from fastapi import HTTPException

from app.adapters import storage as storage_module
from app.adapters.storage import CloudinaryStorage, LocalStorage, get_storage, public_url

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


def sign(params: dict, secret: str) -> str:
    """The signing rule from Cloudinary's docs: sorted key=value pairs joined by &, secret appended, SHA-1."""
    return hashlib.sha1(("&".join(f"{k}={params[k]}" for k in sorted(params)) + secret).encode()).hexdigest()  # noqa: S324 (the algorithm Cloudinary requires)


@pytest.fixture()
def cloud():
    return CloudinaryStorage("democloud", "key123", "s3cret")


def test_public_upload_is_signed_and_returns_the_delivery_url(cloud, monkeypatch):
    seen = {}

    def fake_post(url, data, files, timeout):
        seen.update(url=url, data=data, files=files)
        return httpx.Response(200, json={"secure_url": "https://res.cloudinary.com/democloud/image/upload/v17/campusplug/public/abc.png"})

    monkeypatch.setattr(storage_module.httpx, "post", fake_post)
    url = cloud.save_public(PNG, "png")
    assert url == "https://res.cloudinary.com/democloud/image/upload/v17/campusplug/public/abc.png"
    assert seen["url"] == "https://api.cloudinary.com/v1_1/democloud/image/upload"
    data = seen["data"]
    assert data["api_key"] == "key123" and data["type"] == "upload" and data["public_id"].startswith("campusplug/public/")
    signed = {k: data[k] for k in ("public_id", "timestamp", "type")}
    assert data["signature"] == sign(signed, "s3cret")
    assert "s3cret" not in str(data)  # the secret itself is never sent
    assert seen["files"]["file"][1] == PNG


def test_private_upload_is_never_a_public_asset_and_is_read_back_with_a_signed_request(cloud, monkeypatch):
    calls = {}

    def fake_post(url, data, files, timeout):
        calls["upload"] = data
        return httpx.Response(
            200, json={"public_id": f"{data['public_id']}", "format": "png", "secure_url": "https://example.invalid/not-used"}
        )

    def fake_get(url, params, timeout):
        calls["download"] = (url, params)
        return httpx.Response(200, content=PNG)

    monkeypatch.setattr(storage_module.httpx, "post", fake_post)
    monkeypatch.setattr(storage_module.httpx, "get", fake_get)
    path = cloud.save_private(PNG, "png")
    assert calls["upload"]["type"] == "private"
    assert path.startswith("cld-private/") and path.endswith(".png") and "http" not in path
    assert cloud.read_private(path) == PNG
    url, params = calls["download"]
    assert url == "https://api.cloudinary.com/v1_1/democloud/image/download"
    assert params["type"] == "private" and params["format"] == "png" and params["public_id"].startswith("campusplug/private/")
    signed = {k: params[k] for k in ("format", "public_id", "timestamp", "type")}
    assert params["signature"] == sign(signed, "s3cret")


def test_private_reads_refuse_paths_that_are_not_ours(cloud, monkeypatch):
    monkeypatch.setattr(storage_module.httpx, "get", lambda *a, **k: pytest.fail("no request should be made"))
    for bad in (
        "public/abc.png",
        "https://evil.example/x.png",
        "cld-private/../../x.png",
        "cld-private/abc.png",
        "cld-private/abcdefgh.exe",
    ):
        with pytest.raises(HTTPException) as e:
            cloud.read_private(bad)
        assert e.value.status_code == 404


def test_upload_failures_become_a_friendly_502_and_log_no_secrets(cloud, monkeypatch, caplog):
    monkeypatch.setattr(
        storage_module.httpx, "post", lambda *a, **k: httpx.Response(401, json={"error": {"message": "Invalid api_key key123"}})
    )
    with caplog.at_level("ERROR", logger="campusplug.storage"), pytest.raises(HTTPException) as e:
        cloud.save_public(PNG, "png")
    assert e.value.status_code == 502 and "try again" in e.value.detail
    assert "s3cret" not in caplog.text and "key123" not in caplog.text

    def boom(*a, **k):
        raise httpx.ConnectError("down")

    monkeypatch.setattr(storage_module.httpx, "post", boom)
    with pytest.raises(HTTPException) as e:
        cloud.save_private(PNG, "png")
    assert e.value.status_code == 502


def test_deleting_a_public_photo_destroys_the_right_asset_and_ignores_local_paths(cloud, monkeypatch):
    seen = []
    monkeypatch.setattr(storage_module.httpx, "post", lambda url, data, timeout: seen.append((url, data)) or httpx.Response(200, json={}))
    cloud.delete_public("https://res.cloudinary.com/democloud/image/upload/v17/campusplug/public/abc.png")
    cloud.delete_public("public/local-file.png")
    assert len(seen) == 1
    url, data = seen[0]
    assert url.endswith("/image/destroy") and data["public_id"] == "campusplug/public/abc" and data["type"] == "upload"


def test_public_urls_get_automatic_format_and_quality():
    cld = "https://res.cloudinary.com/democloud/image/upload/v17/campusplug/public/abc.png"
    assert public_url(cld) == "https://res.cloudinary.com/democloud/image/upload/f_auto,q_auto/v17/campusplug/public/abc.png"
    assert public_url("public/x.png") == "/uploads/x.png"


def test_storage_provider_comes_from_settings(monkeypatch):
    from app.config import get_settings

    assert isinstance(get_storage(), LocalStorage)
    for key, value in {
        "STORAGE_PROVIDER": "cloudinary",
        "CLOUDINARY_CLOUD_NAME": "c",
        "CLOUDINARY_API_KEY": "k",
        "CLOUDINARY_API_SECRET": "s",
    }.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()
    try:
        assert isinstance(get_storage(), CloudinaryStorage)
    finally:
        monkeypatch.undo()
        get_settings.cache_clear()


def test_local_delete_only_touches_public_files(tmp_path):
    local = LocalStorage(tmp_path)
    path = local.save_public(PNG, "png")
    secret = local.save_private(PNG, "png")
    local.delete_public(secret)  # private files are never removed this way
    assert (tmp_path / secret).exists()
    local.delete_public(path)
    assert not (tmp_path / path).exists()
