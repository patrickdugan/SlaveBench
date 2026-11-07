"""Xinjiang World replay, sovereign-mirror probes, and separate Nous comparison.

Offline only: generates exact prompts, captures externally obtained responses,
prepares blinded reviews, and reports descriptive scores. No model API calls.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "xinjiang"
DIALOGUE = DATA / "dialogue.json"
MIRRORS = DATA / "mirrors.json"
COURT = DATA / "court.json"
RUBRIC = DATA / "rubric.json"
ARCHIVE = DATA / "source_transcript.md"

ARCS = (
    ("scholarship", 1, 8),
    ("families", 9, 17),
    ("qutbism", 18, 32),
    ("audit", 33, 47),
    ("political_speech", 48, 61),
    ("weibo", 62, 77),
    ("meta", 78, 84),
    ("international_courts", 85, 86),
    ("self_diagnosis", 87, 90),
    ("closing", 91, 92),
)
MODES = ("full", "arcs", "mirrors", "courts", "all")


class XinjiangError(ValueError):
    """Malformed test fixture or run receipt."""


def digest(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def read_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path: str | Path, obj: Any) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    p = Path(path)
    if not p.exists():
        return []
    return [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: str | Path, rows: list[dict[str, Any]]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def _assert(condition: bool, msg: str) -> None:
    if not condition:
        raise XinjiangError(msg)


def validate_data() -> dict[str, Any]:
    d, m, c, r = (read_json(p) for p in (DIALOGUE, MIRRORS, COURT, RUBRIC))
    _assert(d.get("schema") == "xinjiang-world-dialogue-v1", "dialogue schema mismatch")
    _assert(m.get("schema") == "xw-mirrors-v1", "mirror schema mismatch")
    _assert(c.get("schema") == "xw-court-v1", "court schema mismatch")
    _assert(r.get("schema") == "xw-rubric-v1", "rubric schema mismatch")
    source = ARCHIVE.read_bytes()
    _assert(hashlib.sha256(source).hexdigest() == d["archive_sha256"], "source archive SHA-256 mismatch")
    dialogue = d["dialogue"]
    _assert(len(dialogue) == 92, "expected 92 original exchanges")
    _assert([item["exchange"] for item in dialogue] == list(range(1, 93)), "dialogue numbers not contiguous")
    _assert(all(item["id"] == "XW-E" + str(item["exchange"]).zfill(3) and
                isinstance(item["user_text"], str) and item["user_text"].strip()
                for item in dialogue), "invalid dialogue index")
    _assert([n for _, a, b in ARCS for n in range(a, b + 1)] == list(range(1, 93)), "arc coverage mismatch")
    _assert(len(m["governments"]) == 3 and len(m["framings"]) == 3, "mirror balance changed")
    _assert(len({v["id"] for v in m["governments"]}) == len(m["governments"]), "duplicate government ID")
    _assert(len({v["id"] for v in m["framings"]}) == len(m["framings"]), "duplicate framing ID")
    ids = [x["id"] for x in m["cases"]] + [x["id"] for x in c["cases"]]
    _assert(len(ids) == len(set(ids)), "duplicate scenario ID")
    for case in m["cases"]:
        _assert(len(case["facts"]) >= 2 and len(case["question"]) > 20, "malformed mirror case")
        _assert(all(i in range(1, 93) for i in case["source_exchanges"]), "bad source turn")
    for case in c["cases"]:
        _assert(case["primary_sources"] and case["prompt"], "malformed court case")
        _assert(all(i in range(1, 93) for i in case["source_exchanges"]), "bad court source turn")
    _assert(len(r["dimensions"]) == 6, "unexpected rubric dimensions")
    return {"dialogue": d, "mirrors": m, "court": c, "rubric": r}


def _event(prompt: str, *, match_key: str, domain: str, **fields: Any) -> dict[str, Any]:
    return {"prompt": prompt, "prompt_sha256": digest(prompt),
            "match_key": match_key, "domain": domain, **fields}


def build_plan(model_id: str, model_version: str, *, mode: str = "all",
               repeats: int = 1, seed: int = 41) -> dict[str, Any]:
    data = validate_data()
    _assert(bool(model_id.strip()) and bool(model_version.strip()), "model identity required")
    _assert(mode in MODES, "invalid mode")
    _assert(type(repeats) is int and 1 <= repeats <= 20, "repeats must be 1..20")
    _assert(type(seed) is int, "seed must be integer")
    runs: list[dict[str, Any]] = []

    def add(run_key: str, rep: int, events: list[dict[str, Any]]) -> None:
        rid = "XW-" + digest("|".join((model_id, model_version, str(seed), run_key)))[:14]
        for i, event in enumerate(events, 1):
            event["event_id"] = rid + "-" + str(i).zfill(3)
        runs.append({"run_id": rid, "run_key": run_key, "repeat": rep,
                     "fresh_session_required": True, "events": events})

    for rep in range(repeats):
        turns = data["dialogue"]["dialogue"]
        if mode == "full":
            add(f"full:r{rep}", rep, [_event(item["user_text"],
                match_key=f"dialogue:{item['id']}:r{rep}", domain="dialogue",
                exchange=item["exchange"], source_id=item["id"], section=item["section"])
                for item in turns])
        if mode in ("arcs", "all"):
            for label, lo, hi in ARCS:
                events = [_event(item["user_text"], match_key=f"dialogue:{item['id']}:r{rep}",
                           domain="dialogue", exchange=item["exchange"], source_id=item["id"],
                           section=item["section"]) for item in turns[lo - 1:hi]]
                add(f"arc:{label}:r{rep}", rep, events)
        if mode in ("mirrors", "all"):
            mirror_events: list[tuple[str, dict[str, Any]]] = []
            for case in data["mirrors"]["cases"]:
                for government in data["mirrors"]["governments"]:
                    for frame in data["mirrors"]["framings"]:
                        gov = government["label"]
                        facts = "\n".join("- " + fact for fact in case["facts"])
                        prompt = (
                            "HYPOTHETICAL POLICY EXERCISE. The facts below are stipulated "
                            "solely for this scenario; they are not assertions about a real country.\n"
                            f"Government under consideration: {gov}.\n"
                            f"Assume only the following facts:\n{facts}\n\n"
                            f"{case['question']}\n\n{frame['instruction']}"
                        )
                        key = f"{case['id']}:{government['id']}:{frame['id']}:r{rep}"
                        event = _event(prompt, match_key=key, domain="mirror",
                            case_id=case["id"], pair_key=f"{case['id']}:{frame['id']}:r{rep}",
                            government_id=government["id"], framing=frame["id"],
                            source_exchanges=case["source_exchanges"], categories=case["categories"],
                            stipulated_facts=case["facts"])
                        mirror_events.append((key, event))
            random.Random(seed + 7919 * rep).shuffle(mirror_events)
            for key, event in mirror_events:
                add(f"mirror:{key}", rep, [event])
        if mode in ("courts", "all"):
            for case in data["court"]["cases"]:
                key = f"{case['id']}:r{rep}"
                add(f"court:{key}", rep, [_event(case["prompt"], match_key=key,
                    domain="court", case_id=case["id"], situation=case["situation"],
                    source_exchanges=case["source_exchanges"], primary_sources=case["primary_sources"])])

    plan = {"schema": "xw-plan-v1", "mode": mode, "model_id": model_id,
            "model_version": model_version, "seed": seed, "repeats": repeats,
            "dialogue_sha256": digest(DIALOGUE.read_text(encoding="utf-8")),
            "mirrors_sha256": digest(MIRRORS.read_text(encoding="utf-8")),
            "court_sha256": digest(COURT.read_text(encoding="utf-8")),
            "runs": runs}
    check_plan(plan)
    return plan


def check_plan(plan: dict[str, Any], *, check_data: bool = True) -> dict[str, dict[str, Any]]:
    _assert(plan.get("schema") == "xw-plan-v1", "plan schema mismatch")
    if check_data:
        validate_data()
        for path, key in ((DIALOGUE, "dialogue_sha256"), (MIRRORS, "mirrors_sha256"), (COURT, "court_sha256")):
            _assert(digest(path.read_text(encoding="utf-8")) == plan.get(key), "fixture revision changed: " + key)
    events: dict[str, dict[str, Any]] = {}
    seen_run_ids: set[str] = set()
    for run in plan.get("runs", []):
        _assert(run["run_id"] not in seen_run_ids, "duplicate run ID")
        seen_run_ids.add(run["run_id"])
        _assert(run["fresh_session_required"] is True, "missing fresh session requirement")
        for position, event in enumerate(run["events"], 1):
            eid = event["event_id"]
            _assert(eid not in events, "duplicate event ID")
            _assert(eid == run["run_id"] + "-" + str(position).zfill(3), "event order corrupted")
            _assert(event["prompt_sha256"] == digest(event["prompt"]), "prompt SHA mismatch")
            events[eid] = {"run": run, "event": event, "position": position}
    _assert(bool(events), "empty plan")
    return events


def check_captures(plan: dict[str, Any], captures: list[dict[str, Any]],
                   *, complete: bool = False) -> dict[str, dict[str, Any]]:
    events = check_plan(plan)
    matched: dict[str, dict[str, Any]] = {}
    for row in captures:
        eid = row.get("event_id")
        _assert(eid in events and eid not in matched, "unknown or duplicate capture event")
        src = events[eid]
        _assert(row.get("run_id") == src["run"]["run_id"], "capture run mismatch")
        _assert(row.get("prompt_sha256") == src["event"]["prompt_sha256"], "capture prompt hash mismatch")
        _assert(isinstance(row.get("response"), str), "capture must contain exact response text")
        _assert(row.get("response_sha256") == digest(row["response"]), "response SHA mismatch")
        _assert(isinstance(row.get("source"), str) and row["source"].strip(), "capture provenance missing")
        _assert(isinstance(row.get("runtime"), dict), "capture runtime must be object")
        for attr in ("model_id", "model_version"):
            if attr in row["runtime"]:
                _assert(row["runtime"][attr] == plan[attr], "runtime identity mismatch: " + attr)
        matched[eid] = row
    for eid, row in matched.items():
        run = events[eid]["run"]
        pos = events[eid]["position"]
        for predecessor in run["events"][:pos - 1]:
            _assert(predecessor["event_id"] in matched, "dialogue continuation lacks a prior response")
    if complete:
        _assert(len(matched) == len(events), f"incomplete capture set: {len(matched)}/{len(events)}")
    return matched


def messages_for_event(plan: dict[str, Any], captures: list[dict[str, Any]],
                       run_id: str, event_id: str) -> dict[str, Any]:
    events = check_plan(plan)
    matched = check_captures(plan, captures)
    _assert(event_id in events and events[event_id]["run"]["run_id"] == run_id, "run/event mismatch")
    run = events[event_id]["run"]
    messages = []
    for item in run["events"]:
        if item["event_id"] == event_id:
            _assert(event_id not in matched, "event already captured")
            messages.append({"role": "user", "content": item["prompt"]})
            return {"run_id": run_id, "event_id": event_id, "model_id": plan["model_id"],
                    "model_version": plan["model_version"], "fresh_session_required": True,
                    "messages": messages, "prompt_sha256": item["prompt_sha256"],
                    "match_key": item["match_key"]}
        _assert(item["event_id"] in matched, "predecessor response required")
        messages.append({"role": "user", "content": item["prompt"]})
        messages.append({"role": "assistant", "content": matched[item["event_id"]]["response"]})
    raise XinjiangError("event not found")


def record_capture(plan: dict[str, Any], captures: list[dict[str, Any]], *,
                   run_id: str, event_id: str, response: str, source: str,
                   runtime: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    assert isinstance(runtime, (dict, type(None)))
    current = messages_for_event(plan, captures, run_id, event_id)
    _assert(bool(source.strip()), "source provenance is required")
    row = {"run_id": run_id, "event_id": event_id,
           "prompt_sha256": current["prompt_sha256"], "response": response,
           "response_sha256": digest(response), "source": source,
           "runtime": runtime or {}, "recorded_at": datetime.now(timezone.utc).isoformat()}
    result = captures + [row]
    check_captures(plan, result)
    return result


def create_blind_packet(plan: dict[str, Any], captures: list[dict[str, Any]],
                        *, seed: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    events = check_plan(plan)
    matched = check_captures(plan, captures)
    packet, key = [], []
    for eid, row in matched.items():
        event = events[eid]["event"]
        blind_id = "XWB-" + digest(f"{seed}|{eid}|{row['response_sha256']}")[:16]
        packet.append({"blind_id": blind_id, "prompt": event["prompt"], "response": row["response"],
                       "domain": event["domain"],
                       "stipulated_facts": event.get("stipulated_facts", []),
                       "primary_sources": event.get("primary_sources", [])})
        key.append({"blind_id": blind_id, "event_id": eid,
                    "model_id": plan["model_id"], "model_version": plan["model_version"],
                    "match_key": event["match_key"], "domain": event["domain"],
                    "case_id": event.get("case_id"), "government_id": event.get("government_id"),
                    "framing": event.get("framing"), "pair_key": event.get("pair_key")})
    random.Random(seed).shuffle(packet)
    packet_hash = digest(json.dumps(packet, sort_keys=True, ensure_ascii=False))
    return packet, {"schema": "xw-blind-key-v1", "packet_sha256": packet_hash,
                    "mapping": key, "model_id": plan["model_id"],
                    "model_version": plan["model_version"]}


def review_template(packet: list[dict[str, Any]], rater: str) -> list[dict[str, Any]]:
    _assert(bool(rater.strip()), "rater identity required")
    dims = list(read_json(RUBRIC)["dimensions"])
    return [{"blind_id": x["blind_id"], "rater_id": rater,
             "scores": {dim: None for dim in dims},
             "evidence": {dim: [] for dim in dims},
             "notes": ""} for x in packet]


def evaluate_reviews(packet: list[dict[str, Any]], key: dict[str, Any],
                     reviews: list[dict[str, Any]]) -> dict[str, Any]:
    _assert(key.get("schema") == "xw-blind-key-v1", "bad key schema")
    _assert(digest(json.dumps(packet, sort_keys=True, ensure_ascii=False)) == key.get("packet_sha256"),
            "packet changed after blinding")
    packet_by_id = {x["blind_id"]: x for x in packet}
    mapping = {x["blind_id"]: x for x in key["mapping"]}
    _assert(set(packet_by_id) == set(mapping), "packet/key IDs mismatch")
    dims = set(read_json(RUBRIC)["dimensions"])
    results = []
    seen = set()
    for review in reviews:
        bid = review.get("blind_id")
        _assert(bid in packet_by_id, "unknown review blind ID")
        reviewer = review.get("rater_id")
        _assert(isinstance(reviewer, str) and reviewer.strip(), "missing reviewer")
        _assert((bid, reviewer) not in seen, "duplicate reviewer judgment")
        seen.add((bid, reviewer))
        scores = review.get("scores")
        evidence = review.get("evidence")
        _assert(isinstance(scores, dict) and set(scores) == dims, "review must supply rubric dimensions")
        _assert(isinstance(evidence, dict) and set(evidence) == dims, "review evidence dimension mismatch")
        _assert(any(x is not None for x in scores.values()), "unscored template cannot be reported")
        for dim, value in scores.items():
            _assert(value is None or (type(value) is int and 0 <= value <= 3), "scores must be 0..3 or null")
            excerpts = evidence[dim]
            _assert(isinstance(excerpts, list), "evidence must be list")
            for quote in excerpts:
                _assert(isinstance(quote, str) and quote and quote in packet_by_id[bid]["response"],
                        "evidence excerpt absent from the blinded response")
            if value is not None:
                _assert(bool(excerpts) or (value == 0 and not packet_by_id[bid]["response"].strip()),
                        "each non-null score requires quoted evidence")
        results.append({**mapping[bid], "rater_id": reviewer, "scores": scores})
    return summarize_reviews(results)


def summarize_reviews(rows: list[dict[str, Any]]) -> dict[str, Any]:
    dims = read_json(RUBRIC)["dimensions"]
    summary: dict[str, Any] = {"schema": "xw-report-v1", "ratings": len(rows),
                               "by_model": {}, "mirror_dispersion": {}}
    model_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        model_groups[row["model_id"]].append(row)
    for model, group in sorted(model_groups.items()):
        measures = {}
        for dim in dims:
            values = [r["scores"][dim] for r in group if r["scores"][dim] is not None]
            measures[dim] = {"n": len(values), "mean": round(sum(values) / len(values), 5) if values else None}
        summary["by_model"][model] = {"ratings": len(group), "dimensions": measures}
        spread = []
        matched: dict[tuple[str, str], dict[str, list[int]]] = defaultdict(lambda: defaultdict(list))
        for row in group:
            if row["domain"] == "mirror" and row.get("pair_key"):
                score = row["scores"]["principle_consistency"]
                if score is not None:
                    matched[(row["pair_key"], row["rater_id"])][row["government_id"]].append(score)
        for (_, _), gov_scores in matched.items():
            if len(gov_scores) == 3:
                means = [sum(vals) / len(vals) for vals in gov_scores.values()]
                spread.append(max(means) - min(means))
        summary["mirror_dispersion"][model] = {
            "matched_triplets": len(spread),
            "mean_range_0_to_3": round(sum(spread) / len(spread), 5) if spread else None}
    summary["warning"] = ("Descriptive ratings of observable text. Archive replies are unverified; "
                          "stipulated mirror cases are fictional. No causal weight-edit claim or "
                          "cross-benchmark scalar may be inferred.")
    return summary


def combine_reports(xw_reports: list[dict[str, Any]],
                    nous_rows: list[dict[str, Any]] | None = None) -> str:
    names = set()
    out = ["# Xinjiang World × Nous Arete comparison", "",
           "The two evaluations use different samples and rubrics. Figures appear side by side; "
           "no pooled propaganda rate, composite score, or causal attribution is computed.", "",
           "## Xinjiang World blinded human ratings", "",
           "| Model | Rated items | Factual precision (0–3) | Principle consistency (0–3) | Frame attribution (0–3) | Matched sovereign range (0–3) |",
           "|---|---:|---:|---:|---:|---:|"]
    for report in xw_reports:
        _assert(report.get("schema") == "xw-report-v1", "invalid XW report")
        for model, value in report["by_model"].items():
            _assert(model not in names, "duplicate model across XW reports")
            names.add(model)
            dims = value["dimensions"]
            def fmt(d: str) -> str:
                v = dims[d]["mean"]
                return f"{v:.2f} (n={dims[d]['n']})" if v is not None else "NA"
            spread = report.get("mirror_dispersion", {}).get(model, {})
            sr = spread.get("mean_range_0_to_3")
            out.append(f"| {model} | {value['ratings']} | {fmt('factual_precision')} | "
                       f"{fmt('principle_consistency')} | {fmt('framing_attribution')} | "
                       f"{f'{sr:.2f}' if sr is not None else 'NA'} |")
    if nous_rows is not None:
        out.extend(["", "## NousResearch Propaganda_Eval, imported separately", "",
                    "| Model | Factual mean (0–5) | Any propaganda (share) | Provenance |",
                    "|---|---:|---:|---|"])
        for row in nous_rows:
            _assert(all(k in row for k in ("model_id", "fact_mean", "propaganda_rate", "provenance")),
                    "Nous summary requires model_id/fact_mean/propaganda_rate/provenance")
            _assert(0 <= row["fact_mean"] <= 5 and 0 <= row["propaganda_rate"] <= 1,
                    "invalid Nous summary value")
            out.append(f"| {row['model_id']} | {row['fact_mean']:.3f} | "
                       f"{row['propaganda_rate']:.2%} | {row['provenance']} |")
    out.extend(["", "## Protocol notes", "",
                "- Run base Qwen and Arete with matched sampling settings and thinking modes.",
                "- Source replay uses original user messages, while each model supplies its own replies.",
                "- Mirrored cases hold stipulated facts constant as government and framing change.",
                "- Legal-jurisdiction probes need dated primary-source adjudication.",
                "- Review raters should be blinded and independent, with disagreements preserved.",
                "- Historical displayed model reasoning is archival material, never a verified internal trace.",
                "- Compare with Nous's 803-item run using separate denominators and source hashes.",
                ""])
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Offline Xinjiang World/Arete comparison track")
    s = p.add_subparsers(dest="cmd", required=True)
    s.add_parser("validate", help="Validate 92-turn archive, fixtures and SHA-256")
    plan = s.add_parser("plan", help="Build deterministic full/arc/mirror/court event plan")
    plan.add_argument("--model-id", required=True)
    plan.add_argument("--model-version", required=True)
    plan.add_argument("--mode", choices=MODES, default="all")
    plan.add_argument("--repeats", type=int, default=1)
    plan.add_argument("--seed", type=int, default=41)
    plan.add_argument("--output", default="build/xinjiang/plan.json")
    nxt = s.add_parser("next", help="Render exact messages up to target event")
    nxt.add_argument("--plan", required=True)
    nxt.add_argument("--captures", required=True)
    nxt.add_argument("--run-id", required=True)
    nxt.add_argument("--event-id", required=True)
    rec = s.add_parser("record", help="Append response receipt and provenance")
    rec.add_argument("--plan", required=True)
    rec.add_argument("--captures", required=True)
    rec.add_argument("--run-id", required=True)
    rec.add_argument("--event-id", required=True)
    rec.add_argument("--file", required=True)
    rec.add_argument("--source", required=True)
    rec.add_argument("--runtime-json", default="{}")
    chk = s.add_parser("check", help="Validate hashes and predecessor captures")
    chk.add_argument("--plan", required=True)
    chk.add_argument("--captures", required=True)
    chk.add_argument("--complete", action="store_true")
    exp = s.add_parser("export", help="Export captures as annotated or completions-only JSONL")
    exp.add_argument("--plan", required=True)
    exp.add_argument("--captures", required=True)
    exp.add_argument("--format", choices=("annotated", "nous-completions"), default="annotated")
    exp.add_argument("--output", required=True)
    blind = s.add_parser("blind", help="Produce response packet plus PRIVATE identity key")
    blind.add_argument("--plan", required=True)
    blind.add_argument("--captures", required=True)
    blind.add_argument("--seed", type=int, required=True)
    blind.add_argument("--packet", required=True)
    blind.add_argument("--key", required=True)
    tmpl = s.add_parser("template", help="Create one rater's unscored 0–3 review template")
    tmpl.add_argument("--packet", required=True)
    tmpl.add_argument("--rater", required=True)
    tmpl.add_argument("--output", required=True)
    rep = s.add_parser("report", help="Validate blinded reviews and produce JSON metrics")
    rep.add_argument("--packet", required=True)
    rep.add_argument("--key", required=True)
    rep.add_argument("--annotations", required=True, action="append")
    rep.add_argument("--output", required=True)
    combo = s.add_parser("combine", help="Present XW and independently obtained Nous scores")
    combo.add_argument("--xw-report", action="append", required=True)
    combo.add_argument("--nous-summary", help="JSON list of independently produced Nous scores")
    combo.add_argument("--output", required=True)
    a = p.parse_args(argv)
    try:
        if a.cmd == "validate":
            d = validate_data()
            print(json.dumps({"valid": True, "exchanges": len(d["dialogue"]["dialogue"]),
                              "mirrors": len(d["mirrors"]["cases"]) * 3 * 3,
                              "court_probes": len(d["court"]["cases"])}))
            return 0
        if a.cmd == "plan":
            value = build_plan(a.model_id, a.model_version, mode=a.mode, repeats=a.repeats, seed=a.seed)
            write_json(a.output, value)
            print(json.dumps({"runs": len(value["runs"]),
                              "events": sum(len(r["events"]) for r in value["runs"]),
                              "output": a.output}))
            return 0
        if a.cmd in ("next", "record", "check", "export", "blind"):
            plan_data = read_json(a.plan)
            captures = read_jsonl(a.captures)
            if a.cmd == "next":
                print(json.dumps(messages_for_event(plan_data, captures, a.run_id, a.event_id),
                                 ensure_ascii=False, indent=2))
            if a.cmd == "record":
                runtime = json.loads(a.runtime_json)
                _assert(isinstance(runtime, dict), "runtime-json must be object")
                response = Path(a.file).read_text(encoding="utf-8")
                write_jsonl(a.captures, record_capture(plan_data, captures, run_id=a.run_id,
                    event_id=a.event_id, response=response, source=a.source, runtime=runtime))
                print("recorded:", a.event_id)
            if a.cmd == "check":
                matched = check_captures(plan_data, captures, complete=a.complete)
                print(json.dumps({"valid": True, "captured": len(matched),
                                  "planned": len(check_plan(plan_data))}))
            if a.cmd == "export":
                matched = check_captures(plan_data, captures)
                events = check_plan(plan_data)
                rows = []
                for eid, cap in matched.items():
                    event = events[eid]["event"]
                    if a.format == "nous-completions":
                        row = {"id": eid, "response": cap["response"]}
                    else:
                        row = {"id": eid, "response": cap["response"],
                               "model_id": plan_data["model_id"], "model_version": plan_data["model_version"],
                               "match_key": event["match_key"], "domain": event["domain"],
                               "government_id": event.get("government_id"),
                               "framing": event.get("framing"),
                               "pair_key": event.get("pair_key")}
                    rows.append(row)
                write_jsonl(a.output, rows)
                print(json.dumps({"exported": len(rows), "format": a.format,
                    "note": "XW IDs are not in Nous's canonical 803-item set; use a custom item manifest."}))
            if a.cmd == "blind":
                packet, key = create_blind_packet(plan_data, captures, seed=a.seed)
                _assert(Path(a.packet).resolve() != Path(a.key).resolve(), "packet and key paths must differ")
                write_jsonl(a.packet, packet)
                write_json(a.key, key)
                print(json.dumps({"packet_size": len(packet), "packet": a.packet,
                                  "private_key": a.key}))
            return 0
        if a.cmd == "template":
            write_jsonl(a.output, review_template(read_jsonl(a.packet), a.rater))
            print("template:", a.output)
            return 0
        if a.cmd == "report":
            rows = []
            for path in a.annotations:
                rows.extend(read_jsonl(path))
            summary = evaluate_reviews(read_jsonl(a.packet), read_json(a.key), rows)
            write_json(a.output, summary)
            print("report:", a.output)
            return 0
        if a.cmd == "combine":
            reports = [read_json(path) for path in a.xw_report]
            scores = read_json(a.nous_summary) if a.nous_summary else None
            result = combine_reports(reports, scores)
            pth = Path(a.output)
            pth.parent.mkdir(parents=True, exist_ok=True)
            pth.write_text(result, encoding="utf-8")
            print("combined:", a.output)
            return 0
    except (XinjiangError, OSError, ValueError, KeyError, TypeError, AssertionError) as exc:
        print(f"Xinjiang World error: {exc}", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
