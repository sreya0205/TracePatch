from fastapi.testclient import TestClient
from incidentpilot.api.main import app

client = TestClient(app)


def test_api_health():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "active_sandbox_backend" in data


def test_api_sandbox_execute():
    payload = {
        "script_content": "print('Test Sandbox execution'); exit(0)",
        "timeout_seconds": 5,
    }
    response = client.post("/api/v1/sandbox/execute", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["exit_code"] == 0
    assert "Test Sandbox execution" in data["stdout"]


def test_api_incident_analyze():
    payload = {
        "incident_id": "INC-TEST-API",
        "raw_logs": (
            "Traceback (most recent call last):\n"
            "  File \"api/handlers/checkout.py\", line 67, in process\n"
            "    customer_id = body['customer_id']\n"
            "KeyError: 'customer_id'"
        ),
        "repo_path": ".",
    }
    response = client.post("/api/v1/incidents/analyze", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["incident_id"] == "INC-TEST-API"
    assert data["triage"]["error_type"] == "KeyError"
    assert data["final_report"]["reproduction_verified"] is True
    assert "checkout.py" in data["final_report"]["culprit_file"]
