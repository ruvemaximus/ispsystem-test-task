import pytest


@pytest.mark.asyncio
async def test_downloaded_archive_from_valid_url(auth_client, archive):
    response = await auth_client.get(f"/archive/{archive}/")
    assert response.status_code == 200
    archive_info = response.json()
    assert archive_info.get("status") == "ok"
    assert archive_info.get("author") == {"username": "user"}
    assert archive_info.get("files")


@pytest.mark.asyncio
async def test_delete_archive(auth_client, archive):
    response = await auth_client.delete(f"/archive/{archive}/")
    assert response.status_code == 200
    data = response.json()
    assert data.get("ok") is True
    assert data.get("message")


@pytest.mark.asyncio
async def test_archive_deleted(auth_client, archive):
    response = await auth_client.get(f"/archive/{archive}/")
    assert response.status_code == 404
    assert response.json().get("detail")
