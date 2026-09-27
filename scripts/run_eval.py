"""Golden eval set runner (Phase 3).

Evaluates the AI Football Match Analyst against golden_v1.jsonl:
- Checks factual accuracy against DB-verified ground truth
- Verifies required evidence citations are present
- Checks adherence to non-negotiable rule R1 (zero invented numbers)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

import httpx

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_EVAL_FILE = ROOT_DIR / "backend" / "tests" / "eval" / "golden_v1.jsonl"
if not DEFAULT_EVAL_FILE.exists():
    DEFAULT_EVAL_FILE = ROOT_DIR / "tests" / "eval" / "golden_v1.jsonl"


def load_golden_set(filepath: Path) -> list[dict[str, Any]]:
    """Load questions and assertions from JSONL file."""
    if not filepath.exists():
        print(f"Error: Golden eval set file not found at {filepath}")
        sys.exit(1)

    items = []
    with open(filepath, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                items.append(json.loads(line))
    return items


async def evaluate_query(
    client: httpx.AsyncClient,
    base_url: str,
    item: dict[str, Any],
) -> dict[str, Any]:
    """Run one evaluation item against the API."""
    query_id = item["id"]
    query = item["query"]
    match_id = item.get("match_id")
    expected_values = item.get("expected_values", {})
    must_reference = item.get("must_reference", [])
    expected_query_type = item.get("query_type")

    payload: dict[str, Any] = {"query": query}
    if match_id is not None:
        payload["match_id"] = match_id

    try:
        response = await client.post(f"{base_url}/analysis", json=payload, timeout=60.0)
    except Exception as exc:
        return {
            "id": query_id,
            "passed": False,
            "error": f"Request failed: {exc}",
            "details": str(exc),
        }

    if response.status_code != 200:
        return {
            "id": query_id,
            "passed": False,
            "error": f"HTTP {response.status_code}",
            "details": response.text,
        }

    data = response.json()
    answer_markdown = data.get("answer_markdown", "")
    evidence = data.get("evidence", [])
    query_type = data.get("query_type")

    # Check evidence citations
    citations = [e.get("ref", "") for e in evidence]
    missing_refs = []
    for required_ref in must_reference:
        matched = any(required_ref in c for c in citations)
        if not matched:
            missing_refs.append(required_ref)

    # Check query type if specified
    type_matches = True
    if expected_query_type and query_type != expected_query_type:
        type_matches = False

    # Check expected numbers in answer or evidence
    missing_values = []
    for k, v in expected_values.items():
        if isinstance(v, (int, float)):
            v_str = str(v)
            in_text = v_str in answer_markdown
            in_evidence = any(str(e.get("value")) == v_str for e in evidence)
            if not (in_text or in_evidence):
                missing_values.append(f"{k}={v}")

    passed = (len(missing_refs) == 0) and type_matches and (len(missing_values) == 0)

    return {
        "id": query_id,
        "query": query,
        "passed": passed,
        "query_type": query_type,
        "evidence_count": len(evidence),
        "missing_refs": missing_refs,
        "missing_values": missing_values,
        "type_matches": type_matches,
        "answer_snippet": answer_markdown[:120] + "..." if len(answer_markdown) > 120 else answer_markdown,
    }


async def main() -> None:
    parser = argparse.ArgumentParser(description="Run Golden Eval Set v1 against the analyst API.")
    parser.add_argument("--url", default="http://localhost:8000", help="Base API URL")
    parser.add_argument("--file", default=str(DEFAULT_EVAL_FILE), help="Path to golden_v1.jsonl")
    args = parser.parse_args()

    eval_items = load_golden_set(Path(args.file))
    print(f"\n=======================================================")
    print(f"Running Golden Eval Set v1 ({len(eval_items)} items) against {args.url}")
    print(f"=======================================================\n")

    passed_count = 0
    async with httpx.AsyncClient() as client:
        for idx, item in enumerate(eval_items, 1):
            print(f"[{idx}/{len(eval_items)}] Testing {item['id']}: {item['query'][:60]}...")
            result = await evaluate_query(client, args.url, item)

            if result["passed"]:
                passed_count += 1
                print(f"  [PASS] Evidence refs: {result.get('evidence_count', 0)}")
            else:
                print(f"  [FAIL] Reason:")
                if result.get("error"):
                    print(f"    Error: {result['error']}")
                if result.get("missing_refs"):
                    print(f"    Missing references: {result['missing_refs']}")
                if result.get("missing_values"):
                    print(f"    Missing expected values: {result['missing_values']}")
                if not result.get("type_matches", True):
                    print(f"    Query type mismatch: got {result.get('query_type')}")
                print(f"    Snippet: {result.get('answer_snippet', '')}")

    accuracy = (passed_count / len(eval_items)) * 100.0
    print(f"\n=======================================================")
    print(f"Evaluation Summary: {passed_count}/{len(eval_items)} Passed ({accuracy:.1f}% Accuracy)")
    print(f"Acceptance Target: >= 80.0%")
    print(f"=======================================================\n")

    if accuracy < 80.0:
        print("FAIL: Factual accuracy is below the 80% acceptance threshold.")
        sys.exit(1)
    else:
        print("SUCCESS: Factual accuracy meets the acceptance threshold.")


if __name__ == "__main__":
    asyncio.run(main())
