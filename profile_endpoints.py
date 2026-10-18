import time
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.auth import ensure_system_user, _issue_token

client = TestClient(app)
user = ensure_system_user()
token = _issue_token(user)
auth_headers = {"Authorization": f"Bearer {token}"}

print("=== FASTAPI ENDPOINT LATENCY PROFILING ===")

endpoints = [
    ("GET", "/api/v1/health", {}),
    ("GET", "/api/v1/ready", {}),
    ("GET", "/api/v1/rag/status", {}),
    ("GET", "/api/v1/documents", {"headers": auth_headers}),
    ("POST", "/api/v1/agent/ask", {"headers": auth_headers, "json": {"question": "What were total sales from 2026-09-01 to 2026-09-30?"}}),
    ("POST", "/api/v1/chat/ask", {"headers": auth_headers, "json": {"question": "What is the annual leave policy?"}}),
]

for method, path, extra in endpoints:
    latencies = []
    headers = extra.get("headers", {})
    json_body = extra.get("json")
    for i in range(3):
        t0 = time.perf_counter()
        if method == "GET":
            resp = client.get(path, headers=headers)
        else:
            resp = client.post(path, json=json_body, headers=headers)
        dt = (time.perf_counter() - t0) * 1000
        latencies.append(dt)
    
    print(f"{method} {path:22s} -> Status: {resp.status_code} | Latencies: min={min(latencies):.2f}ms, avg={sum(latencies)/len(latencies):.2f}ms, max={max(latencies):.2f}ms")
