import pytest_asyncio
from httpx import AsyncClient

from app.main import app


@pytest_asyncio.fixture(scope="session")
async def client():
    async with AsyncClient(app=app, base_url="http://localhost:8000") as ac:
        yield ac


@pytest_asyncio.fixture(scope="session")
async def auth_client(client):
    response = await client.post(
        "/auth/token", data={"username": "user", "password": "user"}
    )
    token = response.json()["access_token"]

    async with AsyncClient(
        app=app,
        base_url="http://localhost:8000",
        headers={"Authorization": f"Bearer {token}"},
    ) as ac:
        yield ac


@pytest_asyncio.fixture(scope="session")
async def archive(auth_client):
    response = await auth_client.post(
        "/archive",
        data={
            "url": "http://download.ispsystem.com/OSTemplate/new/latest/Debian-7-i386-5.57-20170910000.tar.gz"
        },
    )
    assert response.status_code == 200
    assert response.json().get("id")
    yield response.json().get("id")
