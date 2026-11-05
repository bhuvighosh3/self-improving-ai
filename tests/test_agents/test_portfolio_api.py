from fastapi.testclient import TestClient

from self_improving_ai.dashboard.app import app


def test_api_executes_tool_and_retains_evidence():
    with TestClient(app) as client:
        response = client.post("/api/portfolio/execute", json={"task":"allocation","client_id":"CLI-001"})
        data = response.json()
        assert data["result"]["total_market_value"] == 146750
        assert data["trace"][0]["tool"] == "calculate_allocation_drift"
        assert data["model_tokens"] == 0
        assert client.post("/api/portfolio/execute", json={"task":"projection","num_simulations":-1}).status_code == 422


def test_api_reports_missing_model_configuration(monkeypatch):
    for key in ("SIA_PORTFOLIO_API_KEY", "GOOGLE_API_KEY", "GEMINI_API_KEY", "GOOGLE_GENAI_USE_VERTEXAI"):
        monkeypatch.delenv(key, raising=False)
    with TestClient(app) as client:
        data = client.post("/api/portfolio/agent", json={"message":"Garcia"}).json()
        assert data["result"]["error"]["code"] == "MISSING_MODEL_CONFIGURATION"


def test_api_applies_scenarios_and_rejects_silently_ignored_inputs():
    with TestClient(app) as client:
        result = client.post("/api/portfolio/execute", json={"task":"allocation","client_id":"CLI-002",
            "target_stock_weight":.6}).json()["result"]
        assert result["asset_classes"]["stock"]["hypothetical_adjustment_usd"] == 54820
        for payload in ({"task":"projection","account_id":"ACC-001A"},
                        {"task":"risk","target_amount":100}, {"task":"projection","num_simulations":True},
                        {"task":"projection","years":1.5}, {"task":"allocation","target_stock_weight":True}):
            assert client.post("/api/portfolio/execute",json=payload).status_code == 422
        assert client.post("/api/portfolio/agent",json={"message":"  "}).status_code == 422
