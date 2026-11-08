"""The deployed API's access key: off locally, enforced on every /api call but the health check when set."""
from fastapi.testclient import TestClient

from pubhedge_svc.app import app

c = TestClient(app)


def test_no_key_set_means_open(monkeypatch):
    monkeypatch.delenv("PUBHEDGE_ACCESS_KEY", raising=False)
    assert c.get("/api/limits").status_code == 200


def test_key_set_guards_the_api(monkeypatch):
    monkeypatch.setenv("PUBHEDGE_ACCESS_KEY", "s3cret-demo-key")
    assert c.get("/api/health").status_code == 200  # the platform's health probe needs no key
    assert c.get("/api/limits").status_code == 401
    assert c.get("/api/limits", headers={"x-pubhedge-key": "wrong"}).status_code == 401
    assert c.get("/api/limits", headers={"x-pubhedge-key": "s3cret-demo-key"}).status_code == 200
    assert c.get("/api/limits?key=s3cret-demo-key").status_code == 200  # how EventSource sends it
    assert c.options("/api/limits", headers={"Origin": "http://localhost:3000",
                                              "Access-Control-Request-Method": "GET"}).status_code == 200
