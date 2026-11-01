"""Strict, dependency-free loading and validation of SlaveBench research records."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class DataError(ValueError):
    pass


def read_json(path: str | Path) -> Any:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    rows = []
    with open(path, encoding="utf-8") as f:
        for line_number, line in enumerate(f, 1):
            if line.strip():
                try:
                    row = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise DataError(f"{path}:{line_number}: {exc}") from exc
                if not isinstance(row, dict):
                    raise DataError(f"{path}:{line_number}: expected an object")
                rows.append(row)
    return rows


def write_jsonl(path: str | Path, rows: list[dict[str, Any]]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def load_cases(path: str | Path) -> dict[str, dict[str, Any]]:
    suite = read_json(path)
    if not isinstance(suite, dict) or not isinstance(suite.get("cases"), list):
        raise DataError("Prompt suite must have a cases list")
    rubric = read_json(Path(path).parent / "rubric.json")
    dimensions = set(rubric["dimensions"])
    result = {}
    for case in suite["cases"]:
        if not isinstance(case, dict):
            raise DataError("Prompt case must be an object")
        cid = case.get("id")
        if not isinstance(cid, str) or not cid.startswith("SB-") or cid in result:
            raise DataError(f"Bad or duplicate case id: {cid!r}")
        if not isinstance(case.get("prompt"), str) or len(case["prompt"]) < 15:
            raise DataError(f"{cid}: missing substantive prompt")
        dims = case.get("dimensions")
        if not isinstance(dims, list) or not dims or not all(x in dimensions for x in dims):
            raise DataError(f"{cid}: unknown or empty rubric dimensions")
        if len(set(dims)) != len(dims):
            raise DataError(f"{cid}: duplicate dimension")
        result[cid] = case
    return result


def validate_responses(rows: list[dict[str, Any]], cases: dict[str, dict[str, Any]]) -> None:
    seen = set()
    for r in rows:
        required = {"response_id", "case_id", "model_id", "response", "source", "condition"}
        if not required.issubset(r):
            raise DataError(f"Response missing keys {sorted(required-set(r))}: {r.get('response_id')}")
        rid = r["response_id"]
        if not isinstance(rid, str) or not rid or rid in seen:
            raise DataError(f"Bad or duplicate response id: {rid!r}")
        seen.add(rid)
        if r["case_id"] not in cases:
            raise DataError(f"{rid}: unknown case {r['case_id']!r}")
        for field in ["model_id", "response", "source", "condition"]:
            if not isinstance(r[field], str) or not r[field].strip():
                raise DataError(f"{rid}: empty or invalid {field}")


def validate_annotations(
    rows: list[dict[str, Any]],
    packet: dict[str, dict[str, Any]],
    cases: dict[str, dict[str, Any]],
    *,
    require_complete: bool = True,
) -> None:
    seen = set()
    for r in rows:
        if not all(x in r for x in ("blind_id", "rater_id", "scores", "evidence", "notes")):
            raise DataError("Annotation must include blind_id, rater_id, scores, evidence, notes")
        bid = r["blind_id"]
        key = (bid, r["rater_id"])
        if key in seen:
            raise DataError(f"Duplicate annotation {key}")
        seen.add(key)
        if bid not in packet:
            raise DataError(f"Unrecognized blind_id {bid}")
        if not isinstance(r["rater_id"], str) or not r["rater_id"].strip():
            raise DataError("Blank rater_id")
        cid = packet[bid]["case_id"]
        expected = set(cases[cid]["dimensions"])
        scores = r["scores"]
        if not isinstance(scores, dict) or (set(scores) != expected if require_complete else not set(scores).issubset(expected)):
            raise DataError(f"{bid}: scores must match applicable dimensions {expected}")
        for dimension, value in scores.items():
            if type(value) is not int or value not in (0, 1, 2):
                raise DataError(f"{bid}.{dimension}: score must be integer 0, 1, or 2")
        evidence = r["evidence"]
        if not isinstance(evidence, dict) or not set(evidence).issubset(expected):
            raise DataError(f"{bid}: evidence must be an object keyed by applicable dimensions")
        for dimension, spans in evidence.items():
            if not isinstance(spans, list) or not all(isinstance(span, str) for span in spans):
                raise DataError(f"{bid}.{dimension}: evidence must be a list of exact textual spans")
            for span in spans:
                if span and span not in packet[bid]["response"]:
                    raise DataError(f"{bid}.{dimension}: evidence span not in visible response: {span[:55]!r}")
        if not isinstance(r["notes"], str):
            raise DataError("Annotation notes must be a string")
