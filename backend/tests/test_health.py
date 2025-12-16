from __future__ import annotations

from httpx import AsyncClient


async def test_health_and_ready(client: AsyncClient) -> None:
    r1 = await client.get("/health")
    assert r1.status_code == 200
    assert r1.json()["status"] == "ok"

    r2 = await client.get("/ready")
    assert r2.status_code == 200
    assert r2.json()["status"] == "ready"

    r3 = await client.get("/api/v1/health")
    assert r3.status_code == 200
    assert r3.json()["status"] == "ok"

    r4 = await client.get("/api/v1/ready")
    assert r4.status_code == 200
    assert r4.json()["status"] == "ready"
