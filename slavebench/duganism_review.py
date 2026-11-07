"""Proof-carrying, human-review extension of Duganism for freeform answers.

Accepts XW-01 archived-dialogue responses and independently captured Nous 803
answers. Structured Duganism scoring remains in duganism.py. This module creates
blinded review packets and verifies exact quotations, cited evidence pointers,
rater attribution, and metric coverage. It NEVER infers semantic truth from prose.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path
import random
import sys
from typing import Any

from . import duganism as d

DIMENSIONS = tuple([f"E{i}" for i in range(9)] + ["directness", "factual_calibration"])


def _packet_hash(packet: list[dict[str, Any]]) -> str:
    # Preserve compatibility with the original xinjiang.py's packet hash scheme.
    return d.sha(json.dumps(packet, sort_keys=True, ensure_ascii=False))


def _sources(row: dict[str, Any]) -> list[str]:
    arr = row.get("evidence_sources", row.get("primary_sources", []))
    d.require(isinstance(arr, list) and all(isinstance(x, str) for x in arr),
              "evidence_sources must be a list of source IDs or URLs")
    return arr


def pack(rows: list[dict[str, Any]], seed: int = 41) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    d.require(type(seed) is int, "seed must be an integer")
    packet, keys, ids = [], [], set()
    for row in rows:
        identifier = row.get("id")
        model = row.get("model_id")
        reply = row.get("response")
        source = row.get("source")
        d.require(isinstance(identifier, str) and identifier and isinstance(model, str) and model,
                  "source row requires nonempty id and model_id")
        d.require(isinstance(reply, str), "source row must have response text")
        d.require(isinstance(source, str) and source.strip(), "source row requires capture provenance")
        d.require(isinstance(row.get("prompt", ""), str), "source row prompt must be string")
        uid = "DUGR-" + d.sha(f"{seed}|{identifier}|{model}|{d.sha(reply)}")[:16]
        d.require(uid not in ids, "duplicate model/case/reply identity in packet")
        ids.add(uid)
        packet.append({"blind_id": uid, "prompt": row.get("prompt", ""),
                       "response": reply, "evidence_sources": _sources(row)})
        keys.append({"blind_id": uid, "case_id": identifier,
                     "model_id": model, "source": source})
    random.Random(seed).shuffle(packet)
    return packet, {"schema": "duganism-review-key-v0.1", "packet_sha256": _packet_hash(packet),
                    "mapping": keys, "seed": seed}


def _validate_key(packet: list[dict[str, Any]], key: dict[str, Any]) -> dict[str, dict[str, Any]]:
    d.require(key.get("schema") in ("duganism-review-key-v0.1", "xw-blind-key-v1"),
              "unsupported key schema")
    d.require(_packet_hash(packet) == key.get("packet_sha256"), "blinded packet hash mismatch")
    p = {x["blind_id"]: x for x in packet}
    k = {x["blind_id"]: x for x in key["mapping"]}
    d.require(len(p) == len(packet) and len(k) == len(key["mapping"]) and
              set(p) == set(k), "review key and packet identities differ")
    d.require(all("model_id" not in item for item in packet), "provider identities must remain blind")
    return k


def make_template(packet: list[dict[str, Any]], rater_id: str) -> list[dict[str, Any]]:
    d.require(isinstance(rater_id, str) and rater_id.strip(), "rater required")
    return [{
        "blind_id": item["blind_id"], "rater_id": rater_id,
        "dimensions": {name: {"score": None, "quotes": [], "source_refs": [], "rationale": ""}
                       for name in DIMENSIONS},
        "disclosure": "Independent human review; no private model grader", "notes": ""
    } for item in packet]


def validate_reviews(packet: list[dict[str, Any]], key: dict[str, Any],
                     reviews: list[dict[str, Any]]) -> list[dict[str, Any]]:
    mapping = _validate_key(packet, key)
    packet_by_id = {x["blind_id"]: x for x in packet}
    out, visited = [], set()
    for row in reviews:
        bid = row.get("blind_id")
        rater = row.get("rater_id")
        d.require(bid in packet_by_id and isinstance(rater, str) and rater.strip(),
                  "unknown blind ID or missing rater")
        d.require((bid, rater) not in visited, "duplicate blinded reviewer row")
        visited.add((bid, rater))
        dimensions = row.get("dimensions")
        d.require(isinstance(dimensions, dict) and set(dimensions) == set(DIMENSIONS),
                  "unexpected Duganism review dimensions")
        packet_item = packet_by_id[bid]
        allowed_sources = set(_sources(packet_item))
        has_score = False
        values: dict[str, int | None] = {}
        for name in DIMENSIONS:
            entry = dimensions[name]
            d.require(isinstance(entry, dict) and set(entry) ==
                      {"score", "quotes", "source_refs", "rationale"}, "invalid dimension annotation")
            score = entry["score"]
            d.require(score is None or (type(score) is int and 0 <= score <= 3),
                      "score must be 0..3 or null")
            quotes, sources = entry["quotes"], entry["source_refs"]
            d.require(isinstance(quotes, list) and all(isinstance(x, str) and x for x in quotes),
                      "quotes must be strings")
            d.require(isinstance(sources, list) and all(isinstance(x, str) for x in sources),
                      "source refs must be strings")
            d.require(len(sources) == len(set(sources)) and set(sources) <= allowed_sources,
                      "review references evidence absent from frozen packet")
            for quote in quotes:
                d.require(quote in packet_item["response"], "quote absent from exact model output")
            if score is not None:
                d.require(bool(quotes) or (score == 0 and not packet_item["response"].strip()),
                          "scored finding requires verbatim supporting quote")
                d.require(isinstance(entry["rationale"], str) and
                          len(entry["rationale"].strip()) >= 12, "scored finding requires explanation")
                if name == "factual_calibration":
                    d.require(bool(sources), "factual calibration requires independent source pointers")
                has_score = True
            values[name] = score
        d.require(has_score, "unscored template cannot be submitted as a completed review")
        key_row = mapping[bid]
        out.append({"blind_id": bid, "rater_id": rater,
                    "model_id": key_row["model_id"],
                    "case_id": key_row.get("case_id", key_row.get("match_key", bid)),
                    "scores": values,
                    "review_sha256": d.sha(d.canonical(row)),
                    "response_sha256": d.sha(packet_item["response"])})
    return out


def report(packet: list[dict[str, Any]], key: dict[str, Any],
           annotations: list[dict[str, Any]]) -> dict[str, Any]:
    reviewed = validate_reviews(packet, key, annotations)
    by_model: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in reviewed:
        by_model[row["model_id"]].append(row)
    means: dict[str, Any] = {}
    for model, group in sorted(by_model.items()):
        scores = {}
        for dim in DIMENSIONS:
            values = [x["scores"][dim] for x in group if x["scores"][dim] is not None]
            scores[dim] = {"n": len(values), "mean": round(sum(values) / len(values), 5)
                           if values else None}
        means[model] = {"reviews": len(group), "dimensions": scores}
    pair_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in reviewed:
        pair_groups[row["blind_id"]].append(row)
    disagreement = {"paired_items": 0, "dimension_pairs": 0, "exact_agreements": 0}
    for group in pair_groups.values():
        if len(group) < 2:
            continue
        disagreement["paired_items"] += 1
        # Pairwise agreement for first two distinct raters, no forced resolution.
        a, b = group[:2]
        for dim in DIMENSIONS:
            x, y = a["scores"][dim], b["scores"][dim]
            if x is None or y is None:
                continue
            disagreement["dimension_pairs"] += 1
            disagreement["exact_agreements"] += (x == y)
    return {"schema": "duganism-freeform-report-v0.1", "judge_version": d.VERSION,
            "packet_sha256": _packet_hash(packet),
            "reviews": len(reviewed), "models": means,
            "inter_rater": disagreement,
            "judgments": reviewed,
            "limitations": "Scores are explicitly human-entered and quote-grounded, "
                           "not verified factual semantics or an independent trained AI judge."}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Duganism quote-verified freeform reviewer")
    sub = p.add_subparsers(dest="command", required=True)
    pkg = sub.add_parser("pack", help="Blind external freeform model outputs, including Nous results")
    pkg.add_argument("--responses", required=True)
    pkg.add_argument("--seed", type=int, default=41)
    pkg.add_argument("--packet", required=True)
    pkg.add_argument("--key", required=True)
    form = sub.add_parser("template", help="Produce empty independent reviewer forms")
    form.add_argument("--packet", required=True)
    form.add_argument("--rater", required=True)
    form.add_argument("--output", required=True)
    rep = sub.add_parser("report", help="Validate quote- and evidence-grounded reviews")
    rep.add_argument("--packet", required=True)
    rep.add_argument("--key", required=True)
    rep.add_argument("--annotations", action="append", required=True)
    rep.add_argument("--output", required=True)
    a = p.parse_args(argv)
    try:
        if a.command == "pack":
            d.require(Path(a.packet).resolve() != Path(a.key).resolve(),
                      "private key and reviewer packet must use different paths")
            packet, key = pack(d.load_jsonl(a.responses), a.seed)
            d.save_jsonl(a.packet, packet)
            d.save(a.key, key)
            print(d.canonical({"packed": len(packet), "packet": a.packet, "key": a.key}))
        elif a.command == "template":
            packet = d.load_jsonl(a.packet)
            d.save_jsonl(a.output, make_template(packet, a.rater))
            print(d.canonical({"template_count": len(packet), "output": a.output}))
        elif a.command == "report":
            rows = []
            for x in a.annotations:
                rows.extend(d.load_jsonl(x))
            result = report(d.load_jsonl(a.packet), d.load(a.key), rows)
            d.save(a.output, result)
            print(d.canonical({"reviews": result["reviews"], "report": a.output}))
        return 0
    except (d.JudgeError, OSError, ValueError, KeyError, TypeError) as exc:
        print(f"Duganism reviewer error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
