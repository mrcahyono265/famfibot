from fastapi.testclient import TestClient

from app.main import app


def test_health() -> None:
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_webhook_rejects_missing_secret() -> None:
    response = TestClient(app).post("/webhooks/telegram", json={"update_id": 1})
    assert response.status_code == 403
