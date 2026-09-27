"""Quick smoke-test for POST /analysis."""

import httpx
import json
import sys

BASE = "http://localhost:8000"

query = sys.argv[1] if len(sys.argv) > 1 else "How many shots did Argentina take?"
match_id = int(sys.argv[2]) if len(sys.argv) > 2 else 38

payload = {"query": query, "match_id": match_id}

print(f"POST {BASE}/analysis")
print(f"Body: {json.dumps(payload, indent=2)}")
print("---")

resp = httpx.post(f"{BASE}/analysis", json=payload, timeout=120)
print(f"Status: {resp.status_code}")
print(json.dumps(resp.json(), indent=2))
